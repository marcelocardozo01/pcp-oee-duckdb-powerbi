-- =========================================================
-- ANALYTICS - PARA ONDE VAI O TEMPO DA MAQUINA
--
-- Decompoe as 24 horas de calendario de cada maquina, por mes, do
-- tempo total ate o tempo que realmente gerou peca boa. E a "cascata"
-- do OEE/TEEP: cada degrau e uma perda com dono diferente.
--
--   1 Sem turno programado   calendario - turnos trabalhados     (decisao da empresa)
--   2 Parada planejada       refeicao, preventiva, sem programa  (PCP / manutencao)
--   3 Setup                  troca de molde, ferramenta e cor    (PCP / producao)
--   4 Quebra                 manutencao corretiva                (manutencao)
--   5 Outras paradas         processo, material, pessoas...      (producao / suprimentos)
--   6 Tempo nao apontado     ninguem explicou                    (disciplina de apontamento)
--   7 Ritmo abaixo do padrao produzindo - teorico                (processo)
--   8 Refugo                 tempo teorico das pecas refugadas   (qualidade)
--   9 Tempo produtivo        tempo teorico das pecas boas
--
-- A soma dos 9 degraus e o tempo de calendario.
-- =========================================================

CREATE OR REPLACE TABLE an_perdas_tempo AS

WITH base AS (
    SELECT
        STRFTIME(DATA, '%Y-%m') AS ANO_MES,
        CODIGO_RECURSO,
        SUM(TEMPO_TURNO_MIN) AS TURNO,
        SUM(PARADA_PLANEJADA_MIN) AS PLANEJADA,
        SUM(SETUP_MIN) AS SETUP,
        SUM(QUEBRA_MIN) AS QUEBRA,
        SUM(PARADA_NAO_PLANEJADA_MIN - SETUP_MIN - QUEBRA_MIN) AS OUTRAS,
        SUM(TEMPO_NAO_APONTADO_MIN) AS NAO_APONTADO,
        SUM(TEMPO_PRODUZINDO_MIN - TEMPO_TEORICO_MIN) AS RITMO,
        SUM(TEMPO_TEORICO_MIN * QTD_REFUGO / NULLIF(QTD_PRODUZIDA, 0)) AS REFUGO,
        SUM(TEMPO_TEORICO_MIN * QTD_BOA / NULLIF(QTD_PRODUZIDA, 0)) AS PRODUTIVO
    FROM producao_turno
    GROUP BY 1, 2
),

cal AS (SELECT ANO_MES, COUNT(*) * 1440.0 AS CALENDARIO FROM dim_calendario GROUP BY 1),

degraus AS (
    SELECT b.ANO_MES, b.CODIGO_RECURSO, d.ORDEM, d.ETAPA, d.TIPO,
           CASE d.ORDEM WHEN 1 THEN c.CALENDARIO - b.TURNO WHEN 2 THEN b.PLANEJADA WHEN 3 THEN b.SETUP
                        WHEN 4 THEN b.QUEBRA WHEN 5 THEN b.OUTRAS WHEN 6 THEN b.NAO_APONTADO
                        WHEN 7 THEN b.RITMO WHEN 8 THEN b.REFUGO ELSE b.PRODUTIVO END AS MINUTOS
    FROM base b
    JOIN cal c USING (ANO_MES)
    CROSS JOIN (VALUES (1, 'Sem turno programado', 'Fora da carga'), (2, 'Parada planejada', 'Fora da carga'),
                       (3, 'Setup', 'Disponibilidade'), (4, 'Quebra', 'Disponibilidade'),
                       (5, 'Outras paradas', 'Disponibilidade'), (6, 'Tempo não apontado', 'Disponibilidade'),
                       (7, 'Ritmo abaixo do padrão', 'Performance'), (8, 'Refugo', 'Qualidade'),
                       (9, 'Tempo produtivo', 'Produtivo')) d(ORDEM, ETAPA, TIPO)
)

SELECT ANO_MES, CODIGO_RECURSO, ORDEM, ETAPA, TIPO, GREATEST(COALESCE(MINUTOS, 0), 0) / 60.0 AS HORAS
FROM degraus
ORDER BY 1, 2, 3;
