-- =========================================================
-- ANALYTICS - CONFIABILIDADE POR MAQUINA E MES (MTBF / MTTR)
--
--   MTBF (h)   = horas produzindo / numero de quebras
--   MTTR (min) = minutos em quebra / numero de quebras
--
-- Quebra = parada da categoria 'Manutenção corretiva'.
-- Mes sem quebra fica com MTBF e MTTR nulos (nao ha o que dividir).
-- =========================================================

CREATE OR REPLACE TABLE an_confiabilidade AS

SELECT
    STRFTIME(DATA, '%Y-%m') AS ANO_MES,
    CODIGO_RECURSO,
    SUM(TEMPO_PRODUZINDO_MIN) / 60.0 AS HORAS_PRODUZINDO,
    SUM(N_QUEBRAS) AS N_QUEBRAS,
    SUM(QUEBRA_MIN) / 60.0 AS HORAS_QUEBRA,
    SUM(TEMPO_PRODUZINDO_MIN) / 60.0 / NULLIF(SUM(N_QUEBRAS), 0) AS MTBF_H,
    SUM(QUEBRA_MIN) / NULLIF(SUM(N_QUEBRAS), 0) AS MTTR_MIN
FROM producao_turno
GROUP BY 1, 2
ORDER BY 1, 2;
