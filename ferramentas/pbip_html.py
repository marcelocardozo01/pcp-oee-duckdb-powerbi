"""Medidas DAX que devolvem HTML + CSS, para o visual "HTML Content" do Power BI.

Cada medida monta um bloco do painel (cabecalho, cartoes, barras, cascata, tabela)
como texto HTML com estilo inline. O Power BI recalcula a medida a cada filtro e o
visual desenha o resultado: o layout e de pagina web, o numero e do modelo.

As funcoes abaixo sao "moldes" em Python que escrevem o DAX, para o mesmo desenho
valer em todas as paginas. Quem importa e ferramentas/gerar_pbip.py.
"""

# Paleta do painel (a mesma do painel HTML)
C = dict(fundo="#0F5160", painel="#0A4250", trilho="#14606F", linha="#1C6E7E",
         tinta="#F2F2F2", tinta2="#A9D3DC", mudo="#6FA9B5",
         ciano="#53D1EC", petroleo="#078CA9", lima="#C5DF16", lima2="#DDF156", coral="#FF7A6B")
FONTE = "font-family:Bahnschrift,Segoe UI,sans-serif;color:%s;line-height:1.35" % C["tinta"]
VISUAL_HTML = "htmlContent443BE3AD55E043BF878BED274D3A6865"


def s(txt):
    """Texto -> literal DAX."""
    return '"' + txt.replace('"', '""') + '"'


def junta(*partes):
    return " & ".join(partes)


PCT = lambda v: f'FORMAT({v}, "0.0%")'
PCT2 = lambda v: f'FORMAT({v}, "0.00%")'
PCT0 = lambda v: f'FORMAT({v}, "0%")'
INT = lambda v: f'FORMAT({v}, "#,##0")'
DEC = lambda v: f'FORMAT({v}, "#,##0.0")'
HORAS = lambda v: f'FORMAT({v}, "#,##0") & " h"'
REAIS = lambda v: f'"R$ " & FORMAT({v}, "#,##0")'
SUF = lambda suf: (lambda v: f'FORMAT({v}, "#,##0.0") & " {suf}"')


def painel(titulo, sub, altura):
    return (f"<div style='{FONTE};background:{C['painel']};border-radius:12px;padding:13px 16px 10px;"
            f"box-sizing:border-box;height:{altura}px;overflow:hidden'>"
            f"<div style='font-size:15px;font-weight:600'>{titulo}</div>"
            f"<div style='font-size:12px;color:{C['tinta2']};margin:1px 0 10px'>{sub}</div>")


def cabecalho(titulo, com_maquina=True):
    escopo = ('IF(HASONEVALUE(dRecurso[CODIGO_RECURSO]), "máquina " & SELECTEDVALUE(dRecurso[CODIGO_RECURSO]), '
              'IF(HASONEVALUE(dRecurso[CELULA]), "célula " & SELECTEDVALUE(dRecurso[CELULA]), "fábrica toda"))'
              if com_maquina else 'IF(HASONEVALUE(fIndicador[ESCOPO]), SELECTEDVALUE(fIndicador[ESCOPO]), "Fábrica")')
    fita = f"repeating-linear-gradient(135deg,{C['lima']} 0 14px,{C['painel']} 14px 28px)"
    return [
        'VAR ini = LOOKUPVALUE(dMes[MES_ROTULO], dMes[ANO_MES], MIN(dMes[ANO_MES]))',
        'VAR fim = LOOKUPVALUE(dMes[MES_ROTULO], dMes[ANO_MES], MAX(dMes[ANO_MES]))',
        'VAR periodo = IF(ini = fim, ini, ini & " a " & fim)' if com_maquina else 'VAR periodo = fim',
        f'VAR escopo = {escopo}',
        'RETURN',
        "    " + junta(
            s(f"<div style='{FONTE};background:{C['painel']};height:70px;box-sizing:border-box;position:relative;overflow:hidden'>"
              f"<div style='padding:9px 20px 0'><div style='font-size:12px;color:{C['lima']};letter-spacing:.4px'>Moldara Embalagens</div>"
              f"<div style='font-size:23px;font-weight:600;line-height:1.15'>{titulo}"
              f"<span style='font-size:13px;font-weight:400;color:{C['tinta2']};margin-left:12px'>"),
            "periodo", s(", "), "escopo",
            s(f"</span></div></div><div style='position:absolute;left:0;right:0;bottom:0;height:5px;background:{fita}'></div></div>")),
    ]


