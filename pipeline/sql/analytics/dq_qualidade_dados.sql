-- =========================================================
-- ANALYTICS - QUALIDADE DOS DADOS DA COLETA
--
-- Antes de confiar no indicador, medir a coleta. Cada linha e uma
-- checagem com quantos registros caíram nela e o que o pipeline fez.
--
--   1 Linhas repetidas no arquivo do coletor      -> removidas
--   2 Motivos de parada sem de-para               -> viram 'Não classificado'
--   3 Refugo da planilha diferente do coletor     -> vale o coletor (rateio)
--   4 Turnos com mais de 30 min sem apontamento   -> contam contra a disponibilidade
--   5 Turnos com producao e sem nenhuma parada    -> suspeita de diario nao preenchido
--   6 Ordens encerradas abaixo de 98% do planejado-> viram pedido incompleto
-- =========================================================

CREATE OR REPLACE TABLE dq_qualidade_dados AS

WITH ref AS (
    SELECT c.DATA, c.TURNO, c.CODIGO_RECURSO, c.NUMERO_OP, c.Q AS Q_COLETOR, p.Q AS Q_PLANILHA
    FROM (SELECT DATA, TURNO, CODIGO_RECURSO, NUMERO_OP, SUM(QTD_REFUGO) AS Q FROM apontamento GROUP BY ALL HAVING SUM(QTD_REFUGO) > 0) c
    LEFT JOIN (SELECT CAST(DATA AS DATE) AS DATA, TURNO, RECURSO AS CODIGO_RECURSO, OP AS NUMERO_OP, SUM(QUANTIDADE) AS Q
               FROM diario_refugo GROUP BY ALL) p USING (DATA, TURNO, CODIGO_RECURSO, NUMERO_OP)
)

SELECT 1 AS ORDEM, 'Linhas repetidas no arquivo do coletor' AS CHECAGEM, 'Coletor (MES)' AS ORIGEM,
       (SELECT COUNT(*) FROM mes_apontamento) - (SELECT COUNT(*) FROM apontamento) AS REGISTROS,
       (SELECT COUNT(*) FROM mes_apontamento) AS TOTAL,
       'Mesma máquina, ordem e início: fica uma linha só' AS TRATAMENTO
UNION ALL
SELECT 2, 'Motivos de parada sem de-para', 'Diário de bordo',
       (SELECT COUNT(*) FROM parada WHERE CODIGO_MOTIVO = 'N/C'), (SELECT COUNT(*) FROM parada),
       'Classificados como não planejados até entrarem no de-para'
UNION ALL
SELECT 3, 'Refugo da planilha diferente do coletor', 'Diário de bordo x coletor',
       (SELECT COUNT(*) FROM ref WHERE Q_PLANILHA IS NULL OR Q_PLANILHA <> Q_COLETOR), (SELECT COUNT(*) FROM ref),
       'Quantidade do coletor; a planilha só define a proporção por defeito'
UNION ALL
SELECT 4, 'Turnos com mais de 30 min sem apontamento', 'Coletor x diário de bordo',
       (SELECT COUNT(*) FROM producao_turno WHERE TEMPO_NAO_APONTADO_MIN > 30), (SELECT COUNT(*) FROM producao_turno),
       'O tempo sem explicação conta contra a disponibilidade'
UNION ALL
SELECT 5, 'Turnos com produção e sem nenhuma parada registrada', 'Diário de bordo',
       (SELECT COUNT(*) FROM producao_turno WHERE QTD_PRODUZIDA > 0 AND PARADA_PLANEJADA_MIN + PARADA_NAO_PLANEJADA_MIN = 0),
       (SELECT COUNT(*) FROM producao_turno),
       'Sinaliza diário não preenchido'
UNION ALL
SELECT 6, 'Ordens encerradas abaixo de 98% do planejado', 'ERP x coletor',
       (SELECT COUNT(*) FROM ordem WHERE STATUS = 'Encerrada' AND QTD_BOA < 0.98 * QTD_PLANEJADA),
       (SELECT COUNT(*) FROM ordem WHERE STATUS = 'Encerrada'),
       'O pedido correspondente fica incompleto no OTIF'
ORDER BY 1;
