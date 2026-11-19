"""Valida os PBIPs contra os dados exportados, sem abrir o Power BI.

Para cada PBIP em powerbi/:
  1. cada coluna de origem (sourceColumn) existe no .parquet que a tabela le
  2. cada campo usado nos visuais (Entity/Property e queryRef) existe no modelo
  3. cada coluna das relacoes existe
  4. cada referencia DAX Tabela[Campo] existe e cada [Medida] solta e conhecida

Opcional (--tmdl): carrega o modelo com a biblioteca do Power BI Desktop
(TmdlSerializer), que acusa erro de sintaxe TMDL.

Uso: python ferramentas/validar_pbip.py [--tmdl]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
EXPORTS = RAIZ / "dados" / "exports"


def nome(t):
    t = t.strip()
    return t[1:-1].replace("''", "'") if t.startswith("'") else t


def ler_modelo(pasta_modelo):
    tabelas = {}
    for f in (pasta_modelo / "definition" / "tables").glob("*.tmdl"):
        txt = f.read_text(encoding="utf-8")
        tab = nome(re.search(r"^table (.+)$", txt, re.M).group(1))
        cols, meds, fontes = {}, set(), {}
        atual = None
        for linha in txt.splitlines():
            m = re.match(r"^\tcolumn ('(?:[^']|'')+'|[^\s=]+)", linha)
            if m:
                atual = nome(m.group(1))
                cols[atual] = None
                continue
            m = re.match(r"^\tmeasure ('(?:[^']|'')+'|[^\s=]+)", linha)
            if m:
                meds.add(nome(m.group(1)))
                atual = None
                continue
            m = re.match(r"^\t\tsourceColumn: (.+)$", linha)
            if m and atual:
                cols[atual] = nome(m.group(1))
        arq = re.findall(r'"([\w]+\.parquet)"', txt)
        tabelas[tab] = {"cols": cols, "meds": meds, "parquet": arq, "txt": txt}
    return tabelas


def colunas_parquet(arq):
    p = EXPORTS / arq
    if not p.exists():
        return None
    return {r[0] for r in duckdb.sql(f"DESCRIBE SELECT * FROM '{p.as_posix()}'").fetchall()}


def validar(pbip):
    erros = []
    modelo = next(pbip.parent.glob("*.SemanticModel"))
    relatorio = next(pbip.parent.glob("*.Report"))
    tabs = ler_modelo(modelo)
    campos = {t: set(v["cols"]) | v["meds"] for t, v in tabs.items()}
    todas_meds = set().union(*(v["meds"] for v in tabs.values()))
    todos_campos = set().union(*campos.values())

    # 0. nomes repetidos: o Power BI nao diferencia maiusculas, e medida nao pode
    #    ter o nome de nenhuma coluna da mesma tabela nem de outra medida do modelo
    vistos = {}
    for t, v in tabs.items():
        cols = {c.lower() for c in v["cols"]}
        for med in v["meds"]:
            if med.lower() in cols:
                erros.append(f"{t}: medida '{med}' tem o mesmo nome de uma coluna")
            if med.lower() in vistos:
                erros.append(f"medida '{med}' existe em {vistos[med.lower()]} e {t}")
            vistos[med.lower()] = t

    # 1. colunas de origem x parquet
    for t, v in tabs.items():
        if not v["parquet"]:
            continue
        # tabela pode juntar varios parquets: vale a uniao das colunas
        pc = set()
        for arq in v["parquet"]:
            cols_arq = colunas_parquet(arq)
            if cols_arq is None:
                erros.append(f"{t}: arquivo {arq} nao existe em dados/exports")
            else:
                pc |= cols_arq
        arqs = ", ".join(v["parquet"])
        # colunas criadas no Power Query
        criadas = set(re.findall(r'\{"[^"]+", "([^"]+)"\}', v["txt"]))                       # Table.RenameColumns
        criadas |= set(re.findall(r'Table\.AddColumn\(\w+, "([^"]+)"', v["txt"]))
        criadas |= set(re.findall(r'\{"([^"]+)", each ', v["txt"]))                           # Table.Group
        for novos in re.findall(r'Table\.ExpandTableColumn\(\w+, "[^"]+", \{[^}]*\}, \{([^}]*)\}', v["txt"]):
            criadas |= set(re.findall(r'"([^"]+)"', novos))
        # colunas citadas no Power Query (SelectColumns / TransformColumnTypes)
        m_cols = set()
        for lista in re.findall(r"Table\.SelectColumns\([^,]+, \{([^}]*)\}", v["txt"]):
            m_cols |= set(re.findall(r'"([^"]+)"', lista))
        m_cols |= set(re.findall(r'\{"([^"]+)", (?:type \w+|Int64\.Type)\}', v["txt"]))
        for c in sorted(m_cols - pc - criadas):
            erros.append(f"{t}: Power Query cita a coluna {c}, que nao existe em {arqs}")
        for c, src in v["cols"].items():
            if src and src not in pc and src not in criadas:
                erros.append(f"{t}[{c}]: sourceColumn {src} nao existe em {arqs}")

    # 2. campos dos visuais
    for f in relatorio.rglob("*.json"):
        txt = f.read_text(encoding="utf-8")
        pares = re.findall(r'"Entity":\s*"([^"]+)"\s*}\s*}\s*,\s*"Property":\s*"([^"]+)"', txt)
        pares += re.findall(r'"(?:queryRef|metadata)":\s*"(?:\w+\()?([A-Za-z]\w*)\.([^"()]+)\)?"', txt)
        for t, c in pares:
            if t not in campos:
                erros.append(f"{f.parent.name}: tabela {t} nao existe")
            elif c not in campos[t]:
                erros.append(f"{f.parent.name}: {t}.{c} nao existe")

    # 3. relacoes
    rel = modelo / "definition" / "relationships.tmdl"
    if rel.exists():
        for lado in re.findall(r"(?:from|to)Column: (.+)", rel.read_text(encoding="utf-8")):
            t, c = re.match(r"('(?:[^']|'')+'|[^.]+)\.(.+)", lado.strip()).groups()
            if nome(t) not in campos or nome(c) not in campos[nome(t)]:
                erros.append(f"relacao: {lado.strip()} nao existe")

    # 4. DAX
    for t, v in tabs.items():
        dax = "\n".join(l for l in v["txt"].splitlines() if not l.strip().startswith(("lineageTag", "annotation", "sourceColumn")))
        dax = re.sub(r"partition [\s\S]*?(?=\n\t\w|\Z)", "", dax)
        for tt, c in re.findall(r"('(?:[^']|'')+'|\b[A-Za-z]\w*)\[([^\]]+)\]", dax):
            if nome(tt) in campos and c not in campos[nome(tt)]:
                erros.append(f"DAX em {t}: {nome(tt)}[{c}] nao existe")
        locais = set(re.findall(r'"(@?[^"]+)"\s*,', dax))
        for c in re.findall(r"(?<![\w'\]])\[([^\]]+)\]", dax):
            if c not in todas_meds and c not in todos_campos and c not in locais and not c.startswith("@"):
                erros.append(f"DAX em {t}: [{c}] desconhecido")
    return sorted(set(erros))


def validar_tmdl(pasta_modelo):
    ps = (
        "$d = (Get-AppxPackage *MicrosoftPowerBIDesktop*).InstallLocation; "
        "if (-not $d) { $d = 'C:\\Program Files\\Microsoft Power BI Desktop' }; "
        "Add-Type -Path (Join-Path $d 'bin\\Microsoft.PowerBI.Tabular.dll'); "
        f"$db = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder('{pasta_modelo / 'definition'}'); "
        "'OK: ' + $db.Model.Tables.Count + ' tabelas'"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "sem resposta"


if __name__ == "__main__":
    total = 0
    for pbip in sorted((RAIZ / "powerbi").glob("*.pbip")):
        erros = validar(pbip)
        total += len(erros)
        extra = f" | TMDL {validar_tmdl(next(pbip.parent.glob('*.SemanticModel')))}" if "--tmdl" in sys.argv else ""
        print(f"{pbip.name}: {len(erros)} problema(s){extra}")
        for e in erros:
            print("   -", e)
    sys.exit(1 if total else 0)
