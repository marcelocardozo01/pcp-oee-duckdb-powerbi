-- =========================================================
-- ANALYTICS - INDICADORES DO PCP POR MES
--
-- Uma linha por mes, escopo (Fabrica ou celula) e indicador.
-- E a tabela que alimenta o painel HTML e a pagina de indicadores
-- do Power BI. O catalogo (nome, unidade, sentido, meta, formula e
-- fonte) fica em config/indicadores.csv.
--
-- Cada bloco abaixo soma os numeradores e denominadores de uma
-- origem. O indicador so e dividido no fim, entao o valor da fabrica
-- nunca e a media das celulas.
--
-- Indicadores que so existem para a fabrica toda (estoque de materia-
-- prima, inventario) ficam sem linha por celula.
--
-- STATUS: 'No alvo', 'Atenção' (ate 10% da meta) ou 'Crítico'.
-- Percentuais ficam como fracao (0,75 = 75%).
-- =========================================================

CREATE OR REPLACE TABLE an_kpi_mensal AS

WITH
corte AS (SELECT MAX(DATA) AS DT FROM apontamento),

meses AS (
    SELECT ANO_MES, ANY_VALUE(MES_ROTULO) AS MES_ROTULO, MAX(DATA) AS FIM_MES, COUNT(*) AS DIAS
    FROM dim_calendario GROUP BY 1
),

escopos AS (
    SELECT 'Fábrica' AS ESCOPO, 0 AS ORDEM_ESCOPO
    UNION ALL
    SELECT DISTINCT CELULA, ORDEM_CELULA FROM dim_recurso
),

grade AS (SELECT m.*, e.ESCOPO, e.ORDEM_ESCOPO FROM meses m CROSS JOIN escopos e),

-- producao, tempos e qualidade (coletor + diario de bordo)
prod AS (
    SELECT STRFTIME(t.DATA, '%Y-%m') AS ANO_MES, e.ESCOPO,
           SUM(t.TEMPO_PROGRAMADO_MIN) AS PROG, SUM(t.TEMPO_PRODUZINDO_MIN) AS RUN, SUM(t.TEMPO_TEORICO_MIN) AS TEO,
           SUM(t.QTD_PRODUZIDA) AS TOT, SUM(t.QTD_BOA) AS BOA, SUM(t.QTD_REFUGO) AS REF, SUM(t.QTD_RETRABALHO) AS RET,
           SUM(t.PARADA_NAO_PLANEJADA_MIN) AS NP, SUM(t.SETUP_MIN) AS SETUP, SUM(t.SETUP_TROCA_MIN) AS SETUP_TROCA,
           SUM(t.N_QUEBRAS) AS NQ, SUM(t.QUEBRA_MIN) AS MQ,
           SUM(t.KG_TRANSFORMADO) AS KG, SUM(t.CUSTO_REFUGO) AS CR, SUM(t.CUSTO_PARADA) AS CP
    FROM producao_turno t
    JOIN dim_recurso r USING (CODIGO_RECURSO)
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = r.CELULA
    GROUP BY 1, 2
),

-- tempo de calendario: 24 h por dia e por maquina
cal AS (
    SELECT c.ANO_MES, e.ESCOPO, COUNT(*) * 1440.0 AS CAL
    FROM dim_calendario c
    CROSS JOIN dim_recurso r
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = r.CELULA
    GROUP BY 1, 2
),

-- programa x realizado
prog AS (
    SELECT STRFTIME(p.DATA, '%Y-%m') AS ANO_MES, e.ESCOPO,
           SUM(p.QTD_PROGRAMADA) AS QP, SUM(p.QTD_REAL) AS QR, SUM(p.QTD_ADERENTE) AS QA,
           SUM(p.TEMPO_PADRAO_PROGRAMADO_MIN) AS TP
    FROM programa_dia p
    JOIN dim_recurso r USING (CODIGO_RECURSO)
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = r.CELULA
    GROUP BY 1, 2
),

-- ordens: sequencia e setup (mes do inicio real)
ord_ini AS (
    SELECT STRFTIME(o.INICIO_REAL, '%Y-%m') AS ANO_MES, e.ESCOPO,
           COUNT(*) AS N_INI, COUNT(*) FILTER (WHERE o.NA_SEQUENCIA) AS N_SEQ, COUNT(*) FILTER (WHERE o.TEVE_SETUP) AS N_SETUP
    FROM ordem o
    JOIN dim_recurso r USING (CODIGO_RECURSO)
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = r.CELULA
    WHERE o.INICIO_REAL IS NOT NULL
    GROUP BY 1, 2
),

