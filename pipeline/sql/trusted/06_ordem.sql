-- =========================================================
-- TRUSTED - ORDENS DE PRODUCAO
--
-- Cabecalho da ordem (ERP) + o que aconteceu de verdade (coletor)
-- + a posicao dela no programa semanal do PCP.
--
-- Regras:
--   1. Inicio real = primeiro apontamento. Fim real = encerramento no ERP.
--   2. NO_PRAZO_PROGRAMA: encerrou ate o dia de fim programado.
--   3. NA_SEQUENCIA: nenhuma ordem que vinha DEPOIS dela no programa da
--      mesma maquina e semana comecou ANTES. Quem fura a fila marca a
--      ordem ultrapassada como fora de sequencia.
--   4. TEVE_SETUP: o produto mudou em relacao a ordem anterior da maquina.
--   5. Lead time de producao = dias corridos entre inicio e fim real.
-- =========================================================

CREATE OR REPLACE TABLE ordem AS

WITH real AS (
    SELECT NUMERO_OP, MIN(INICIO) AS INICIO_REAL, MAX(FIM) AS ULTIMO_APONTAMENTO,
           SUM(QTD_BOA) AS QTD_BOA, SUM(QTD_PRODUZIDA) AS QTD_PRODUZIDA, SUM(QTD_REFUGO) AS QTD_REFUGO
    FROM apontamento
    GROUP BY 1
),

prog AS (
    SELECT OP AS NUMERO_OP, MIN(SEMANA) AS SEMANA_PROGRAMA, ARG_MIN(SEQUENCIA, SEMANA) AS SEQUENCIA_PROGRAMA
    FROM programa_semanal
    GROUP BY 1
),

base AS (
    SELECT
        o.NUMERO_OP,
        o.CODIGO_PRODUTO,
        o.CODIGO_RECURSO,
        o.NUMERO_PEDIDO,
        o.QTD_PLANEJADA,
        CAST(o.DATA_ABERTURA AS DATE) AS DATA_ABERTURA,
        CAST(o.INICIO_PROGRAMADO AS TIMESTAMP) AS INICIO_PROGRAMADO,
        CAST(o.FIM_PROGRAMADO AS TIMESTAMP) AS FIM_PROGRAMADO,
        CAST(o.DATA_NECESSIDADE AS DATE) AS DATA_NECESSIDADE,
        o.STATUS,
        r.INICIO_REAL,
        CAST(o.DATA_ENCERRAMENTO AS TIMESTAMP) AS FIM_REAL,
        COALESCE(r.QTD_BOA, 0) AS QTD_BOA,
        COALESCE(r.QTD_PRODUZIDA, 0) AS QTD_PRODUZIDA,
        COALESCE(r.QTD_REFUGO, 0) AS QTD_REFUGO,
        p.SEMANA_PROGRAMA,
        p.SEQUENCIA_PROGRAMA
    FROM erp_ordens_producao o
    LEFT JOIN real r USING (NUMERO_OP)
    LEFT JOIN prog p USING (NUMERO_OP)
)

SELECT
    b.*,
    DATE_DIFF('minute', b.INICIO_REAL, b.FIM_REAL) / 1440.0 AS LEAD_TIME_PRODUCAO_DIAS,
    DATE_DIFF('day', CAST(b.FIM_PROGRAMADO AS DATE), CAST(b.FIM_REAL AS DATE)) AS DIAS_DESVIO_FIM,
    CAST(b.FIM_REAL AS DATE) <= CAST(b.FIM_PROGRAMADO AS DATE) AS NO_PRAZO_PROGRAMA,
    CASE WHEN b.INICIO_REAL IS NULL THEN NULL
         ELSE NOT EXISTS (SELECT 1 FROM base x
                          WHERE x.CODIGO_RECURSO = b.CODIGO_RECURSO AND x.SEMANA_PROGRAMA = b.SEMANA_PROGRAMA
                            AND x.SEQUENCIA_PROGRAMA > b.SEQUENCIA_PROGRAMA AND x.INICIO_REAL < b.INICIO_REAL) END AS NA_SEQUENCIA,
    CASE WHEN b.INICIO_REAL IS NULL THEN NULL
         ELSE COALESCE(LAG(b.CODIGO_PRODUTO) OVER (PARTITION BY b.CODIGO_RECURSO ORDER BY b.INICIO_REAL) <> b.CODIGO_PRODUTO, FALSE) END AS TEVE_SETUP
FROM base b;
