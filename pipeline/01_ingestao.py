"""Etapa 1 - ingestao: carrega os arquivos brutos (dados/brutos) no DuckDB (dados/pcp.duckdb).

Cada origem chega num formato diferente, como no dia a dia de um PCP:

  erp/          parquet (na empresa real: extracao do ERP via ODBC)
  mes/          1 CSV por dia do coletor de chao de fabrica (; e virgula decimal)
  diario_bordo/ 1 planilha por mes, abas Paradas e Refugo, digitadas pelo lider
  programa/     1 planilha por semana com o programa do PCP
  planilhas/    ponto (CSV), inventario ciclico e previsao de vendas (Excel)

As planilhas sao lidas pelo NOME das colunas: a linha de cabecalho e procurada,
entao titulo, observacoes e colunas novas nao quebram a carga.

Tabelas criadas (camada raw): erp_*, mes_apontamento, diario_parada, diario_refugo,
programa_semanal, ponto_horas, inventario_ciclico, previsao_vendas e as de config.
"""
import re
from pathlib import Path

import duckdb
import openpyxl
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
BRUTOS = RAIZ / "dados" / "brutos"
CONFIG = RAIZ / "config"
BANCO = RAIZ / "dados" / "pcp.duckdb"

ERP = ["recursos", "produtos", "roteiros", "estrutura", "materiais", "clientes",
       "ordens_producao", "pedidos_venda", "requisicoes_material", "estoque_diario"]


def ler_aba(arquivo, aba, colunas):
    """Le uma aba procurando a linha de cabecalho que contem todas as `colunas`."""
    wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
    try:
        linhas = list(wb[aba].iter_rows(values_only=True))
    finally:
        wb.close()
    limpa = lambda r: [str(x).strip() if x is not None else "" for x in r]
    h = next((i for i, r in enumerate(linhas[:20]) if set(colunas) <= set(limpa(r))), None)
    if h is None:
        raise ValueError(f"{Path(arquivo).name} / {aba}: cabecalho {colunas} nao encontrado")
    cab = limpa(linhas[h])
    dados = [r for r in linhas[h + 1:] if r and any(x is not None for x in r)]
    df = pd.DataFrame(dados, columns=cab)
    df = df[[c for c in cab if c]]
    df["ARQUIVO"] = Path(arquivo).name
    return df


def criar(con, nome, df):
    con.register("df_tmp", df)
    con.execute(f"CREATE OR REPLACE TABLE {nome} AS SELECT * FROM df_tmp")
    con.unregister("df_tmp")


