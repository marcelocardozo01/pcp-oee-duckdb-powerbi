"""Gera o kit de coleta a partir de esquema.py:

  modelos/             planilhas em branco, com instrucoes, listas de escolha e uma linha de exemplo
  exemplo_preenchido/  as mesmas planilhas com uma semana da fabrica ficticia (5 a 10/10/2026)
  imprimir/            ficha de turno em papel, para quem ainda nao tem computador no chao de fabrica

Uso: python kit_coleta/gerar_modelos.py
"""
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))
from esquema import MOTIVOS, PLANILHAS, STATUS_OP, TIPOS_ITEM

ESCURO, CLARO, LIMA = "0A4250", "6FA9B5", "C5DF16"
LISTAS = {"Turno": '"1,2,3"', "Motivo": '"' + ",".join(MOTIVOS) + '"', "Status": '"' + ",".join(STATUS_OP) + '"',
          "Tipo": '"' + ",".join(TIPOS_ITEM) + '"'}
FORMATO = {"data": "dd/mm/yyyy", "datahora": "dd/mm/yyyy hh:mm", "hora": "@", "inteiro": "0", "numero": "#,##0.00##"}
EXEMPLO_VAZIO = {"data": datetime(2026, 10, 5), "datahora": datetime(2026, 10, 5, 6, 0), "hora": "06:00", "inteiro": 1, "numero": 1.0, "texto": "exemplo"}


def montar(caminho, arquivo, dados=None):
    """Escreve uma planilha do esquema. `dados` = {aba: lista de linhas}; sem dados, vai so o modelo."""
    spec = PLANILHAS[arquivo]
    wb = Workbook()
    guia = wb.active
    guia.title = "Como preencher"
    guia.column_dimensions["A"].width = 26
    guia.column_dimensions["B"].width = 26
    guia.column_dimensions["C"].width = 12
    guia.column_dimensions["D"].width = 90
    guia.append([arquivo.replace(".xlsx", "").split("_", 1)[1]])
    guia["A1"].font = Font(bold=True, size=14, color=ESCURO)
    guia.append(["Quem preenche e quando:", None, None, spec["quem"]])
    guia.append(["Regras:", None, None, "Não mude o nome das abas nem dos títulos das colunas. Pode inserir colunas novas e linhas acima do cabeçalho. "
                                        "Título escuro = obrigatório; título claro = opcional."])
    guia.append([])
    guia.append(["Aba", "Coluna", "Obrigatória", "O que preencher"])
    for c in guia[5]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=ESCURO)
    for aba, (descricao, colunas) in spec["abas"].items():
        guia.append([aba, None, None, descricao])
        guia.cell(guia.max_row, 1).font = Font(bold=True)
        for nome, tipo, obrig, ajuda in colunas:
            guia.append([None, nome, "sim" if obrig else "não", ajuda or {"data": "Data", "hora": "HH:MM"}.get(tipo, "")])
    for linha in guia.iter_rows(min_row=2):
        linha[3].alignment = Alignment(wrap_text=True, vertical="top")

    for aba, (descricao, colunas) in spec["abas"].items():
        ws = wb.create_sheet(aba)
        ws.append([f"{aba.upper()} - {arquivo.split('_', 1)[1].replace('.xlsx', '')}"])
        ws["A1"].font = Font(bold=True, size=12, color=ESCURO)
        ws.append([descricao])
        ws["A2"].font = Font(italic=True, color="555555")
        ws.append([])
        ws.append([c[0] for c in colunas])
        for j, (nome, tipo, obrig, ajuda) in enumerate(colunas, 1):
            cel = ws.cell(4, j)
            cel.font = Font(bold=True, color="FFFFFF")
            cel.fill = PatternFill("solid", fgColor=ESCURO if obrig else CLARO)
            cel.alignment = Alignment(wrap_text=True, vertical="center")
            if ajuda:
                cel.comment = Comment(ajuda, "PCP")
            letra = get_column_letter(j)
            ws.column_dimensions[letra].width = max(13, min(34, len(nome) + 5))
            if nome in LISTAS:
                dv = DataValidation(type="list", formula1=LISTAS[nome], allow_blank=True, showErrorMessage=nome != "Motivo")
                ws.add_data_validation(dv)
                dv.add(f"{letra}5:{letra}5000")
        ws.freeze_panes = "A5"
        linhas = (dados or {}).get(aba)
        if linhas is None and dados is None:                # modelo em branco: uma linha de exemplo, em cinza
            linhas = [[EXEMPLO_VAZIO[c[1]] if c[2] else None for c in colunas]]
            for j, (nome, tipo, obrig, _) in enumerate(colunas):
                if nome in ("Motivo", "Status", "Tipo") and obrig:
                    linhas[0][j] = {"Motivo": MOTIVOS[4], "Status": STATUS_OP[0], "Tipo": TIPOS_ITEM[0]}[nome]
                if nome == "Mês":
                    linhas[0][j] = "2026-10"
                if nome == "Hora fim":
                    linhas[0][j] = "14:00"
        for linha in linhas or []:
            ws.append(list(linha))
        for j, (nome, tipo, _, _) in enumerate(colunas, 1):
            for r in range(5, ws.max_row + 1):
                c = ws.cell(r, j)
                if tipo in FORMATO:
                    c.number_format = FORMATO[tipo]
                if dados is None:
                    c.font = Font(italic=True, color="999999")
        if dados is None:
            ws["A3"] = "A linha em cinza é só um exemplo de formato: apague antes de usar."
            ws["A3"].font = Font(color="B45309", bold=True)
    wb.save(caminho)