def cartoes(specs, altura=112):
    """specs: (rotulo, medida, formato, meta, sentido, escala da barra, texto da meta)."""
    L, blocos = [], []
    base = (f"flex:1;min-width:0;background:{C['painel']};border-radius:12px;padding:11px 14px 9px;box-sizing:border-box;height:{altura}px")
    rot_css = f"font-size:12px;color:{C['tinta2']};white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
    val_css = "font-size:29px;font-weight:600;line-height:1.2"
    for i, (rot, med, fmt, meta, sentido, escala, meta_txt) in enumerate(specs, 1):
        L.append(f"VAR v{i} = {med}")
        if meta is None:
            blocos.append(junta(
                s(f"<div style='{base};border-left:4px solid {C['petroleo']}'><div style='{rot_css}'>{rot}</div><div style='{val_css}'>"),
                fmt(f"v{i}"),
                s(f"</div><div style='font-size:11px;color:{C['tinta2']};margin-top:17px'>{meta_txt}</div></div>")))
            continue
        ok = f"v{i} >= {meta}" if sentido == "maior" else f"v{i} <= {meta}"
        al = f"v{i} >= {round(meta * 0.9, 6)}" if sentido == "maior" else f"v{i} <= {round(meta * 1.1, 6)}"
        L += [f'VAR c{i} = IF({ok}, "{C["lima"]}", IF({al}, "{C["tinta"]}", "{C["coral"]}"))',
              f'VAR r{i} = IF({ok}, "✓ No alvo", IF({al}, "! Atenção", "✕ Crítico"))',
              f'VAR w{i} = FORMAT(INT(MIN(1, DIVIDE(v{i}, {escala})) * 100), "0")']
        marca = int(round(meta / escala * 100))
        blocos.append(junta(
            s(f"<div style='{base};border-left:4px solid "), f"c{i}",
            s(f"'><div style='{rot_css}'>{rot}</div><div style='{val_css}'>"), fmt(f"v{i}"),
            s(f"</div><div style='height:5px;border-radius:3px;background:{C['trilho']};position:relative;margin:7px 0 8px'>"
              f"<div style='height:5px;border-radius:3px;background:{C['ciano']};width:"), f"w{i}",
            s(f"%'></div><div style='position:absolute;left:{marca}%;top:-3px;width:2px;height:11px;background:{C['tinta']}'></div></div>"
              f"<div style='display:flex;justify-content:space-between;font-size:11px;color:{C['tinta2']}'><span>{meta_txt}</span>"
              f"<span style='font-weight:600;color:"), f"c{i}", s("'>"), f"r{i}", s("</span></div></div>")))
    L.append("RETURN")
    L.append("    " + s(f"<div style='{FONTE};display:flex;gap:12px'>"))
    L += ["    & " + b for b in blocos]
    L.append("    & " + s("</div>"))
    return L