def main():
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(BANCO))

    # ERP
    for t in ERP:
        con.execute(f"CREATE OR REPLACE TABLE erp_{t} AS SELECT * FROM read_parquet('{(BRUTOS / 'erp' / (t + '.parquet')).as_posix()}')")

    # Coletor (MES): todos os CSV do dia, guardando o nome do arquivo de origem
    con.execute(f"""
        CREATE OR REPLACE TABLE mes_apontamento AS
        SELECT * FROM read_csv('{(BRUTOS / 'mes').as_posix()}/apontamento_*.csv', delim=';', header=true,
                               decimal_separator=',', dateformat='%d/%m/%Y', timestampformat='%d/%m/%Y %H:%M',
                               filename=true,
                               types={{'DATA': 'DATE', 'INICIO': 'TIMESTAMP', 'FIM': 'TIMESTAMP', 'TEMPO_PRODUCAO_MIN': 'DOUBLE'}})""")

    # Diario de bordo (paradas e refugo por defeito)
    par, ref = [], []
    for f in sorted((BRUTOS / "diario_bordo").glob("Diario de Bordo_*.xlsx")):
        par.append(ler_aba(f, "Paradas", ["Data", "Turno", "Máquina", "Hora início", "Duração (min)", "Motivo"]))
        ref.append(ler_aba(f, "Refugo", ["Data", "Turno", "Máquina", "OP", "Defeito", "Quantidade"]))
    par = pd.concat(par, ignore_index=True).rename(columns={
        "Data": "DATA", "Turno": "TURNO", "Máquina": "RECURSO", "Hora início": "HORA_INICIO",
        "Duração (min)": "DURACAO_MIN", "Motivo": "MOTIVO_DIGITADO", "OP": "OP", "Líder": "LIDER"})
    ref = pd.concat(ref, ignore_index=True).rename(columns={
        "Data": "DATA", "Turno": "TURNO", "Máquina": "RECURSO", "Defeito": "DEFEITO", "Quantidade": "QUANTIDADE"})
    par["OP"] = pd.to_numeric(par["OP"], errors="coerce").astype("Int64")
    criar(con, "diario_parada", par)
    criar(con, "diario_refugo", ref)

    # Programa semanal do PCP
    prog = []
    for f in sorted((BRUTOS / "programa").glob("Programa Semanal_*.xlsx")):
        df = ler_aba(f, "PROGRAMA", ["Data", "Máquina", "Seq.", "OP", "Cód. produto", "Qtd. programada"])
        df["SEMANA"] = re.search(r"_(\d{4}-S\d{2})", f.name).group(1)
        prog.append(df)
    prog = pd.concat(prog, ignore_index=True).rename(columns={
        "Data": "DATA", "Máquina": "RECURSO", "Seq.": "SEQUENCIA", "Cód. produto": "CODIGO_PRODUTO",
        "Produto": "PRODUTO", "Qtd. programada": "QTD_PROGRAMADA"})
    criar(con, "programa_semanal", prog)

    # Ponto (RH)
    con.execute(f"""
        CREATE OR REPLACE TABLE ponto_horas AS
        SELECT * FROM read_csv('{(BRUTOS / 'planilhas' / 'ponto_horas_trabalhadas.csv').as_posix()}', delim=';', header=true,
                               decimal_separator=',', dateformat='%d/%m/%Y',
                               types={{'DATA': 'DATE', 'HORAS_NORMAIS': 'DOUBLE', 'HORAS_EXTRAS': 'DOUBLE'}})""")

    # Inventario ciclico
    inv = ler_aba(BRUTOS / "planilhas" / "Inventario Ciclico_2026.xlsx", "CONTAGENS",
                  ["Data", "Código do item", "Saldo sistema", "Qtd. contada"]).rename(columns={
        "Data": "DATA", "Código do item": "CODIGO_ITEM", "Tipo": "TIPO_ITEM", "Saldo sistema": "SALDO_SISTEMA",
        "Qtd. contada": "QTD_CONTADA", "Contador": "CONTADOR"})
    inv["CODIGO_ITEM"] = inv["CODIGO_ITEM"].astype(str)
    criar(con, "inventario_ciclico", inv)

    # Previsao de vendas: meses nas colunas -> uma linha por produto e mes
    prev = ler_aba(BRUTOS / "planilhas" / "Previsao de Vendas_2026.xlsx", "PREVISAO", ["Cód. produto", "Produto"])
    meses = [c for c in prev.columns if re.fullmatch(r"\d{4}-\d{2}", c)]
    prev = prev.melt(id_vars=["Cód. produto"], value_vars=meses, var_name="ANO_MES", value_name="QTD_PREVISTA")
    criar(con, "previsao_vendas", prev.rename(columns={"Cód. produto": "CODIGO_PRODUTO"}))

    # Config
    for nome in ["motivos_parada", "depara_motivos_parada", "indicadores", "feriados"]:
        con.execute(f"""CREATE OR REPLACE TABLE cfg_{nome} AS
                        SELECT * FROM read_csv('{(CONFIG / (nome + '.csv')).as_posix()}', delim=';', header=true, quote='')""")

    for t in ["erp_ordens_producao", "erp_pedidos_venda", "mes_apontamento", "diario_parada", "diario_refugo",
              "programa_semanal", "ponto_horas", "inventario_ciclico", "previsao_vendas"]:
        print(f"{t}: {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:,} linhas")
    con.close()


if __name__ == "__main__":
    main()
