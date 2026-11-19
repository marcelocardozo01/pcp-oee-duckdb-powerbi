"""Gera o painel HTML de performance do PCP (painel_html/saida/index.html).

Le os mesmos .parquet que o Power BI (dados/exports), resume em um JSON e
injeta no modelo (painel_html/modelo.html). O resultado e um unico arquivo
estatico, sem servidor e sem dependencia externa: abre no navegador, no
celular ou anexado num e-mail.

Uso: python painel_html/gerar_painel.py
"""
import json
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[1]
EXP = RAIZ / "dados" / "exports"
AQUI = Path(__file__).resolve().parent


def main():
    con = duckdb.connect()
    for f in EXP.glob("*.parquet"):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")

    def q(sql):
        cur = con.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def r(v, n=2):
        return None if v is None else round(float(v), n)

    d = {}
    d["meses"] = q("SELECT ANO_MES AS id, ANY_VALUE(MES_ROTULO) AS rotulo FROM dim_calendario GROUP BY 1 ORDER BY 1")
    d["corte"] = q("SELECT STRFTIME(MAX(DATA), '%d/%m/%Y') AS c FROM dim_calendario")[0]["c"]
    d["maquinas"] = q("SELECT CODIGO_RECURSO AS id, RECURSO AS nome, CELULA AS cel FROM dim_recurso ORDER BY ORDEM_CELULA, 1")
    d["catalogo"] = q("""SELECT CODIGO AS id, FAMILIA AS fam, INDICADOR AS nome, UNIDADE AS un, SENTIDO AS sentido,
                                META AS meta, FORMULA AS formula, FONTE AS fonte FROM dim_indicador""")
    # indicadores: kpi[mes][escopo][codigo] = [valor, status]
    kpi = {}
    for x in q("SELECT ANO_MES, ESCOPO, CODIGO, VALOR, STATUS FROM an_kpi_mensal"):
        kpi.setdefault(x["ANO_MES"], {}).setdefault(x["ESCOPO"], {})[x["CODIGO"]] = [r(x["VALOR"], 5), x["STATUS"]]
    d["kpi"] = kpi

    base = """SUM(TEMPO_PROGRAMADO_MIN) AS prog, SUM(TEMPO_PRODUZINDO_MIN) AS run, SUM(TEMPO_TEORICO_MIN) AS teo,
              SUM(QTD_PRODUZIDA) AS tot, SUM(QTD_BOA) AS boa, SUM(QTD_REFUGO) AS ref"""
    arred = lambda rows, chaves: [{k: (v if k in chaves else r(v, 1)) for k, v in x.items()} for x in rows]
    d["maq_mes"] = arred(q(f"""SELECT STRFTIME(DATA, '%Y-%m') AS mes, CODIGO_RECURSO AS maq, {base},
                                      SUM(PARADA_NAO_PLANEJADA_MIN) AS np, SUM(SETUP_MIN) AS setup, SUM(QUEBRA_MIN) AS quebra,
                                      SUM(N_QUEBRAS) AS nq, SUM(CUSTO_REFUGO) AS cref
                               FROM producao_turno GROUP BY 1, 2 ORDER BY 1, 2"""), ("mes", "maq"))
    d["dia"] = arred(q(f"""SELECT STRFTIME(t.DATA, '%Y-%m-%d') AS dia, r.CELULA AS cel, {base}
                           FROM producao_turno t JOIN dim_recurso r USING (CODIGO_RECURSO) GROUP BY 1, 2 ORDER BY 1, 2"""), ("dia", "cel"))
    d["turno"] = arred(q(f"""SELECT STRFTIME(t.DATA, '%Y-%m') AS mes, r.CELULA AS cel, t.TURNO AS turno, {base}
                             FROM producao_turno t JOIN dim_recurso r USING (CODIGO_RECURSO) GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"""),
                       ("mes", "cel", "turno"))
    d["perdas"] = arred(q("""SELECT ANO_MES AS mes, CODIGO_RECURSO AS maq, ORDEM AS o, HORAS AS h FROM an_perdas_tempo ORDER BY 1, 2, 3"""),
                        ("mes", "maq", "o"))
    d["etapas"] = q("SELECT DISTINCT ORDEM AS o, ETAPA AS nome, TIPO AS tipo FROM an_perdas_tempo ORDER BY 1")
    d["paradas"] = arred(q("""SELECT STRFTIME(p.DATA, '%Y-%m') AS mes, r.CELULA AS cel, p.MOTIVO AS motivo, p.CATEGORIA AS cat,
                                     SUM(p.DURACAO_MIN) / 60.0 AS h, COUNT(*) AS n
                              FROM parada p JOIN dim_recurso r USING (CODIGO_RECURSO) WHERE NOT p.PLANEJADA
                              GROUP BY 1, 2, 3, 4 ORDER BY 1, 2"""), ("mes", "cel", "motivo", "cat", "n"))
    d["defeitos"] = arred(q("""SELECT STRFTIME(f.DATA, '%Y-%m') AS mes, r.CELULA AS cel, f.DEFEITO AS defeito,
                                      SUM(f.QTD_REFUGO) AS qtd, SUM(f.CUSTO_REFUGO) AS custo
                               FROM refugo_defeito f JOIN dim_recurso r USING (CODIGO_RECURSO) GROUP BY 1, 2, 3 ORDER BY 1, 2"""),
                          ("mes", "cel", "defeito"))
    d["produtos"] = arred(q("""SELECT STRFTIME(a.DATA, '%Y-%m') AS mes, p.CELULA AS cel, p.PRODUTO AS produto,
                                      SUM(a.QTD_PRODUZIDA) AS tot, SUM(a.QTD_BOA) AS boa, SUM(a.QTD_REFUGO) AS ref,
                                      SUM(a.TEMPO_PRODUCAO_MIN) AS run, SUM(a.TEMPO_TEORICO_MIN) AS teo, SUM(a.CUSTO_REFUGO) AS cref
                               FROM apontamento a JOIN dim_produto p USING (CODIGO_PRODUTO) GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"""),
                          ("mes", "cel", "produto"))
    d["prog_dia"] = arred(q("""SELECT STRFTIME(p.DATA, '%Y-%m-%d') AS dia, r.CELULA AS cel,
                                      SUM(p.TEMPO_PADRAO_PROGRAMADO_MIN) / 60.0 AS hp,
                                      SUM(p.QTD_REAL * d.CICLO_PADRAO_S / d.CAVIDADES) / 3600.0 AS hr,
                                      SUM(p.QTD_ADERENTE * d.CICLO_PADRAO_S / d.CAVIDADES) / 3600.0 AS ha
                               FROM programa_dia p JOIN dim_recurso r USING (CODIGO_RECURSO) JOIN dim_produto d USING (CODIGO_PRODUTO)
                               GROUP BY 1, 2 ORDER BY 1, 2"""), ("dia", "cel"))
    d["prog_maq"] = arred(q("""SELECT STRFTIME(DATA, '%Y-%m') AS mes, CODIGO_RECURSO AS maq,
                                      SUM(QTD_PROGRAMADA) AS qp, SUM(QTD_REAL) AS qr, SUM(QTD_ADERENTE) AS qa
                               FROM programa_dia GROUP BY 1, 2 ORDER BY 1, 2"""), ("mes", "maq"))
    d["clientes"] = q("""SELECT STRFTIME(p.DATA_PROMETIDA, '%Y-%m') AS mes, d.CELULA AS cel, p.CLIENTE AS cliente,
                                COUNT(*) AS n, COUNT(*) FILTER (WHERE p.OTIF) AS otif,
                                COUNT(*) FILTER (WHERE p.NO_PRAZO) AS ot, COUNT(*) FILTER (WHERE p.COMPLETO) AS inf
                         FROM pedido p JOIN dim_produto d USING (CODIGO_PRODUTO) GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""")
    d["atrasados"] = q("""SELECT STRFTIME(p.DATA_PROMETIDA, '%Y-%m') AS mes, d.CELULA AS cel, p.NUMERO_PEDIDO AS pedido,
                                 p.CLIENTE AS cliente, d.PRODUTO AS produto, p.CODIGO_RECURSO AS maq,
                                 STRFTIME(p.DATA_PROMETIDA, '%d/%m') AS prometida,
                                 COALESCE(STRFTIME(p.DATA_ENTREGA, '%d/%m'), 'em aberto') AS entrega,
                                 p.DIAS_ATRASO AS dias, p.QTD_PEDIDA AS pedida, p.QTD_ENTREGUE AS entregue
                          FROM pedido p JOIN dim_produto d USING (CODIGO_PRODUTO)
                          WHERE NOT p.OTIF ORDER BY p.DIAS_ATRASO DESC, p.QTD_ENTREGUE * 1.0 / p.QTD_PEDIDA""")
    d["estoque"] = arred(q("""SELECT STRFTIME(DATA, '%Y-%m-%d') AS dia,
                                     SUM(VALOR) FILTER (WHERE TIPO_ITEM = 'Matéria-prima') AS mp,
                                     SUM(VALOR) FILTER (WHERE TIPO_ITEM = 'Produto acabado') AS pa,
                                     COALESCE(SUM(VALOR) FILTER (WHERE TIPO_ITEM = 'Em processo'), 0) AS wip
                              FROM estoque_dia GROUP BY 1 ORDER BY 1"""), ("dia",))
    d["cobertura"] = arred(q("""WITH s AS (SELECT STRFTIME(DATA, '%Y-%m') AS mes, CODIGO_ITEM, ANY_VALUE(ITEM) AS item,
                                                AVG(SALDO) AS saldo, COUNT(*) AS dias, COUNT(*) FILTER (WHERE RUPTURA) AS rupt
                                           FROM estoque_dia WHERE TIPO_ITEM = 'Matéria-prima' GROUP BY 1, 2),
                                     c AS (SELECT STRFTIME(DATA, '%Y-%m') AS mes, CODIGO_MATERIAL AS CODIGO_ITEM, SUM(QTD_REAL) AS cons
                                           FROM consumo_material GROUP BY 1, 2)
                                SELECT s.mes, s.item, s.saldo / NULLIF(c.cons / s.dias, 0) AS dias, s.rupt
                                FROM s LEFT JOIN c USING (mes, CODIGO_ITEM) ORDER BY 1, 2"""), ("mes", "item", "rupt"))
    d["previsao"] = q("""SELECT v.ANO_MES AS mes, p.CELULA AS cel, p.PRODUTO AS produto, v.QTD_PREVISTA AS prev, v.QTD_PEDIDA AS ped
                         FROM previsao v JOIN dim_produto p USING (CODIGO_PRODUTO) ORDER BY 1, 2, 3""")
    d["pessoas"] = arred(q("""SELECT STRFTIME(DATA, '%Y-%m') AS mes, CELULA AS cel, TURNO AS turno, SUM(HORAS_TRABALHADAS) AS hh,
                                     SUM(HORAS_EXTRAS) AS he, SUM(AUSENTES) AS aus, SUM(QUADRO_PREVISTO) AS quadro
                              FROM mao_de_obra GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"""), ("mes", "cel", "turno", "aus", "quadro"))
    d["dq"] = q("SELECT CHECAGEM AS checagem, ORIGEM AS origem, REGISTROS AS n, TOTAL AS total, TRATAMENTO AS tratamento FROM dq_qualidade_dados ORDER BY ORDEM")
    d["volumes"] = q("""SELECT (SELECT COUNT(*) FROM apontamento) AS apontamentos, (SELECT COUNT(*) FROM parada) AS paradas,
                               (SELECT COUNT(*) FROM ordem) AS ordens, (SELECT COUNT(*) FROM pedido) AS pedidos,
                               (SELECT COUNT(*) FROM refugo_defeito) AS refugos, (SELECT COUNT(*) FROM programa_dia) AS programa""")[0]

    modelo = (AQUI / "modelo.html").read_text(encoding="utf-8")
    dados = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    saida = AQUI / "saida"
    saida.mkdir(exist_ok=True)
    (saida / "index.html").write_text(modelo.replace("/*__DADOS__*/null", dados), encoding="utf-8", newline="\n")
    print(f"painel_html/saida/index.html: {(saida / 'index.html').stat().st_size / 1024:,.0f} KB")


if __name__ == "__main__":
    main()
