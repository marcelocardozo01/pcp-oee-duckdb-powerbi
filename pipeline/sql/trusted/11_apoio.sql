-- =========================================================
-- TRUSTED - PLANILHAS DE APOIO (pessoas, inventario, previsao)
--
--   mao_de_obra : ponto por dia, turno e celula
--                 Absenteismo = ausentes / quadro previsto
--                 Horas extras = extras / (normais + extras)
--
--   inventario  : conferencia ciclica x saldo do sistema
--                 ACURADO = diferenca de ate 2% do saldo
--
--   previsao    : previsao do comercial x pedidos, por produto e mes
--                 (mes da data prometida)
--                 Acuracia = 1 - soma |previsto - pedido| / soma pedido
-- =========================================================

CREATE OR REPLACE TABLE mao_de_obra AS
SELECT
    DATA,
    TURNO,
    CELULA,
    QUADRO_PREVISTO,
    PRESENTES,
    QUADRO_PREVISTO - PRESENTES AS AUSENTES,
    HORAS_NORMAIS,
    HORAS_EXTRAS,
    HORAS_NORMAIS + HORAS_EXTRAS AS HORAS_TRABALHADAS
FROM ponto_horas;

CREATE OR REPLACE TABLE inventario AS
SELECT
    CAST(DATA AS DATE) AS DATA,
    CODIGO_ITEM,
    TIPO_ITEM,
    SALDO_SISTEMA,
    QTD_CONTADA,
    QTD_CONTADA - SALDO_SISTEMA AS DIFERENCA,
    (QTD_CONTADA - SALDO_SISTEMA) / NULLIF(SALDO_SISTEMA, 0) AS DIFERENCA_PCT,
    ABS(QTD_CONTADA - SALDO_SISTEMA) <= 0.02 * SALDO_SISTEMA AS ACURADO,
    CONTADOR
FROM inventario_ciclico;

CREATE OR REPLACE TABLE previsao AS
WITH pedidos AS (
    SELECT STRFTIME(DATA_PROMETIDA, '%Y-%m') AS ANO_MES, CODIGO_PRODUTO, SUM(QTD_PEDIDA) AS QTD_PEDIDA
    FROM erp_pedidos_venda
    GROUP BY 1, 2
)
SELECT
    v.ANO_MES,
    v.CODIGO_PRODUTO,
    v.QTD_PREVISTA,
    COALESCE(p.QTD_PEDIDA, 0) AS QTD_PEDIDA,
    ABS(v.QTD_PREVISTA - COALESCE(p.QTD_PEDIDA, 0)) AS ERRO_ABSOLUTO
FROM previsao_vendas v
LEFT JOIN pedidos p USING (ANO_MES, CODIGO_PRODUTO)
WHERE v.ANO_MES <= (SELECT STRFTIME(MAX(DATA), '%Y-%m') FROM apontamento);
