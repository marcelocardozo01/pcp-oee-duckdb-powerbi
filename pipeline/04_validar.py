"""Etapa 4 - validacao: o pipeline so termina "verde" se os numeros fecham.

Confere, na camada exportada:
  1. todo indicador do catalogo (config/indicadores.csv) tem valor em todos os meses, para a fabrica
  2. OEE = Disponibilidade x Performance x Qualidade
  3. a cascata de perdas soma o tempo de calendario de cada maquina
  4. o refugo por defeito soma o refugo do coletor
  5. producao + paradas cabem no turno de 480 minutos
  6. percentuais entre 0 e 1 onde isso e obrigatorio

Sai com codigo 1 se alguma checagem falhar.
"""
import sys
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
EXP = RAIZ / "dados" / "exports"


def main():
    con = duckdb.connect()
    for f in EXP.glob("*.parquet"):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")
    q = lambda sql: con.execute(sql).fetchall()
    falhas = []

    def checar(nome, ok, detalhe=""):
        print(f"[{'ok' if ok else 'FALHOU'}] {nome}{' - ' + detalhe if detalhe else ''}")
        if not ok:
            falhas.append(nome)

    n_ind = q("SELECT COUNT(*) FROM dim_indicador")[0][0]
    n_mes = q("SELECT COUNT(DISTINCT ANO_MES) FROM dim_calendario")[0][0]
    faltam = q("""SELECT i.CODIGO, m.ANO_MES FROM dim_indicador i CROSS JOIN (SELECT DISTINCT ANO_MES FROM dim_calendario) m
                  LEFT JOIN an_kpi_mensal k ON k.CODIGO = i.CODIGO AND k.ANO_MES = m.ANO_MES AND k.ESCOPO = 'Fábrica'
                  WHERE k.VALOR IS NULL""")
    checar(f"cobertura do catalogo: {n_ind} indicadores x {n_mes} meses", not faltam, str(faltam[:5]) if faltam else "")

    dif = q("""SELECT MAX(ABS(o.VALOR - d.VALOR * p.VALOR * u.VALOR))
               FROM an_kpi_mensal o
               JOIN an_kpi_mensal d ON d.CODIGO = 'EFI02' AND d.ANO_MES = o.ANO_MES AND d.ESCOPO = o.ESCOPO
               JOIN an_kpi_mensal p ON p.CODIGO = 'EFI03' AND p.ANO_MES = o.ANO_MES AND p.ESCOPO = o.ESCOPO
               JOIN an_kpi_mensal u ON u.CODIGO = 'EFI04' AND u.ANO_MES = o.ANO_MES AND u.ESCOPO = o.ESCOPO
               WHERE o.CODIGO = 'EFI01'""")[0][0]
    checar("OEE = disponibilidade x performance x qualidade", dif < 1e-9, f"maior diferenca {dif:.1e}")

    dif = q("""SELECT MAX(ABS(h.HORAS - c.HORAS)) FROM
               (SELECT ANO_MES, CODIGO_RECURSO, SUM(HORAS) AS HORAS FROM an_perdas_tempo GROUP BY 1, 2) h
               JOIN (SELECT ANO_MES, COUNT(*) * 24.0 AS HORAS FROM dim_calendario GROUP BY 1) c USING (ANO_MES)""")[0][0]
    checar("cascata de perdas soma o tempo de calendario", dif < 1.0, f"maior diferenca {dif:.2f} h por maquina-mes")

    a, b = q("SELECT (SELECT SUM(QTD_REFUGO) FROM refugo_defeito), (SELECT SUM(QTD_REFUGO) FROM apontamento)")[0]
    checar("refugo por defeito = refugo do coletor", abs(a - b) < 1, f"{a:,.0f} x {b:,.0f}")

    n = q("""SELECT COUNT(*) FROM producao_turno
             WHERE PARADA_PLANEJADA_MIN + PARADA_NAO_PLANEJADA_MIN + TEMPO_PRODUZINDO_MIN > 480 + 5""")[0][0]
    checar("producao + paradas cabem no turno de 480 min", n == 0, f"{n} turnos estouram")

    n = q("""SELECT COUNT(*) FROM an_kpi_mensal
             WHERE CODIGO IN ('EFI01','EFI02','EFI03','EFI04','EFI05','EFI06','PLA02','PLA03','PLA04',
                              'ENT01','ENT02','ENT03','QUA01','QUA02','QUA03','MAT03','MAT05')
               AND (VALOR < 0 OR VALOR > 1)""")[0][0]
    checar("percentuais entre 0 e 100%", n == 0, f"{n} fora da faixa")

    if falhas:
        sys.exit(f"\n{len(falhas)} checagem(ns) falharam.")
    print("\nTodas as checagens passaram.")


if __name__ == "__main__":
    main()
