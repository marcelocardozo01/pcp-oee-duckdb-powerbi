-- =========================================================
-- TRUSTED - CONSUMO DE MATERIA-PRIMA: REAL x TEORICO
--
-- Uma linha por dia, ordem e material.
--
--   QTD_REAL    : requisitado no almoxarifado (ERP)
--   QTD_TEORICA : pecas BOAS do dia x quantidade por peca da estrutura
--
--   Rendimento = teorico / real
--
-- O que separa os dois e material que virou refugo, borra de
-- partida, purga de troca de cor e perda de processo.
-- CONTA_RENDIMENTO marca resinas e masterbatch (em kg): rotulo e
-- tinta ficam fora do rendimento para nao misturar unidades.
-- =========================================================

CREATE OR REPLACE TABLE consumo_material AS

WITH boas AS (
    SELECT DATA, NUMERO_OP, ANY_VALUE(CODIGO_PRODUTO) AS CODIGO_PRODUTO, ANY_VALUE(CODIGO_RECURSO) AS CODIGO_RECURSO,
           SUM(QTD_BOA) AS QTD_BOA
    FROM apontamento
    GROUP BY 1, 2
)

SELECT
    CAST(r.DATA AS DATE) AS DATA,
    r.NUMERO_OP,
    b.CODIGO_PRODUTO,
    b.CODIGO_RECURSO,
    r.CODIGO_MATERIAL,
    m.DESCRICAO AS MATERIAL,
    m.UNIDADE,
    r.QUANTIDADE AS QTD_REAL,
    b.QTD_BOA * e.QTD_POR_PECA AS QTD_TEORICA,
    r.QUANTIDADE * m.CUSTO_UNITARIO AS VALOR_REAL,
    b.QTD_BOA * e.QTD_POR_PECA * m.CUSTO_UNITARIO AS VALOR_TEORICO,
    m.UNIDADE = 'kg' AND r.CODIGO_MATERIAL <> 'MP-TINTA' AS CONTA_RENDIMENTO
FROM erp_requisicoes_material r
JOIN erp_materiais m USING (CODIGO_MATERIAL)
JOIN boas b ON b.DATA = CAST(r.DATA AS DATE) AND b.NUMERO_OP = r.NUMERO_OP
JOIN erp_estrutura e ON e.CODIGO_PRODUTO = b.CODIGO_PRODUTO AND e.CODIGO_MATERIAL = r.CODIGO_MATERIAL;
