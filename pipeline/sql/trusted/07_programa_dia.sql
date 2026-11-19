-- =========================================================
-- TRUSTED - PROGRAMA x REALIZADO POR DIA
--
-- Uma linha por dia, maquina e ordem: o que o PCP programou
-- (planilha semanal) contra as pecas boas do coletor.
--
--   QTD_ADERENTE = menor entre programado e realizado
--
--   Aderencia ao volume = soma do realizado / soma do programado
--   Aderencia ao mix    = soma do aderente  / soma do programado
--
-- A diferenca entre as duas e o que a fabrica produziu fora do
-- combinado: bateu o volume, mas com a ordem errada ou no dia errado.
-- Producao sem programa entra com QTD_PROGRAMADA = 0.
-- =========================================================

CREATE OR REPLACE TABLE programa_dia AS

WITH prog AS (
    SELECT CAST(DATA AS DATE) AS DATA, RECURSO AS CODIGO_RECURSO, OP AS NUMERO_OP,
           ANY_VALUE(CODIGO_PRODUTO) AS CODIGO_PRODUTO, SUM(QTD_PROGRAMADA) AS QTD_PROGRAMADA
    FROM programa_semanal
    GROUP BY 1, 2, 3
),

real AS (
    SELECT DATA, CODIGO_RECURSO, NUMERO_OP, ANY_VALUE(CODIGO_PRODUTO) AS CODIGO_PRODUTO, SUM(QTD_BOA) AS QTD_REAL
    FROM apontamento
    GROUP BY 1, 2, 3
)

SELECT
    COALESCE(p.DATA, r.DATA) AS DATA,
    COALESCE(p.CODIGO_RECURSO, r.CODIGO_RECURSO) AS CODIGO_RECURSO,
    COALESCE(p.NUMERO_OP, r.NUMERO_OP) AS NUMERO_OP,
    COALESCE(p.CODIGO_PRODUTO, r.CODIGO_PRODUTO) AS CODIGO_PRODUTO,
    COALESCE(p.QTD_PROGRAMADA, 0) AS QTD_PROGRAMADA,
    COALESCE(r.QTD_REAL, 0) AS QTD_REAL,
    LEAST(COALESCE(p.QTD_PROGRAMADA, 0), COALESCE(r.QTD_REAL, 0)) AS QTD_ADERENTE,
    COALESCE(p.QTD_PROGRAMADA, 0) * d.CICLO_PADRAO_S / d.CAVIDADES / 60.0 AS TEMPO_PADRAO_PROGRAMADO_MIN
FROM prog p
FULL JOIN real r ON r.DATA = p.DATA AND r.CODIGO_RECURSO = p.CODIGO_RECURSO AND r.NUMERO_OP = p.NUMERO_OP
JOIN dim_produto d ON d.CODIGO_PRODUTO = COALESCE(p.CODIGO_PRODUTO, r.CODIGO_PRODUTO);
