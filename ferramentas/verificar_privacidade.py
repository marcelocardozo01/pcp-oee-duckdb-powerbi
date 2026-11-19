"""Auditoria antes de publicar: procura termos proibidos em TUDO que vai para o repositorio.

Varre:
  * todos os arquivos de texto do projeto (codigo, SQL, PBIP, docs)
  * os valores de texto de todos os .parquet e .xlsx
Checa tambem:
  * nenhuma pasta .pbi/ (cache do Power BI Desktop, guarda dados) e nenhum cache.abf
  * nenhum caminho absoluto da pasta de usuario do Windows

A lista de termos proibidos fica FORA do repositorio (ela mesma teria os nomes que
nao podem sair). Formato: um termo por linha; "re:" = expressao regular,
"cs:" = diferencia maiusculas; o resto e texto sem diferenciar maiusculas.

Uso: python ferramentas/verificar_privacidade.py --termos <arquivo fora do repo>
Sai com codigo 1 se achar qualquer coisa.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
IGNORAR = {".git", "__pycache__", ".venv"}
BINARIOS = {".parquet", ".xlsx", ".duckdb", ".png", ".jpg", ".pdf", ".abf", ".wal"}


PALAVRA = re.compile(r"[0-9A-Za-zÀ-ÿ]+")


def normalizar(t):
    return " ".join(PALAVRA.findall(t.lower()))


class Termos:
    """Termos de palavras inteiras sao comparados por n-gramas (rapido mesmo com milhares
    de nomes); numeros por conjunto; o resto (poucos) por expressao regular."""

    def __init__(self, arq):
        self.frases, self.numeros, self.regras = {}, set(), []
        for linha in Path(arq).read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha:
                continue
            if linha.startswith("num:"):
                self.numeros.add(linha[4:])
            elif linha.startswith("re:"):
                self.regras.append((linha, re.compile(linha[3:])))
            elif linha.startswith("cs:"):
                self.regras.append((linha, re.compile(re.escape(linha[3:]))))
            elif re.fullmatch(r"[0-9A-Za-zÀ-ÿ ]+", linha):
                self.frases[normalizar(linha)] = linha
            else:
                self.regras.append((linha, re.compile(re.escape(linha), re.I)))
        self.max_n = max((len(f.split()) for f in self.frases), default=1)

    def __len__(self):
        return len(self.frases) + len(self.numeros) + len(self.regras)

    def procurar(self, texto):
        achados = []
        palavras = normalizar(texto).split()
        vistos = set()
        for n in range(1, self.max_n + 1):
            for i in range(len(palavras) - n + 1):
                g = " ".join(palavras[i:i + n])
                if g in self.frases and g not in vistos:
                    vistos.add(g)
                    achados.append((self.frases[g], g))
        for num in set(re.findall(r"(?<![\d.])\d{5,}(?![\d])", texto)) & self.numeros:
            achados.append(("num:" + num, num))
        for rotulo, rx in self.regras:
            m = rx.search(texto)
            if m:
                ini = max(0, m.start() - 40)
                achados.append((rotulo, texto[ini:m.end() + 40].replace("\n", " ")))
        return achados


def arquivos_publicaveis():
    """Arquivos que o git publicaria (respeita o .gitignore); sem git, todos."""
    try:
        r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           cwd=RAIZ, capture_output=True, text=True, check=True)
        return [RAIZ / l for l in r.stdout.splitlines() if l]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [f for f in RAIZ.rglob("*") if f.is_file() and not IGNORAR & set(f.relative_to(RAIZ).parts)]


def textos_de_dados(f):
    if f.suffix == ".parquet":
        con = duckdb.connect()
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM '{f.as_posix()}'").fetchall()
                if r[1] == "VARCHAR"]
        partes = cols[:]
        for c in cols:
            partes += [v for (v,) in con.execute(f"SELECT DISTINCT \"{c}\" FROM '{f.as_posix()}'").fetchall() if v]
        return "\n".join(partes)
    if f.suffix == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(f, read_only=True)
        return "\n".join(str(c) for ws in wb for row in ws.iter_rows(values_only=True) for c in row if c is not None)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--termos", required=True)
    args = ap.parse_args()
    if Path(args.termos).resolve().is_relative_to(RAIZ):
        sys.exit("A lista de termos precisa ficar FORA do repositorio.")
    termos = Termos(args.termos)
    achados = []
    arquivos = arquivos_publicaveis()
    for f in arquivos:
        rel = f.relative_to(RAIZ)
        if ".pbi" in rel.parts or f.name == "cache.abf":
            achados.append(f"{rel}: cache do Power BI (nao publicar)")
            continue
        if f.suffix.lower() in (".parquet", ".xlsx"):
            texto = textos_de_dados(f)
        elif f.suffix.lower() in BINARIOS:
            continue
        else:
            texto = f.read_text(encoding="utf-8", errors="replace")
        texto_nome = str(rel) + "\n" + texto
        if re.search(r"[A-Za-z]:\\+Users\\+", texto_nome):
            achados.append(f"{rel}: caminho absoluto de usuario")
        for rotulo, trecho in termos.procurar(texto_nome):
            achados.append(f"{rel}: [{rotulo}] ...{trecho}...")
    print(f"{len(arquivos)} arquivos verificados, {len(termos)} termos.")
    for a in achados:
        print(" -", a)
    print("OK: nada encontrado." if not achados else f"{len(achados)} ocorrencia(s).")
    sys.exit(1 if achados else 0)


if __name__ == "__main__":
    main()
