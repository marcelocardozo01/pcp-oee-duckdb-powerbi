"""Leva as respostas do Google Forms para o pipeline.

  python kit_coleta/google_forms/importar_google.py <respostas.xlsx> <pasta das outras planilhas> <pasta de dados de destino>

  respostas.xlsx  a planilha "PCP - Coleta (respostas)" baixada do Google
                  (Arquivo > Fazer download > Microsoft Excel), com as abas Producao, Paradas e Refugo
  pasta das outras planilhas
                  precisa ter pelo menos 01_Cadastros.xlsx; as planilhas 04 a 07 do kit sao opcionais

O que ele faz: transforma as tres abas de respostas nas planilhas 02 (apontamento) e 03 (diario de bordo)
do kit e chama o importador normal. Produto vem como "1001 - Tampa..." e fica so o codigo.
"""
import shutil
import sys
import tempfile
from datetime import datetime, time
from pathlib import Path

import openpyxl

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
import importar_planilhas
from esquema import PLANILHAS
from gerar_modelos import montar


def respostas(caminho, aba):
    """Linhas de uma aba de respostas, como dicionarios pelo titulo da pergunta."""
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        if aba not in wb.sheetnames:
            raise SystemExit(f"{Path(caminho).name}: nao achei a aba {aba}. Abas: {wb.sheetnames}")
        linhas = list(wb[aba].iter_rows(values_only=True))
    finally:
        wb.close()
    if not linhas:
        return []
    cab = [str(c).strip() if c is not None else "" for c in linhas[0]]
    return [dict(zip(cab, l)) for l in linhas[1:] if l and any(x not in (None, "") for x in l)]


def hhmm(v):
    if isinstance(v, (datetime, time)):
        return v.strftime("%H:%M")
    return None if v is None else str(v).strip()[:5]


def num(v):
    if v in (None, ""):
        return None
    try:
        return int(float(str(v).replace(",", ".")))
    except ValueError:
        return None


def main(arq_respostas, pasta_outras, destino):
    pasta_outras = Path(pasta_outras)
    if not (pasta_outras / "01_Cadastros.xlsx").exists():
        raise SystemExit(f"Falta 01_Cadastros.xlsx em {pasta_outras}")
    prod = [[r.get("Data"), num(r.get("Turno")), r.get("Máquina"), num(r.get("OP")), num(str(r.get("Produto") or "").split(" - ")[0]),
             num(r.get("Operador")), hhmm(r.get("Hora início")), hhmm(r.get("Hora fim")), num(r.get("Peças produzidas")),
             num(r.get("Refugo")) or 0, num(r.get("Retrabalho")), None] for r in respostas(arq_respostas, "Producao")]
    par = [[r.get("Data"), num(r.get("Turno")), r.get("Máquina"), hhmm(r.get("Hora início")), num(r.get("Duração (min)")), r.get("Motivo"),
            num(r.get("OP")), r.get("Líder")] for r in respostas(arq_respostas, "Paradas")]
    ref = [[r.get("Data"), num(r.get("Turno")), r.get("Máquina"), num(r.get("OP")), r.get("Defeito"), num(r.get("Quantidade"))]
           for r in respostas(arq_respostas, "Refugo")]
    print(f"Respostas do Google: {len(prod)} de producao, {len(par)} de parada, {len(ref)} de refugo")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for arquivo in PLANILHAS:                            # cadastros e planilhas opcionais vem da pasta informada
            if (pasta_outras / arquivo).exists() and arquivo[:2] not in ("02", "03"):
                shutil.copy(pasta_outras / arquivo, tmp / arquivo)
        montar(tmp / "02_Apontamento de Producao.xlsx", "02_Apontamento de Producao.xlsx", {"Apontamentos": prod})
        montar(tmp / "03_Diario de Bordo.xlsx", "03_Diario de Bordo.xlsx", {"Paradas": par, "Refugo": ref})
        importar_planilhas.main(tmp, destino)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