def barras(titulo, sub, tabela, nome, medida, fmt, altura, maximo=None, meta=None, topo=12, pareto=False, rotulo="36%", extra=None):
    """Barras horizontais ordenadas. `tabela` = expressao de tabela; `nome` = texto no contexto de linha."""
    L = [f'VAR t0 = FILTER(ADDCOLUMNS({tabela}, "@v", {medida}), NOT ISBLANK([@v]) && [@v] <> 0)',
         "VAR tot = SUMX(t0, [@v])",
         'VAR t = ADDCOLUMNS(t0, "@ac", VAR x = [@v] RETURN DIVIDE(SUMX(FILTER(t0, [@v] >= x), [@v]), tot))',
         f"VAR mx = {maximo if maximo is not None else 'MAXX(t0, [@v])'}"]
    marca = (f"<div style='position:absolute;left:{int(round(meta / maximo * 100))}%;top:-3px;width:2px;height:18px;background:{C['tinta']}'></div>"
             if meta is not None and maximo else "")
    val = fmt("[@v]")
    if pareto:
        val = junta(val, s(f" <span style='color:{C['mudo']};margin-left:6px'>"), PCT0("[@ac]"), s("</span>"))
    if extra:
        val = junta(val, s(f" <span style='color:{C['mudo']};margin-left:6px'>"), extra, s("</span>"))
    linha = junta(
        s(f"<div style='display:grid;grid-template-columns:{rotulo} 1fr auto;gap:10px;align-items:center;font-size:12px;line-height:1.2;margin-bottom:4px'>"
          f"<div style='color:{C['tinta2']};white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>"), nome,
        s(f"</div><div style='position:relative;height:12px;background:{C['trilho']};border-radius:0 4px 4px 0'>"
          f"<div style='height:12px;border-radius:0 4px 4px 0;background:{C['ciano']};width:"),
        'FORMAT(INT(MIN(1, DIVIDE([@v], mx)) * 100), "0")',
        s(f"%'></div>{marca}</div><div style='text-align:right;white-space:nowrap;min-width:52px'>"), val, s("</div></div>"))
    if marca:
        sub += " A marca branca é a meta."
    L += ["RETURN",
          "    " + s(painel(titulo, sub, altura)),
          f'    & CONCATENATEX(TOPN({topo}, t, [@v], DESC), {linha}, "", [@v], DESC)',
          "    & " + s("</div>")]
    return L


def cascata(altura):
    cor = (f'SWITCH(fPerdasTempo[TIPO], "Produtivo", "{C["ciano"]}", "Disponibilidade", "{C["lima"]}", '
           f'"Performance", "{C["lima2"]}", "Qualidade", "{C["tinta"]}", "#2B7585")')
    tinta = f'IF(fPerdasTempo[TIPO] = "Fora da carga", "{C["tinta"]}", "{C["painel"]}")'
    ordem = "SWITCH(fPerdasTempo[ORDEM], 9, 1, 8, 2, 7, 3, 3, 4, 4, 5, 5, 6, 6, 7, 2, 8, 9)"
    seg = junta(s("<div style='flex:"), 'FORMAT(INT([@h]), "0")', s(" 0 0;min-width:3px;border-radius:4px;font-size:12px;font-weight:600;padding:6px 7px;"
                  "white-space:nowrap;overflow:hidden;box-sizing:border-box;background:"), cor, s(";color:"), tinta, s("'>"),
                'IF(DIVIDE([@h], tot) > 0.06, FORMAT(DIVIDE([@h], tot), "0%"), "")', s("</div>"))
    leg = junta(s("<span style='white-space:nowrap'><i style='display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;background:"),
                cor, s("'></i>"), "fPerdasTempo[ETAPA]", s(f" <b style='color:{C['tinta']};font-weight:600'>"), HORAS("[@h]"), s("</b></span>"))
    return [
        'VAR t = FILTER(ADDCOLUMNS(SUMMARIZE(fPerdasTempo, fPerdasTempo[ORDEM], fPerdasTempo[ETAPA], fPerdasTempo[TIPO]), '
        '"@h", [Horas de calendário]), [@h] >= 1)',
        "VAR tot = SUMX(t, [@h])",
        "RETURN",
        "    " + s(painel("Para onde foram as horas das máquinas",
                          "As 24 horas de calendário de cada máquina: o que virou peça boa e o que se perdeu no caminho.", altura)
                   + "<div style='display:flex;gap:2px;height:30px;margin-bottom:11px'>"),
        f'    & CONCATENATEX(t, {seg}, "", {ordem}, ASC)',
        "    & " + s(f"</div><div style='display:flex;flex-wrap:wrap;gap:5px 18px;font-size:12px;color:{C['tinta2']}'>"),
        f'    & CONCATENATEX(t, {leg}, "", {ordem}, ASC)',
        "    & " + s("</div></div>"),
    ]


