-- =========================================================
-- TRUSTED - ESTOQUE DIARIO (materia-prima, acabado e em processo)
--
-- Materia-prima e produto acabado vem do fechamento diario do ERP.
-- O estoque em processo (WIP) o ERP nao guarda: e calculado aqui.
--
-- Regra do WIP: no fim de cada dia, pecas boas ja produzidas de ordens
-- que comecaram e ainda nao encerraram, valorizadas ao custo padrao.
--
-- RUPTURA: materia-prima fechou o dia com saldo zero.
-- =========================================================

CREATE OR REPLACE TABLE estoque_dia AS

SELECT
    CAST(e.DATA AS DATE) AS DATA,
    e.CODIGO_ITEM,
    COALESCE(m.DESCRICAO, p.PRODUTO) AS ITEM,
    e.TIPO_ITEM,
    p.CELULA,
    e.SALDO,
    e.SALDO * e.CUSTO_UNITARIO AS VALOR,
    e.TIPO_ITEM = 'Matéria-prima' AND e.SALDO <= 0 AS RUPTURA
FROM erp_estoque_diario e
LEFT JOIN erp_materiais m ON m.CODIGO_MATERIAL = e.CODIGO_ITEM
LEFT JOIN dim_produto p ON CAST(p.CODIGO_PRODUTO AS VARCHAR) = e.CODIGO_ITEM

UNION ALL

SELECT
    c.DATA,
    CAST(o.CODIGO_PRODUTO AS VARCHAR) AS CODIGO_ITEM,
    ANY_VALUE(p.PRODUTO) AS ITEM,
    'Em processo' AS TIPO_ITEM,
    ANY_VALUE(p.CELULA) AS CELULA,
    SUM(a.QTD_BOA) AS SALDO,
    SUM(a.QTD_BOA * p.CUSTO_PADRAO) AS VALOR,
    FALSE AS RUPTURA
FROM dim_calendario c
JOIN ordem o ON CAST(o.INICIO_REAL AS DATE) <= c.DATA AND (o.FIM_REAL IS NULL OR CAST(o.FIM_REAL AS DATE) > c.DATA)
JOIN apontamento a ON a.NUMERO_OP = o.NUMERO_OP AND a.DATA <= c.DATA
JOIN dim_produto p ON p.CODIGO_PRODUTO = o.CODIGO_PRODUTO
GROUP BY c.DATA, o.CODIGO_PRODUTO;
