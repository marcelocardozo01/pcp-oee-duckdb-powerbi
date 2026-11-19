-- =========================================================
-- TRUSTED - PRODUCAO POR TURNO (base do OEE)
--
-- Uma linha por dia, turno e maquina, juntando o coletor (producao)
-- com o diario de bordo (paradas). Todos os tempos em minutos.
--
--   TEMPO_TURNO_MIN          480
--   PARADA_PLANEJADA_MIN     refeicao, preventiva, sem programa, DDS
--   TEMPO_PROGRAMADO_MIN     turno - paradas planejadas
--   PARADA_NAO_PLANEJADA_MIN tudo o que nao e planejado (inclui setup)
--   TEMPO_PRODUZINDO_MIN     tempo de maquina rodando, do coletor
--   TEMPO_NAO_APONTADO_MIN   programado - produzindo - paradas: tempo
--                            que ninguem explicou (cai na disponibilidade)
--   TEMPO_TEORICO_MIN        tempo das pecas no ciclo padrao
--
--   Disponibilidade = TEMPO_PRODUZINDO / TEMPO_PROGRAMADO
--   Performance     = TEMPO_TEORICO    / TEMPO_PRODUZINDO
--   Qualidade       = QTD_BOA          / QTD_PRODUZIDA
--   OEE             = Disponibilidade x Performance x Qualidade
--
-- As colunas sao somaveis: o OEE de qualquer recorte sai da soma dos
-- tempos e das quantidades, nunca da media dos percentuais.
-- =========================================================

CREATE OR REPLACE TABLE producao_turno AS

WITH ap AS (
    SELECT DATA, TURNO, CODIGO_RECURSO,
           SUM(TEMPO_PRODUCAO_MIN) AS TEMPO_PRODUZINDO_MIN,
           SUM(TEMPO_TEORICO_MIN) AS TEMPO_TEORICO_MIN,
           SUM(QTD_PRODUZIDA) AS QTD_PRODUZIDA,
           SUM(QTD_BOA) AS QTD_BOA,
           SUM(QTD_REFUGO) AS QTD_REFUGO,
           SUM(QTD_RETRABALHO) AS QTD_RETRABALHO,
           SUM(KG_TRANSFORMADO) AS KG_TRANSFORMADO,
           SUM(CUSTO_REFUGO) AS CUSTO_REFUGO
    FROM apontamento
    GROUP BY ALL
),

pa AS (
    SELECT DATA, TURNO, CODIGO_RECURSO,
           COALESCE(SUM(DURACAO_MIN) FILTER (WHERE PLANEJADA), 0) AS PARADA_PLANEJADA_MIN,
           COALESCE(SUM(DURACAO_MIN) FILTER (WHERE NOT PLANEJADA), 0) AS PARADA_NAO_PLANEJADA_MIN,
           COALESCE(SUM(DURACAO_MIN) FILTER (WHERE EH_SETUP), 0) AS SETUP_MIN,
           COALESCE(SUM(DURACAO_MIN) FILTER (WHERE CODIGO_MOTIVO = 'S01'), 0) AS SETUP_TROCA_MIN,
           COALESCE(SUM(DURACAO_MIN) FILTER (WHERE EH_QUEBRA), 0) AS QUEBRA_MIN,
           COUNT(*) FILTER (WHERE EH_QUEBRA) AS N_QUEBRAS,
           COUNT(*) FILTER (WHERE NOT PLANEJADA) AS N_PARADAS
    FROM parada
    GROUP BY ALL
),

chaves AS (
    SELECT DATA, TURNO, CODIGO_RECURSO FROM ap
    UNION
    SELECT DATA, TURNO, CODIGO_RECURSO FROM pa
)

SELECT
    k.DATA,
    k.TURNO,
    k.CODIGO_RECURSO,
    480.0 AS TEMPO_TURNO_MIN,
    COALESCE(pa.PARADA_PLANEJADA_MIN, 0) AS PARADA_PLANEJADA_MIN,
    480.0 - COALESCE(pa.PARADA_PLANEJADA_MIN, 0) AS TEMPO_PROGRAMADO_MIN,
    COALESCE(pa.PARADA_NAO_PLANEJADA_MIN, 0) AS PARADA_NAO_PLANEJADA_MIN,
    COALESCE(pa.SETUP_MIN, 0) AS SETUP_MIN,
    COALESCE(pa.SETUP_TROCA_MIN, 0) AS SETUP_TROCA_MIN,
    COALESCE(pa.QUEBRA_MIN, 0) AS QUEBRA_MIN,
    COALESCE(pa.N_QUEBRAS, 0) AS N_QUEBRAS,
    COALESCE(pa.N_PARADAS, 0) AS N_PARADAS,
    COALESCE(ap.TEMPO_PRODUZINDO_MIN, 0) AS TEMPO_PRODUZINDO_MIN,
    GREATEST(480.0 - COALESCE(pa.PARADA_PLANEJADA_MIN, 0) - COALESCE(pa.PARADA_NAO_PLANEJADA_MIN, 0)
             - COALESCE(ap.TEMPO_PRODUZINDO_MIN, 0), 0) AS TEMPO_NAO_APONTADO_MIN,
    COALESCE(ap.TEMPO_TEORICO_MIN, 0) AS TEMPO_TEORICO_MIN,
    COALESCE(ap.QTD_PRODUZIDA, 0) AS QTD_PRODUZIDA,
    COALESCE(ap.QTD_BOA, 0) AS QTD_BOA,
    COALESCE(ap.QTD_REFUGO, 0) AS QTD_REFUGO,
    COALESCE(ap.QTD_RETRABALHO, 0) AS QTD_RETRABALHO,
    COALESCE(ap.KG_TRANSFORMADO, 0) AS KG_TRANSFORMADO,
    COALESCE(ap.CUSTO_REFUGO, 0) AS CUSTO_REFUGO,
    COALESCE(pa.PARADA_NAO_PLANEJADA_MIN, 0) / 60.0 * r.CUSTO_HORA AS CUSTO_PARADA
FROM chaves k
JOIN dim_recurso r USING (CODIGO_RECURSO)
LEFT JOIN ap USING (DATA, TURNO, CODIGO_RECURSO)
LEFT JOIN pa USING (DATA, TURNO, CODIGO_RECURSO);
