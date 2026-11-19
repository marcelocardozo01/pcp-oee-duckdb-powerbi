"""Etapa 3 - exporta a camada de consumo: cada tabela vira um .parquet em dados/exports.

O Power BI le estes arquivos (conector Parquet) pelo parametro PastaExports,
e o painel HTML (painel_html/gerar_painel.py) le os mesmos arquivos.
Uma fonte so para os dois paineis: o numero nao pode divergir.
"""
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
BANCO = RAIZ / "dados" / "pcp.duckdb"
DESTINO = RAIZ / "dados" / "exports"

TABELAS = [
    # dimensoes
    "dim_calendario", "dim_recurso", "dim_produto", "dim_motivo_parada", "dim_turno", "dim_indicador",
    # fatos
    "producao_turno", "apontamento", "parada", "refugo_defeito", "ordem", "programa_dia", "pedido",
    "estoque_dia", "consumo_material", "mao_de_obra", "inventario", "previsao",
    # analytics
    "an_kpi_mensal", "an_perdas_tempo", "an_confiabilidade", "dq_qualidade_dados",
]


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(BANCO))
    con.execute("CREATE OR REPLACE VIEW dim_indicador AS SELECT * FROM cfg_indicadores")
    for t in TABELAS:
        arq = (DESTINO / f"{t}.parquet").as_posix()
        con.execute(f"COPY (SELECT * FROM {t}) TO '{arq}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        print(f"{t}: {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:,} linhas")
    con.close()


if __name__ == "__main__":
    main()
