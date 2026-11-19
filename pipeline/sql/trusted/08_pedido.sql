-- =========================================================
-- TRUSTED - PEDIDOS DE VENDA (base do OTIF)
--
-- A fabrica produz contra pedido: cada pedido tem uma ordem.
--
-- Regras:
--   NO_PRAZO (On Time) : entregue ate a data prometida
--   COMPLETO (In Full) : quantidade entregue >= quantidade pedida
--   OTIF               : no prazo E completo
--   Pedido com data prometida vencida e sem entrega conta como
--   fora do prazo e incompleto (nao some do indicador).
--   So entram pedidos com data prometida ate a data de corte
--   (ultimo dia com apontamento).
-- =========================================================

CREATE OR REPLACE TABLE pedido AS

WITH corte AS (SELECT MAX(DATA) AS DT FROM apontamento)

SELECT
    p.NUMERO_PEDIDO,
    p.CODIGO_CLIENTE,
    c.RAZAO_SOCIAL AS CLIENTE,
    p.CODIGO_PRODUTO,
    o.NUMERO_OP,
    o.CODIGO_RECURSO,
    p.QTD_PEDIDA,
    COALESCE(p.QTD_ENTREGUE, 0) AS QTD_ENTREGUE,
    CAST(p.DATA_PEDIDO AS DATE) AS DATA_PEDIDO,
    CAST(p.DATA_PROMETIDA AS DATE) AS DATA_PROMETIDA,
    CAST(p.DATA_ENTREGA AS DATE) AS DATA_ENTREGA,
    p.DATA_ENTREGA IS NOT NULL AS ENTREGUE,
    COALESCE(p.DATA_ENTREGA <= p.DATA_PROMETIDA, FALSE) AS NO_PRAZO,
    COALESCE(p.QTD_ENTREGUE >= p.QTD_PEDIDA, FALSE) AS COMPLETO,
    COALESCE(p.DATA_ENTREGA <= p.DATA_PROMETIDA AND p.QTD_ENTREGUE >= p.QTD_PEDIDA, FALSE) AS OTIF,
    GREATEST(DATE_DIFF('day', CAST(p.DATA_PROMETIDA AS DATE), COALESCE(CAST(p.DATA_ENTREGA AS DATE), (SELECT DT FROM corte))), 0) AS DIAS_ATRASO,
    DATE_DIFF('day', CAST(p.DATA_PEDIDO AS DATE), CAST(p.DATA_ENTREGA AS DATE)) AS LEAD_TIME_PEDIDO_DIAS,
    COALESCE(p.QTD_ENTREGUE, 0) * pr.PRECO_VENDA AS VALOR_ENTREGUE
FROM erp_pedidos_venda p
JOIN erp_clientes c USING (CODIGO_CLIENTE)
JOIN dim_produto pr USING (CODIGO_PRODUTO)
LEFT JOIN erp_ordens_producao o USING (NUMERO_PEDIDO)
WHERE CAST(p.DATA_PROMETIDA AS DATE) <= (SELECT DT FROM corte);
