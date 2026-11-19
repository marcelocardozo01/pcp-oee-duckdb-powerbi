-- =========================================================
-- TRUSTED - REFUGO POR DEFEITO
--
-- Duas fontes contam o refugo: o contador da maquina (coletor) e a
-- planilha do lider, que separa por defeito. Elas nem sempre fecham.
--
-- Regra: a QUANTIDADE oficial e a do coletor. A planilha entra so com a
-- PROPORCAO de cada defeito, aplicada sobre o refugo do coletor
-- (rateio). Assim o Pareto de defeitos soma exatamente o refugo do OEE.
--
-- Turno com refugo no coletor e sem linha na planilha: 'Não informado'.
-- =========================================================

CREATE OR REPLACE TABLE refugo_defeito AS

WITH linhas AS (
    SELECT CAST(DATA AS DATE) AS DATA, TURNO, RECURSO AS CODIGO_RECURSO, OP AS NUMERO_OP, TRIM(DEFEITO) AS DEFEITO,
           SUM(QUANTIDADE) AS QTD
    FROM diario_refugo
    GROUP BY 1, 2, 3, 4, 5
),

planilha AS (
    SELECT *, SUM(QTD) OVER (PARTITION BY DATA, TURNO, CODIGO_RECURSO, NUMERO_OP) AS QTD_TOTAL
    FROM linhas
),

coletor AS (
    SELECT DATA, TURNO, CODIGO_RECURSO, NUMERO_OP, ANY_VALUE(CODIGO_PRODUTO) AS CODIGO_PRODUTO,
           SUM(QTD_REFUGO) AS QTD_REFUGO
    FROM apontamento
    GROUP BY ALL
    HAVING SUM(QTD_REFUGO) > 0
)

SELECT
    c.DATA,
    c.TURNO,
    c.CODIGO_RECURSO,
    c.NUMERO_OP,
    c.CODIGO_PRODUTO,
    COALESCE(p.DEFEITO, 'Não informado') AS DEFEITO,
    c.QTD_REFUGO * COALESCE(p.QTD / p.QTD_TOTAL, 1) AS QTD_REFUGO,
    c.QTD_REFUGO * COALESCE(p.QTD / p.QTD_TOTAL, 1) * pr.CUSTO_PADRAO AS CUSTO_REFUGO
FROM coletor c
LEFT JOIN planilha p USING (DATA, TURNO, CODIGO_RECURSO, NUMERO_OP)
JOIN dim_produto pr USING (CODIGO_PRODUTO);