-- ordens: pontualidade (mes do fim programado, ate o corte)
ord_prog AS (
    SELECT STRFTIME(o.FIM_PROGRAMADO, '%Y-%m') AS ANO_MES, e.ESCOPO,
           COUNT(*) AS N_PROG, COUNT(*) FILTER (WHERE o.NO_PRAZO_PROGRAMA) AS N_PRAZO
    FROM ordem o
    JOIN dim_recurso r USING (CODIGO_RECURSO)
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = r.CELULA
    WHERE CAST(o.FIM_PROGRAMADO AS DATE) <= (SELECT DT FROM corte)
    GROUP BY 1, 2
),

-- ordens: lead time (mes do fim real)
ord_fim AS (
    SELECT STRFTIME(o.FIM_REAL, '%Y-%m') AS ANO_MES, e.ESCOPO, AVG(o.LEAD_TIME_PRODUCAO_DIAS) AS LT_PROD
    FROM ordem o
    JOIN dim_recurso r USING (CODIGO_RECURSO)
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = r.CELULA
    WHERE o.FIM_REAL IS NOT NULL
    GROUP BY 1, 2
),

-- ordens vencidas e abertas no ultimo dia do mes
atraso AS (
    SELECT g.ANO_MES, g.ESCOPO, COUNT(o.NUMERO_OP) AS N_ATRASO
    FROM grade g
    LEFT JOIN (SELECT o.*, r.CELULA FROM ordem o JOIN dim_recurso r USING (CODIGO_RECURSO)) o
           ON (g.ESCOPO = 'Fábrica' OR g.ESCOPO = o.CELULA)
          AND o.DATA_NECESSIDADE <= g.FIM_MES
          AND (o.FIM_REAL IS NULL OR CAST(o.FIM_REAL AS DATE) > g.FIM_MES)
    GROUP BY 1, 2
),

-- pedidos (mes da data prometida)
ped AS (
    SELECT STRFTIME(p.DATA_PROMETIDA, '%Y-%m') AS ANO_MES, e.ESCOPO,
           COUNT(*) AS N_PED, COUNT(*) FILTER (WHERE p.NO_PRAZO) AS N_OT, COUNT(*) FILTER (WHERE p.COMPLETO) AS N_IF,
           COUNT(*) FILTER (WHERE p.OTIF) AS N_OTIF,
           AVG(p.DIAS_ATRASO) FILTER (WHERE p.DIAS_ATRASO > 0) AS ATRASO_MEDIO,
           AVG(p.LEAD_TIME_PEDIDO_DIAS) AS LT_PED
    FROM pedido p
    JOIN dim_produto d USING (CODIGO_PRODUTO)
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = d.CELULA
    GROUP BY 1, 2
),

-- estoques: media diaria do valor por tipo
est AS (
    SELECT STRFTIME(DATA, '%Y-%m') AS ANO_MES, ESCOPO,
           AVG(VALOR_MP) AS MP_MEDIO, SUM(RUPTURAS) AS RUPTURAS, AVG(VALOR_WIP) AS WIP_MEDIO
    FROM (
        SELECT s.DATA, e.ESCOPO,
               SUM(s.VALOR) FILTER (WHERE s.TIPO_ITEM = 'Matéria-prima') AS VALOR_MP,
               COUNT(*) FILTER (WHERE s.RUPTURA) AS RUPTURAS,
               COALESCE(SUM(s.VALOR) FILTER (WHERE s.TIPO_ITEM = 'Em processo'), 0) AS VALOR_WIP
        FROM estoque_dia s
        JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = s.CELULA
        GROUP BY 1, 2
    )
    GROUP BY 1, 2
),

-- consumo de materia-prima
cons AS (
    SELECT STRFTIME(c.DATA, '%Y-%m') AS ANO_MES, e.ESCOPO,
           SUM(c.VALOR_REAL) AS CONSUMO_VALOR,
           SUM(c.QTD_TEORICA) FILTER (WHERE c.CONTA_RENDIMENTO) AS KG_TEORICO,
           SUM(c.QTD_REAL) FILTER (WHERE c.CONTA_RENDIMENTO) AS KG_REAL
    FROM consumo_material c
    JOIN dim_recurso r USING (CODIGO_RECURSO)
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = r.CELULA
    GROUP BY 1, 2
),

