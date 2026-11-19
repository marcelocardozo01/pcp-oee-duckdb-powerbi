-- =========================================================
-- TRUSTED - DIMENSOES
--
--   dim_calendario    : um dia por linha, do primeiro ao ultimo apontamento
--   dim_recurso       : maquinas, celula e custo hora
--   dim_produto       : produto + ciclo padrao e cavidades do roteiro
--   dim_motivo_parada : motivos oficiais (config/motivos_parada.csv)
--   dim_turno         : 1, 2 e 3
--
-- Dia util = segunda a sexta, sem feriados (config/feriados.csv).
-- =========================================================

CREATE OR REPLACE TABLE dim_calendario AS
SELECT
    CAST(d AS DATE) AS DATA,
    STRFTIME(d, '%Y-%m') AS ANO_MES,
    YEAR(d) AS ANO,
    MONTH(d) AS MES,
    ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'][MONTH(d)] || '/' || STRFTIME(d, '%y') AS MES_ROTULO,
    STRFTIME(d, '%G-S%V') AS SEMANA,
    ISODOW(d) AS NUM_DIA_SEMANA,
    ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'][ISODOW(d)] AS DIA_SEMANA,
    ISODOW(d) <= 5 AND CAST(d AS DATE) NOT IN (SELECT CAST(DATA AS DATE) FROM cfg_feriados) AS DIA_UTIL
FROM RANGE((SELECT MIN(DATA) FROM mes_apontamento),
           (SELECT MAX(DATA) FROM mes_apontamento) + INTERVAL 1 DAY, INTERVAL 1 DAY) t(d);

CREATE OR REPLACE TABLE dim_recurso AS
SELECT
    CODIGO_RECURSO,
    DESCRICAO AS RECURSO,
    CELULA,
    CASE CELULA WHEN 'Injeção' THEN 1 WHEN 'Sopro' THEN 2 ELSE 3 END AS ORDEM_CELULA,
    CUSTO_HORA
FROM erp_recursos;

CREATE OR REPLACE TABLE dim_produto AS
SELECT
    p.CODIGO_PRODUTO,
    p.DESCRICAO AS PRODUTO,
    p.FAMILIA,
    p.CELULA,
    p.PESO_G,
    p.CUSTO_PADRAO,
    p.PRECO_VENDA,
    r.CICLO_PADRAO_S,
    r.CAVIDADES
FROM erp_produtos p
JOIN (SELECT CODIGO_PRODUTO, MIN(CICLO_PADRAO_S) AS CICLO_PADRAO_S, MIN(CAVIDADES) AS CAVIDADES
      FROM erp_roteiros GROUP BY 1) r USING (CODIGO_PRODUTO);

CREATE OR REPLACE TABLE dim_motivo_parada AS
SELECT
    CODIGO_MOTIVO,
    MOTIVO,
    CATEGORIA,
    PLANEJADA = 'S' AS PLANEJADA
FROM cfg_motivos_parada;

CREATE OR REPLACE TABLE dim_turno AS
SELECT * FROM (VALUES (1, '1º turno (06h-14h)'), (2, '2º turno (14h-22h)'), (3, '3º turno (22h-06h)')) t(TURNO, TURNO_NOME);