def maquinas(altura):
    cor = f'IF([@o] >= 0.75, "{C["lima"]}", IF([@o] >= 0.675, "{C["tinta"]}", "{C["coral"]}"))'
    mini = lambda rot, col: junta(s(f"<span>{rot} <b style='color:{C['tinta']};font-weight:600'>"), PCT0(col), s("</b></span>"))
    bloco = junta(
        s(f"<div style='background:{C['fundo']};border-radius:8px;padding:8px 10px 9px;border-top:3px solid "), cor,
        s("'><div style='display:flex;justify-content:space-between;align-items:baseline'><b style='font-size:13px;font-weight:600'>"),
        "dRecurso[CODIGO_RECURSO]", s("</b><span style='font-size:19px;font-weight:600'>"), PCT("[@o]"),
        s(f"</span></div><div style='font-size:10.5px;color:{C['mudo']};white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>"),
        "dRecurso[RECURSO]",
        s(f"</div><div style='height:5px;border-radius:3px;background:{C['trilho']};position:relative;margin:6px 0 6px'>"
          f"<div style='height:5px;border-radius:3px;background:{C['ciano']};width:"),
        'FORMAT(INT(MIN(1, [@o]) * 100), "0")',
        s(f"%'></div><div style='position:absolute;left:75%;top:-3px;width:2px;height:11px;background:{C['tinta']}'></div></div>"
          f"<div style='display:flex;justify-content:space-between;font-size:10.5px;color:{C['tinta2']}'>"),
        mini("D", "[@d]"), mini("P", "[@p]"), mini("Q", "[@q]"), s("</div></div>"))
    return [
        'VAR t = FILTER(ADDCOLUMNS(SUMMARIZE(dRecurso, dRecurso[CODIGO_RECURSO], dRecurso[RECURSO]), "@o", [OEE], '
        '"@d", [Disponibilidade], "@p", [Performance], "@q", [Qualidade]), NOT ISBLANK([@o]))',
        "RETURN",
        "    " + s(painel("Máquinas", "OEE de cada máquina contra a meta de 75%, com disponibilidade (D), performance (P) e qualidade (Q).", altura)
                   + "<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:8px'>"),
        f'    & CONCATENATEX(t, {bloco}, "", dRecurso[CODIGO_RECURSO], ASC)',
        "    & " + s("</div></div>"),
    ]


def tabela(titulo, sub, altura, origem, colunas, ordem, sentido="DESC", grade=None):
    """Tabela HTML. colunas: (cabecalho, expressao DAX de texto, alinhamento)."""
    grade = grade or " ".join("1fr" for _ in colunas)
    cab = "".join(f"<div style='text-align:{a}'>{c}</div>" for c, _, a in colunas)
    cel = []
    for _, expr, a in colunas:
        cel += [s(f"<div style='text-align:{a};white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>"), expr, s("</div>")]
    linha = junta(s(f"<div style='display:grid;grid-template-columns:{grade};gap:10px;font-size:12px;line-height:1.25;padding:3px 0;border-bottom:1px solid {C['linha']}'>"),
                  *cel, s("</div>"))
    return [
        f"VAR t = {origem}",
        "RETURN",
        "    " + s(painel(titulo, sub, altura) + f"<div style='display:grid;grid-template-columns:{grade};gap:10px;font-size:11.5px;"
                   f"color:{C['tinta2']};padding-bottom:5px;border-bottom:1px solid {C['mudo']}'>{cab}</div>"),
        f'    & CONCATENATEX(t, {linha}, "", {ordem}, {sentido})',
        "    & " + s("</div>"),
    ]