-- pessoas
mo AS (
    SELECT STRFTIME(m.DATA, '%Y-%m') AS ANO_MES, e.ESCOPO,
           SUM(m.HORAS_TRABALHADAS) AS HH, SUM(m.HORAS_EXTRAS) AS HE,
           SUM(m.AUSENTES) AS AUSENTES, SUM(m.QUADRO_PREVISTO) AS QUADRO
    FROM mao_de_obra m
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = m.CELULA
    GROUP BY 1, 2
),

-- inventario ciclico (so fabrica)
inv AS (
    SELECT STRFTIME(DATA, '%Y-%m') AS ANO_MES, 'Fábrica' AS ESCOPO,
           COUNT(*) AS N_CONT, COUNT(*) FILTER (WHERE ACURADO) AS N_ACURADO
    FROM inventario
    GROUP BY 1, 2
),

-- previsao de vendas
prev AS (
    SELECT v.ANO_MES, e.ESCOPO, SUM(v.QTD_PREVISTA) AS PREVISTO, SUM(v.QTD_PEDIDA) AS PEDIDO, SUM(v.ERRO_ABSOLUTO) AS ERRO
    FROM previsao v
    JOIN dim_produto d USING (CODIGO_PRODUTO)
    JOIN escopos e ON e.ESCOPO = 'Fábrica' OR e.ESCOPO = d.CELULA
    GROUP BY 1, 2
),

largo AS (
    SELECT
        g.ANO_MES, g.ESCOPO,
        -- eficiencia
        (prod.RUN / NULLIF(prod.PROG, 0)) * (prod.TEO / NULLIF(prod.RUN, 0)) * (prod.BOA / NULLIF(prod.TOT, 0)) AS EFI01,
        prod.RUN / NULLIF(prod.PROG, 0) AS EFI02,
        prod.TEO / NULLIF(prod.RUN, 0) AS EFI03,
        prod.BOA / NULLIF(prod.TOT, 0) AS EFI04,
        (prod.TEO / NULLIF(cal.CAL, 0)) * (prod.BOA / NULLIF(prod.TOT, 0)) AS EFI05,
        prod.PROG / NULLIF(cal.CAL, 0) AS EFI06,
        prod.BOA / 1000.0 AS EFI07,
        prod.KG / 1000.0 AS EFI08,
        prod.RUN / NULLIF(prod.TEO, 0) - 1 AS EFI09,
        -- programacao
        prog.QR / NULLIF(prog.QP, 0) AS PLA01,
        prog.QA / NULLIF(prog.QP, 0) AS PLA02,
        ord_ini.N_SEQ / NULLIF(ord_ini.N_INI, 0)::DOUBLE AS PLA03,
        ord_prog.N_PRAZO / NULLIF(ord_prog.N_PROG, 0)::DOUBLE AS PLA04,
        prog.TP / NULLIF(prod.PROG, 0) AS PLA05,
        -- entrega
        ped.N_OTIF / NULLIF(ped.N_PED, 0)::DOUBLE AS ENT01,
        ped.N_OT / NULLIF(ped.N_PED, 0)::DOUBLE AS ENT02,
        ped.N_IF / NULLIF(ped.N_PED, 0)::DOUBLE AS ENT03,
        COALESCE(ped.ATRASO_MEDIO, 0) AS ENT04,
        atraso.N_ATRASO::DOUBLE AS ENT05,
        ord_fim.LT_PROD AS ENT06,
        ped.LT_PED AS ENT07,
        -- qualidade
        prod.REF / NULLIF(prod.TOT, 0) AS QUA01,
        prod.RET / NULLIF(prod.TOT, 0) AS QUA02,
        (prod.BOA - prod.RET) / NULLIF(prod.TOT, 0) AS QUA03,
        prod.REF / NULLIF(prod.TOT, 0) * 1000000 AS QUA04,
        prod.CR AS QUA05,
        -- paradas e manutencao
        prod.NP / 60.0 AS MAN01,
        prod.NP / NULLIF(prod.PROG, 0) AS MAN02,
        prod.RUN / 60.0 / NULLIF(prod.NQ, 0) AS MAN03,
        prod.MQ / NULLIF(prod.NQ, 0) AS MAN04,
        prod.SETUP_TROCA / NULLIF(ord_ini.N_SETUP, 0) AS MAN05,
        prod.SETUP / NULLIF(prod.PROG, 0) AS MAN06,
        prod.CP AS MAN07,
        -- materiais e estoques
        cons.CONSUMO_VALOR * 12 / NULLIF(est.MP_MEDIO, 0) AS MAT01,
        est.MP_MEDIO / NULLIF(cons.CONSUMO_VALOR / g.DIAS, 0) AS MAT02,
        inv.N_ACURADO / NULLIF(inv.N_CONT, 0)::DOUBLE AS MAT03,
        CASE WHEN g.ESCOPO = 'Fábrica' THEN est.RUPTURAS::DOUBLE END AS MAT04,
        cons.KG_TEORICO / NULLIF(cons.KG_REAL, 0) AS MAT05,
        est.WIP_MEDIO AS MAT06,
        -- pessoas
        prod.BOA / 1000.0 / NULLIF(mo.HH, 0) AS PES01,
        mo.HE / NULLIF(mo.HH, 0) AS PES02,
        mo.AUSENTES / NULLIF(mo.QUADRO, 0)::DOUBLE AS PES03,
        -- demanda
        1 - prev.ERRO / NULLIF(prev.PEDIDO, 0) AS DEM01,
        prev.PREVISTO / NULLIF(prev.PEDIDO, 0) - 1 AS DEM02
    FROM grade g
    LEFT JOIN prod USING (ANO_MES, ESCOPO)
    LEFT JOIN cal USING (ANO_MES, ESCOPO)
    LEFT JOIN prog USING (ANO_MES, ESCOPO)
    LEFT JOIN ord_ini USING (ANO_MES, ESCOPO)
    LEFT JOIN ord_prog USING (ANO_MES, ESCOPO)
    LEFT JOIN ord_fim USING (ANO_MES, ESCOPO)
    LEFT JOIN atraso USING (ANO_MES, ESCOPO)
    LEFT JOIN ped USING (ANO_MES, ESCOPO)
    LEFT JOIN est USING (ANO_MES, ESCOPO)
    LEFT JOIN cons USING (ANO_MES, ESCOPO)
    LEFT JOIN mo USING (ANO_MES, ESCOPO)
    LEFT JOIN inv USING (ANO_MES, ESCOPO)
    LEFT JOIN prev USING (ANO_MES, ESCOPO)
),

