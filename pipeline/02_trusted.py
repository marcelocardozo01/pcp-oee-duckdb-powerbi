"""Etapa 2 - camadas trusted e analytics: roda os SQL em ordem no DuckDB.

  pipeline/sql/trusted/*.sql    (ordem do prefixo numerico) - uma regra de negocio por arquivo
  pipeline/sql/analytics/*.sql  (leem a trusted) - indicadores, perdas, confiabilidade, qualidade dos dados
"""
import re
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
BANCO = RAIZ / "dados" / "pcp.duckdb"
SQL = Path(__file__).resolve().parent / "sql"


def main():
    con = duckdb.connect(str(BANCO))
    for arquivo in sorted((SQL / "trusted").glob("*.sql")) + sorted((SQL / "analytics").glob("*.sql")):
        texto = arquivo.read_text(encoding="utf-8")
        con.execute(texto)
        criadas = re.findall(r"CREATE OR REPLACE TABLE (\w+)", texto)
        resumo = ", ".join(f"{t} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:,}" for t in criadas)
        print(f"{arquivo.parent.name}/{arquivo.name}: {resumo}")
    con.close()


if __name__ == "__main__":
    main()