def indicadores(altura):
    val = lambda col: (f'SWITCH(fIndicador[UNIDADE], "%", FORMAT({col}, "0.0%"), "R$", "R$ " & FORMAT({col}, "#,##0"), '
                       f'"ppm", FORMAT({col}, "#,##0"), "un", FORMAT({col}, "#,##0"), "item-dia", FORMAT({col}, "#,##0"), '
                       f'FORMAT({col}, "#,##0.0") & " " & fIndicador[UNIDADE])')
    meta = (f'IF(ISBLANK(fIndicador[META]), "–", SWITCH(fIndicador[SENTIDO], "maior", "≥ ", "menor", "≤ ", "± ") & '
            f'SWITCH(fIndicador[UNIDADE], "%", FORMAT(fIndicador[META], "0.0%"), "ppm", FORMAT(fIndicador[META], "#,##0"), FORMAT(fIndicador[META], "#,##0.0")))')
    cor = (f'SWITCH(fIndicador[STATUS], "No alvo", "{C["lima"]}", "Atenção", "{C["tinta"]}", "Crítico", "{C["coral"]}", "{C["mudo"]}")')
    marca = 'SWITCH(fIndicador[STATUS], "No alvo", "✓", "Atenção", "!", "Crítico", "✕", "–")'
    familia = junta(s(f"<div style='font-size:12.5px;font-weight:600;line-height:1.2;color:{C['lima']};padding:6px 0 2px;border-bottom:1px solid {C['mudo']}'>"),
                    "fIndicador[FAMILIA]", s("</div>"))
    linha = junta(
        f'IF(RIGHT(fIndicador[CODIGO], 2) = "01", {familia}, "")',
        s(f"<div style='display:grid;grid-template-columns:1fr 92px 74px 82px;gap:8px;font-size:12px;line-height:1.2;padding:2px 0;"
          f"border-bottom:1px solid {C['linha']};break-inside:avoid'><div style='white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>"),
        "fIndicador[INDICADOR]", s("</div><div style='text-align:right;font-weight:600;white-space:nowrap'>"), val("fIndicador[VALOR]"),
        s(f"</div><div style='text-align:right;color:{C['tinta2']};white-space:nowrap'>"), meta,
        s("</div><div style='white-space:nowrap;color:"), cor, s("'>"), marca, s(" "), "fIndicador[STATUS]", s("</div></div>"))
    return [
        "VAR mes = MAX(fIndicador[ANO_MES])",
        'VAR esc = IF(HASONEVALUE(fIndicador[ESCOPO]), SELECTEDVALUE(fIndicador[ESCOPO]), "Fábrica")',
        "VAR t = CALCULATETABLE(fIndicador, fIndicador[ANO_MES] = mes, fIndicador[ESCOPO] = esc)",
        'VAR alvo = COUNTROWS(FILTER(t, fIndicador[STATUS] = "No alvo"))',
        'VAR comMeta = COUNTROWS(FILTER(t, fIndicador[STATUS] <> "Sem meta"))',
        "RETURN",
        "    " + junta(
            s(f"<div style='{FONTE};background:{C['painel']};border-radius:12px;padding:12px 18px;box-sizing:border-box;height:{altura}px;overflow:hidden'>"
              f"<div style='font-size:15px;font-weight:600'>Indicadores do PCP <span style='font-size:12px;font-weight:400;color:{C['tinta2']};margin-left:10px'>"),
            'FORMAT(alvo, "0")', s(" de "), 'FORMAT(comMeta, "0")',
            s(" indicadores com meta estão no alvo. Sem mês selecionado, vale o mais recente.</span></div><div style='column-count:2;column-gap:32px;margin-top:4px'>")),
        f'    & CONCATENATEX(t, {linha}, "", fIndicador[CODIGO], ASC)',
        "    & " + s("</div></div>"),
    ]