longo AS (
    UNPIVOT largo ON COLUMNS(* EXCLUDE (ANO_MES, ESCOPO)) INTO NAME CODIGO VALUE VALOR
)

SELECT
    l.ANO_MES,
    g.MES_ROTULO,
    l.ESCOPO,
    g.ORDEM_ESCOPO,
    l.CODIGO,
    i.FAMILIA,
    i.INDICADOR,
    i.UNIDADE,
    i.SENTIDO,
    l.VALOR,
    i.META,
    CASE WHEN i.META IS NULL THEN NULL
         WHEN i.SENTIDO = 'maior' THEN l.VALOR / NULLIF(i.META, 0)
         WHEN i.SENTIDO = 'menor' THEN CASE WHEN l.VALOR <= i.META THEN 1 ELSE i.META / l.VALOR END
         ELSE CASE WHEN ABS(l.VALOR) <= i.META THEN 1 ELSE i.META / ABS(l.VALOR) END END AS ATINGIMENTO,
    CASE WHEN i.META IS NULL THEN 'Sem meta'
         WHEN i.SENTIDO = 'maior' THEN CASE WHEN l.VALOR >= i.META THEN 'No alvo' WHEN l.VALOR >= 0.9 * i.META THEN 'Atenção' ELSE 'Crítico' END
         WHEN i.SENTIDO = 'menor' THEN CASE WHEN l.VALOR <= i.META THEN 'No alvo' WHEN l.VALOR <= 1.1 * i.META THEN 'Atenção' ELSE 'Crítico' END
         ELSE CASE WHEN ABS(l.VALOR) <= i.META THEN 'No alvo' WHEN ABS(l.VALOR) <= 2 * i.META THEN 'Atenção' ELSE 'Crítico' END END AS STATUS
FROM longo l
JOIN grade g USING (ANO_MES, ESCOPO)
JOIN cfg_indicadores i USING (CODIGO)
ORDER BY l.ANO_MES, g.ORDEM_ESCOPO, l.CODIGO;