def exemplo():
    """Uma semana (5 a 10/10/2026) da fabrica ficticia, no formato das planilhas."""
    con = duckdb.connect()
    exp, bru = (RAIZ / "dados" / "exports").as_posix(), RAIZ / "dados" / "brutos"
    q = lambda sql: [list(r) for r in con.execute(sql).fetchall()]
    ini, fim = "DATE '2026-10-05'", "DATE '2026-10-10'"
    pq = lambda n: f"read_parquet('{bru.as_posix()}/erp/{n}.parquet')"
    d = {"01_Cadastros.xlsx": {
        "Máquinas": q(f"SELECT CODIGO_RECURSO, DESCRICAO, CELULA, CUSTO_HORA FROM {pq('recursos')}"),
        "Produtos": q(f"SELECT CODIGO_PRODUTO, DESCRICAO, FAMILIA, CELULA, PESO_G, CUSTO_PADRAO, PRECO_VENDA FROM {pq('produtos')}"),
        "Roteiros": q(f"SELECT CODIGO_PRODUTO, CODIGO_RECURSO, CICLO_PADRAO_S, CAVIDADES, SETUP_PADRAO_MIN FROM {pq('roteiros')}"),
        "Materiais": q(f"SELECT * FROM {pq('materiais')}"),
        "Estrutura": q(f"SELECT * FROM {pq('estrutura')}"),
        "Clientes": q(f"SELECT * FROM {pq('clientes')}")}}
    d["02_Apontamento de Producao.xlsx"] = {"Apontamentos": q(f"""
        SELECT CAST(DATA AS TIMESTAMP), TURNO, CODIGO_RECURSO, NUMERO_OP, CODIGO_PRODUTO, OPERADOR, STRFTIME(INICIO, '%H:%M'),
               STRFTIME(FIM, '%H:%M'), QTD_PRODUZIDA, QTD_REFUGO, QTD_RETRABALHO, NULL
        FROM read_parquet('{exp}/apontamento.parquet') WHERE DATA BETWEEN {ini} AND {fim} ORDER BY DATA, CODIGO_RECURSO, INICIO""")}
    ref = pd.read_excel(bru / "diario_bordo" / "Diario de Bordo_2026-10.xlsx", sheet_name="Refugo", header=2)
    ref = ref[(ref["Data"] >= "2026-10-05") & (ref["Data"] <= "2026-10-10")]
    d["03_Diario de Bordo.xlsx"] = {
        "Paradas": q(f"""SELECT CAST(DATA AS TIMESTAMP), TURNO, CODIGO_RECURSO, STRFTIME(INICIO, '%H:%M'), CAST(DURACAO_MIN AS INTEGER),
                                MOTIVO_DIGITADO, NULL, LIDER
                         FROM read_parquet('{exp}/parada.parquet') WHERE DATA BETWEEN {ini} AND {fim} ORDER BY DATA, CODIGO_RECURSO, INICIO"""),
        "Refugo": [[r["Data"].to_pydatetime(), int(r["Turno"]), r["Máquina"], int(r["OP"]), r["Defeito"], int(r["Quantidade"])] for _, r in ref.iterrows()]}
    pg = pd.read_excel(bru / "programa" / "Programa Semanal_2026-S41.xlsx", sheet_name="PROGRAMA", header=3)
    d["04_Programa Semanal.xlsx"] = {"PROGRAMA": [[r["Data"].to_pydatetime(), r["Máquina"], int(r["Seq."]), int(r["OP"]), int(r["Cód. produto"]),
                                                   r["Produto"], int(r["Qtd. programada"])] for _, r in pg.iterrows()]}
    ops = f"""(SELECT NUMERO_OP FROM read_parquet('{exp}/apontamento.parquet') WHERE DATA BETWEEN {ini} AND {fim}
               UNION SELECT NUMERO_OP FROM read_parquet('{exp}/programa_dia.parquet') WHERE DATA BETWEEN {ini} AND {fim})"""
    d["05_Ordens e Pedidos.xlsx"] = {
        "Ordens": q(f"""SELECT NUMERO_OP, CODIGO_PRODUTO, CODIGO_RECURSO, NUMERO_PEDIDO, QTD_PLANEJADA, DATA_ABERTURA, INICIO_PROGRAMADO, FIM_PROGRAMADO,
                               DATA_NECESSIDADE, CASE WHEN DATA_ENCERRAMENTO > {fim} + INTERVAL 1 DAY THEN 'Em produção' ELSE STATUS END,
                               CASE WHEN DATA_ENCERRAMENTO > {fim} + INTERVAL 1 DAY THEN NULL ELSE DATA_ENCERRAMENTO END
                        FROM {pq('ordens_producao')} WHERE NUMERO_OP IN {ops} ORDER BY 1"""),
        "Pedidos": q(f"""SELECT NUMERO_PEDIDO, CODIGO_CLIENTE, CODIGO_PRODUTO, QTD_PEDIDA, DATA_PEDIDO, DATA_PROMETIDA,
                                CASE WHEN DATA_ENTREGA > {fim} THEN NULL ELSE DATA_ENTREGA END,
                                CASE WHEN DATA_ENTREGA > {fim} THEN NULL ELSE QTD_ENTREGUE END
                         FROM {pq('pedidos_venda')} WHERE NUMERO_PEDIDO IN (SELECT NUMERO_PEDIDO FROM {pq('ordens_producao')} WHERE NUMERO_OP IN {ops})
                         ORDER BY 1""")}
    inv = pd.read_excel(bru / "planilhas" / "Inventario Ciclico_2026.xlsx", sheet_name="CONTAGENS", header=2)
    inv = inv[(inv["Data"] >= "2026-10-05") & (inv["Data"] <= "2026-10-10")]
    d["06_Materiais e Estoque.xlsx"] = {
        "Requisições": q(f"SELECT DATA, NUMERO_OP, CODIGO_MATERIAL, QUANTIDADE FROM {pq('requisicoes_material')} WHERE DATA BETWEEN {ini} AND {fim} ORDER BY 1, 2"),
        "Saldo diário": q(f"SELECT DATA, CODIGO_ITEM, TIPO_ITEM, SALDO, CUSTO_UNITARIO FROM {pq('estoque_diario')} WHERE DATA BETWEEN {ini} AND {fim} ORDER BY 1, 2"),
        "Inventário": [[r["Data"].to_pydatetime(), str(r["Código do item"]), r["Tipo"], float(r["Saldo sistema"]), float(r["Qtd. contada"]), r["Contador"]]
                       for _, r in inv.iterrows()]}
    prev = pd.read_excel(bru / "planilhas" / "Previsao de Vendas_2026.xlsx", sheet_name="PREVISAO", header=2)
    d["07_Pessoas e Previsao.xlsx"] = {
        "Ponto": q(f"""SELECT CAST(DATA AS TIMESTAMP), TURNO, CELULA, QUADRO_PREVISTO, PRESENTES, HORAS_NORMAIS, HORAS_EXTRAS
                       FROM read_parquet('{exp}/mao_de_obra.parquet') WHERE DATA BETWEEN {ini} AND {fim} ORDER BY 1, 2, 3"""),
        "Previsão": [["2026-10", int(r["Cód. produto"]), int(r["2026-10"])] for _, r in prev.iterrows()]}
    return d