# ----------------------------------------------------------------------------
# Medidas HTML (tabela "Painel") e paginas
# ----------------------------------------------------------------------------
MAQ = "SUMMARIZE(dRecurso, dRecurso[CODIGO_RECURSO], dRecurso[RECURSO])"
NOME_MAQ = 'dRecurso[CODIGO_RECURSO] & "  " & dRecurso[RECURSO]'
A, B = 290, 200                    # alturas dos blocos da 1a e da 2a faixa

MEDIDAS_HTML = {
    "HTML Cabeçalho Visão geral": cabecalho("Performance do PCP"),
    "HTML Cabeçalho OEE": cabecalho("OEE e paradas"),
    "HTML Cabeçalho Programa": cabecalho("Programa e entrega"),
    "HTML Cabeçalho Qualidade": cabecalho("Qualidade"),
    "HTML Cabeçalho Indicadores": cabecalho("Todos os indicadores", com_maquina=False),

    "HTML Cartões Visão geral": cartoes([
        ("OEE", "[OEE]", PCT, 0.75, "maior", 1, "meta ≥ 75%"),
        ("Aderência ao mix", "[Aderência ao mix]", PCT, 0.90, "maior", 1, "meta ≥ 90%"),
        ("OTIF", "[OTIF %]", PCT, 0.90, "maior", 1, "meta ≥ 90%"),
        ("Refugo", "[Refugo %]", PCT2, 0.025, "menor", 0.05, "meta ≤ 2,5%"),
        ("Parada não planejada", "[Parada não planejada %]", PCT, 0.15, "menor", 0.30, "meta ≤ 15%"),
        ("MTBF", "[MTBF (h)]", SUF("h"), 16, "maior", 21.3, "meta ≥ 16 h")]),
    "HTML Cascata": cascata(126),
    "HTML Máquinas": maquinas(352),

    "HTML Cartões OEE": cartoes([
        ("OEE", "[OEE]", PCT, 0.75, "maior", 1, "meta ≥ 75%"),
        ("Disponibilidade", "[Disponibilidade]", PCT, 0.85, "maior", 1, "meta ≥ 85%"),
        ("Performance", "[Performance]", PCT, 0.92, "maior", 1, "meta ≥ 92%"),
        ("Qualidade", "[Qualidade]", PCT, 0.98, "maior", 1, "meta ≥ 98%"),
        ("MTTR", "[MTTR (min)]", SUF("min"), 55, "menor", 110, "meta ≤ 55 min"),
        ("Custo das paradas", "[Custo das paradas]", REAIS, None, None, None, "horas paradas × custo hora da máquina")]),
    "HTML OEE por máquina": barras("OEE por máquina", "Da melhor para a pior no período.", MAQ, NOME_MAQ, "[OEE]", PCT, A, maximo=1, meta=0.75, rotulo="42%"),
    "HTML Motivos de parada": barras("Motivos de parada", "Horas de parada não planejada e percentual acumulado.", "VALUES(fParada[MOTIVO])",
                                     "fParada[MOTIVO]", "[Horas de parada não planejada]", HORAS, A, pareto=True, rotulo="44%"),
    "HTML OEE por turno": barras("OEE por turno", "O mesmo parque, três equipes.", "VALUES(dTurno[TURNO_NOME])", "dTurno[TURNO_NOME]",
                                 "[OEE]", PCT, B, maximo=1, meta=0.75, rotulo="44%"),
    "HTML Paradas por categoria": barras("Paradas por categoria", "Quem é o dono de cada bloco de horas.", "VALUES(fParada[CATEGORIA])",
                                         "fParada[CATEGORIA]", "[Horas de parada não planejada]", HORAS, B, pareto=True, rotulo="44%"),

    "HTML Cartões Programa": cartoes([
        ("Aderência ao volume", "[Aderência ao volume]", PCT, 0.95, "maior", 1.1, "meta ≥ 95%"),
        ("Aderência ao mix", "[Aderência ao mix]", PCT, 0.90, "maior", 1, "meta ≥ 90%"),
        ("OTIF", "[OTIF %]", PCT, 0.90, "maior", 1, "meta ≥ 90%"),
        ("No prazo", "[No prazo %]", PCT, 0.95, "maior", 1, "meta ≥ 95%"),
        ("Completo", "[Completo %]", PCT, 0.95, "maior", 1, "meta ≥ 95%"),
        ("Pedidos fora do OTIF", "[Pedidos fora do OTIF]", INT, None, None, None, "atrasados ou incompletos no período")]),
    "HTML Aderência por máquina": barras("Aderência ao mix por máquina", "Programa cumprido na ordem e no dia combinados.", MAQ, NOME_MAQ,
                                         "[Aderência ao mix]", PCT, A, maximo=1, meta=0.9, rotulo="42%"),
    "HTML OTIF por cliente": barras("OTIF por cliente", "Pedidos entregues no prazo e completos.", "VALUES(fPedido[CLIENTE])", "fPedido[CLIENTE]",
                                    "[OTIF %]", PCT0, A, maximo=1, meta=0.9, rotulo="46%", extra='FORMAT([Pedidos], "0") & " ped."'),
    "HTML Pedidos fora do OTIF": tabela(
        "Pedidos fora do OTIF", "Os mais atrasados do período.", B,
        "TOPN(5, FILTER(fPedido, fPedido[OTIF] = FALSE()), fPedido[DIAS_ATRASO], DESC, fPedido[NUMERO_PEDIDO], ASC)",
        [("Pedido", 'FORMAT(fPedido[NUMERO_PEDIDO], "0")', "left"), ("Cliente", "fPedido[CLIENTE]", "left"),
         ("Produto", "RELATED(dProduto[PRODUTO])", "left"), ("Prometido", 'FORMAT(fPedido[DATA_PROMETIDA], "dd/mm")', "left"),
         ("Entregue", 'IF(ISBLANK(fPedido[DATA_ENTREGA]), "em aberto", FORMAT(fPedido[DATA_ENTREGA], "dd/mm"))', "left"),
         ("Atraso", 'FORMAT(fPedido[DIAS_ATRASO], "0") & " d"', "right"),
         ("Entregue / pedido", 'FORMAT(DIVIDE(fPedido[QTD_ENTREGUE], fPedido[QTD_PEDIDA]), "0%")', "right")],
        "fPedido[DIAS_ATRASO] * 1000000 - fPedido[NUMERO_PEDIDO] / 1000000", grade="64px 1.3fr 1.5fr 70px 70px 54px 110px"),

    "HTML Cartões Qualidade": cartoes([
        ("Refugo", "[Refugo %]", PCT2, 0.025, "menor", 0.05, "meta ≤ 2,5%"),
        ("FPY, aprovação de primeira", "[FPY]", PCT, 0.965, "maior", 1, "meta ≥ 96,5%"),
        ("Qualidade (fator do OEE)", "[Qualidade]", PCT, 0.98, "maior", 1, "meta ≥ 98%"),
        ("Peças refugadas", "[Peças refugadas]", INT, None, None, None, "contador da máquina"),
        ("Custo do refugo", "[Custo do refugo]", REAIS, None, None, None, "peças refugadas × custo padrão")]),
    "HTML Defeitos": barras("Defeitos que mais refugam", "Peças refugadas por defeito e percentual acumulado.", "VALUES(fRefugoDefeito[DEFEITO])",
                            "fRefugoDefeito[DEFEITO]", "[Peças refugadas]", INT, A, pareto=True, rotulo="38%"),
    "HTML Refugo por máquina": barras("Refugo por máquina", "Peças refugadas sobre as produzidas.", MAQ, NOME_MAQ, "[Refugo %]", PCT2, A,
                                      maximo=0.06, meta=0.025, rotulo="42%"),
    "HTML Refugo por produto": barras("Onde o refugo custa mais", "Custo do refugo por produto, em reais.", "VALUES(dProduto[PRODUTO])",
                                      "dProduto[PRODUTO]", "[Custo do refugo por defeito]", REAIS, B, pareto=True, topo=7, rotulo="40%"),

    "HTML Indicadores": indicadores(632),
}

