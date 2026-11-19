-- =========================================================
-- TRUSTED - PARADAS DE MAQUINA (diario de bordo)
--
-- O lider digita o motivo como quer: "Troca de molde", "TROCA MOLDE",
-- "setup"... O texto e normalizado (sem acento, maiusculo, sem espaco
-- nas pontas) e traduzido pelo de-para config/depara_motivos_parada.csv.
--
-- Regras:
--   1. Texto sem de-para vira 'N/C - Nao classificado' e conta como
--      parada NAO planejada, para nao melhorar o indicador por engano.
--   2. Planejada (refeicao, preventiva, sem programa, DDS) sai do tempo
--      programado. Todo o resto, inclusive setup, derruba a disponibilidade.
--   3. Quebra = categoria 'Manutenção corretiva' (base do MTBF e do MTTR).
--   4. No 3o turno, hora menor que 22h pertence ao dia seguinte.
-- =========================================================

CREATE OR REPLACE TABLE parada AS

SELECT
    CAST(d.DATA AS DATE) AS DATA,
    d.TURNO,
    d.RECURSO AS CODIGO_RECURSO,
    CAST(d.DATA AS DATE) + CAST(d.HORA_INICIO || ':00' AS TIME)
        + CASE WHEN d.TURNO = 3 AND CAST(d.HORA_INICIO || ':00' AS TIME) < TIME '22:00:00'
               THEN INTERVAL 1 DAY ELSE INTERVAL 0 DAY END AS INICIO,
    CAST(d.DURACAO_MIN AS DOUBLE) AS DURACAO_MIN,
    TRIM(d.MOTIVO_DIGITADO) AS MOTIVO_DIGITADO,
    m.CODIGO_MOTIVO,
    m.MOTIVO,
    m.CATEGORIA,
    m.PLANEJADA,
    m.CATEGORIA = 'Setup' AS EH_SETUP,
    m.CATEGORIA = 'Manutenção corretiva' AS EH_QUEBRA,
    d.LIDER
FROM diario_parada d
LEFT JOIN cfg_depara_motivos_parada dp
       ON dp.TEXTO_PLANILHA = STRIP_ACCENTS(UPPER(TRIM(d.MOTIVO_DIGITADO)))
JOIN dim_motivo_parada m ON m.CODIGO_MOTIVO = COALESCE(dp.CODIGO_MOTIVO, 'N/C');