FICHA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Ficha de turno</title>
<style>
@page{size:A4 landscape;margin:9mm}
*{box-sizing:border-box}body{font:11px/1.3 "Segoe UI",Arial,sans-serif;color:#111;margin:0}
h1{font-size:17px;margin:0}h2{font-size:12px;margin:9px 0 3px;text-transform:none}
.topo{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid #111;padding-bottom:5px}
.campos{display:flex;gap:14px}.campos div{border-bottom:1px solid #111;min-width:92px;padding:0 2px 1px;font-size:10px;color:#555}
.campos div b{display:block;height:17px}
table{width:100%;border-collapse:collapse;table-layout:fixed}
th,td{border:1px solid #111;padding:2px 4px;height:21px;text-align:left;font-weight:normal}
th{background:#e8e8e8;font-weight:600;font-size:10px;height:auto}
.duas{display:grid;grid-template-columns:1.25fr 1fr;gap:12px}
.leg{font-size:9.5px;columns:4;margin:3px 0 0;padding:0;list-style:none}.leg b{display:inline-block;width:16px}
.nota{font-size:9.5px;color:#444;margin-top:5px}
</style></head><body>
<div class="topo"><div><h1>Ficha de turno: produção, paradas e refugo</h1><div class="nota" style="margin:0">Uma ficha por máquina e por turno. Entregar ao líder no fim do turno.</div></div>
<div class="campos"><div>Data<b></b></div><div>Turno (1, 2, 3)<b></b></div><div>Máquina<b></b></div><div>Operador / matrícula<b></b></div><div>Líder<b></b></div></div></div>
<h2>1. Produção: uma linha por ordem que rodou no turno</h2>
<table><tr><th style="width:8%">OP</th><th style="width:20%">Produto</th><th>Hora início</th><th>Hora fim</th><th>Contador inicial</th><th>Contador final</th><th>Peças produzidas</th><th>Refugo</th><th>Retrabalho</th></tr>
__PROD__</table>
<div class="duas"><div><h2>2. Paradas: toda vez que a máquina parar, inclusive refeição e troca</h2>
<table><tr><th style="width:16%">Hora início</th><th style="width:16%">Duração (min)</th><th style="width:12%">Motivo (nº)</th><th>Observação</th></tr>
__PAR__</table></div>
<div><h2>3. Refugo por defeito</h2>
<table><tr><th style="width:18%">OP</th><th>Defeito</th><th style="width:22%">Quantidade</th></tr>
__REF__</table></div></div>
<h2>Motivos de parada</h2><ul class="leg">__MOT__</ul>
<div class="nota">Peças produzidas = contador final menos contador inicial (boas + refugo). A soma do refugo por defeito deve fechar com o refugo da produção.
Parada que não for anotada não some: aparece no painel como máquina lenta e esconde o motivo verdadeiro.</div>
</body></html>"""


def ficha():
    linha = lambda n, cols: "".join("<tr>" + "<td></td>" * cols + "</tr>" for _ in range(n))
    html = (FICHA.replace("__PROD__", linha(4, 9)).replace("__PAR__", linha(9, 4)).replace("__REF__", linha(9, 3))
            .replace("__MOT__", "".join(f"<li><b>{i}</b>{m}</li>" for i, m in enumerate(MOTIVOS, 1))))
    (AQUI / "imprimir").mkdir(exist_ok=True)
    (AQUI / "imprimir" / "ficha_de_turno.html").write_text(html, encoding="utf-8", newline="\n")


def main():
    for pasta in ("modelos", "exemplo_preenchido"):
        (AQUI / pasta).mkdir(exist_ok=True)
    for arquivo in PLANILHAS:
        montar(AQUI / "modelos" / arquivo, arquivo)
    dados = exemplo()
    for arquivo in PLANILHAS:
        montar(AQUI / "exemplo_preenchido" / arquivo, arquivo, dados[arquivo])
        print(arquivo, {aba: len(l) for aba, l in dados[arquivo].items()})
    ficha()


if __name__ == "__main__":
    main()