H = "html"
SEG = [("slicer", 800, 3, 150, 60, None, {"Values": ["dMes.MES_ROTULO|Mês"]}, None),
       ("slicer", 958, 3, 150, 60, None, {"Values": ["dRecurso.CELULA|Célula"]}, None),
       ("slicer", 1116, 3, 150, 60, None, {"Values": ["dRecurso.CODIGO_RECURSO|Máquina"]}, None)]


def topo(cab, cart):
    return [(H, 0, 0, 1280, 70, None, cab, None)] + SEG + [(H, 16, 82, 1248, 112, None, cart, None)]


PAGINAS = [
    ("visaogeral", "Visão geral", topo("HTML Cabeçalho Visão geral", "HTML Cartões Visão geral") + [
        (H, 16, 206, 1248, 126, None, "HTML Cascata", None),
        ("lineChart", 16, 344, 560, 360, "OEE por dia, contra a meta de 75%", {"Category": ["dCalendario.DATA|Dia"], "Y": ["OEE", "Meta OEE"]}, None),
        (H, 588, 344, 676, 360, None, "HTML Máquinas", None)]),
    ("oeeparadas", "OEE e paradas", topo("HTML Cabeçalho OEE", "HTML Cartões OEE") + [
        (H, 16, 206, 618, A, None, "HTML OEE por máquina", None),
        (H, 646, 206, 618, A, None, "HTML Motivos de parada", None),
        (H, 16, 508, 404, B, None, "HTML OEE por turno", None),
        ("clusteredColumnChart", 432, 508, 404, B, "OEE por mês", {"Category": ["dMes.MES_ROTULO|Mês"], "Y": ["OEE"]}, None),
        (H, 848, 508, 416, B, None, "HTML Paradas por categoria", None)]),
    ("programaentrega", "Programa e entrega", topo("HTML Cabeçalho Programa", "HTML Cartões Programa") + [
        (H, 16, 206, 480, A, None, "HTML Aderência por máquina", None),
        (H, 508, 206, 400, A, None, "HTML OTIF por cliente", None),
        ("lineChart", 920, 206, 344, A, "OTIF por mês, contra a meta de 90%", {"Category": ["dMes.MES_ROTULO|Mês"], "Y": ["OTIF %", "Meta OTIF"]}, None),
        (H, 16, 508, 1248, B, None, "HTML Pedidos fora do OTIF", None)]),
    ("qualidade", "Qualidade", topo("HTML Cabeçalho Qualidade", "HTML Cartões Qualidade") + [
        (H, 16, 206, 618, A, None, "HTML Defeitos", None),
        (H, 646, 206, 618, A, None, "HTML Refugo por máquina", None),
        (H, 16, 508, 618, B, None, "HTML Refugo por produto", None),
        ("clusteredColumnChart", 646, 508, 618, B, "Refugo por mês", {"Category": ["dMes.MES_ROTULO|Mês"], "Y": ["Refugo %"]}, None)]),
    ("indicadores", "Todos os indicadores", [
        (H, 0, 0, 1280, 70, None, "HTML Cabeçalho Indicadores", None),
        ("slicer", 958, 3, 150, 60, None, {"Values": ["dMes.MES_ROTULO|Mês"]}, None),
        ("slicer", 1116, 3, 150, 60, None, {"Values": ["fIndicador.ESCOPO|Escopo"]}, None),
        (H, 16, 80, 1248, 632, None, "HTML Indicadores", None)]),
]
