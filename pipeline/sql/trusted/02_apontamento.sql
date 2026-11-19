-- =========================================================
-- TRUSTED - APONTAMENTO DE PRODUCAO (coletor / MES)
--
-- Uma linha por maquina, turno e ordem.
--
-- Regras:
--   1. O coletor as vezes reenvia o arquivo do dia com linhas repetidas.
--      Mesma maquina + ordem + inicio = mesma linha: fica uma so.
--   2. Peca boa = produzida - refugo. Retrabalho continua boa,
--      mas nao conta como aprovada de primeira (FPY).
--   3. Tempo teorico = pecas produzidas x ciclo padrao / cavidades.
--      E o tempo que a maquina levaria no ritmo do roteiro.
--   4. O contador da maquina e a quantidade oficial de producao e refugo.
-- =========================================================

CREATE OR REPLACE TABLE apontamento AS

WITH unico AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY RECURSO, OP, INICIO ORDER BY filename) AS N
    FROM mes_apontamento
)

SELECT
    a.DATA,
    a.TURNO,
    a.RECURSO AS CODIGO_RECURSO,
    a.OP AS NUMERO_OP,
    a.PRODUTO AS CODIGO_PRODUTO,
    a.OPERADOR,
    a.INICIO,
    a.FIM,
    a.TEMPO_PRODUCAO_MIN,
    a.CICLOS,
    a.QTD_PRODUZIDA,
    a.QTD_REFUGO,
    a.QTD_RETRABALHO,
    a.QTD_PRODUZIDA - a.QTD_REFUGO AS QTD_BOA,
    a.QTD_PRODUZIDA * r.CICLO_PADRAO_S / r.CAVIDADES / 60.0 AS TEMPO_TEORICO_MIN,
    CASE WHEN p.CELULA <> 'Decoração' THEN (a.QTD_PRODUZIDA - a.QTD_REFUGO) * p.PESO_G / 1000.0 ELSE 0 END AS KG_TRANSFORMADO,
    a.QTD_REFUGO * p.CUSTO_PADRAO AS CUSTO_REFUGO
FROM unico a
JOIN erp_roteiros r ON r.CODIGO_PRODUTO = a.PRODUTO AND r.CODIGO_RECURSO = a.RECURSO
JOIN erp_produtos p ON p.CODIGO_PRODUTO = a.PRODUTO
WHERE a.N = 1;
