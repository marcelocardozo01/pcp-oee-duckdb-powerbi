"""Gera o relatorio Power BI (formato PBIP) a partir de uma definicao em Python.

O PBIP e texto: modelo em TMDL e relatorio em JSON. Em vez de montar na mao no
Power BI Desktop, o modelo, as medidas e as paginas ficam descritos aqui e sao
escritos em powerbi/PCP_Performance.*. Mudou uma medida ou um visual? Edita este
arquivo, roda de novo e o diff do Git mostra exatamente o que mudou.

O desenho do painel vem de ferramentas/pbip_html.py: medidas DAX que devolvem HTML + CSS,
mostradas pelo visual "HTML Content" (baixado da AppSource ao abrir). Series no tempo e
segmentacoes usam visuais nativos, com o mesmo tema.

Uso: python ferramentas/gerar_pbip.py
"""
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pbip_html as H

RAIZ = Path(__file__).resolve().parents[1]
PBI = RAIZ / "powerbi"
NOME = "PCP_Performance"
PASTA_PADRAO = "C:\\pcp-moldara\\dados\\exports\\"
NS = uuid.UUID("5f0c2d1e-7a44-4a53-9d0b-3f6a1b2c4d5e")
tag = lambda *p: str(uuid.uuid5(NS, "/".join(p)))

T = {"date": ("dateTime", "type date"), "int": ("int64", "Int64.Type"), "num": ("double", "type number"),
     "text": ("string", "type text"), "bool": ("boolean", "type logical")}

# tabela do modelo -> (parquet, colunas {nome: tipo}, colunas ocultas, ordenar {coluna: por}, passo M extra)
TABELAS = {
    "dCalendario": ("dim_calendario", {"DATA": "date", "ANO_MES": "text", "SEMANA": "text", "DIA_SEMANA": "text",
                                       "NUM_DIA_SEMANA": "int", "DIA_UTIL": "bool"}, ["NUM_DIA_SEMANA"], {"DIA_SEMANA": "NUM_DIA_SEMANA"}, None),
    "dMes": ("dim_calendario", {"ANO_MES": "text", "MES_ROTULO": "text"}, [], {"MES_ROTULO": "ANO_MES"}, "Table.Distinct(Tipos)"),
    "dRecurso": ("dim_recurso", {"CODIGO_RECURSO": "text", "RECURSO": "text", "CELULA": "text", "ORDEM_CELULA": "int",
                                 "CUSTO_HORA": "num"}, ["ORDEM_CELULA"], {"CELULA": "ORDEM_CELULA"}, None),
    "dProduto": ("dim_produto", {"CODIGO_PRODUTO": "int", "PRODUTO": "text", "FAMILIA": "text"}, [], {}, None),
    "dTurno": ("dim_turno", {"TURNO": "int", "TURNO_NOME": "text"}, [], {"TURNO_NOME": "TURNO"}, None),
    "fProducaoTurno": ("producao_turno", {
        "DATA": "date", "TURNO": "int", "CODIGO_RECURSO": "text", "TEMPO_TURNO_MIN": "num", "PARADA_PLANEJADA_MIN": "num",
        "TEMPO_PROGRAMADO_MIN": "num", "PARADA_NAO_PLANEJADA_MIN": "num", "SETUP_MIN": "num", "QUEBRA_MIN": "num",
        "N_QUEBRAS": "int", "TEMPO_PRODUZINDO_MIN": "num", "TEMPO_NAO_APONTADO_MIN": "num", "TEMPO_TEORICO_MIN": "num",
        "QTD_PRODUZIDA": "num", "QTD_BOA": "num", "QTD_REFUGO": "num", "QTD_RETRABALHO": "num", "KG_TRANSFORMADO": "num",
        "CUSTO_REFUGO": "num", "CUSTO_PARADA": "num"}, "*", {}, None),
    "fParada": ("parada", {"DATA": "date", "TURNO": "int", "CODIGO_RECURSO": "text", "DURACAO_MIN": "num", "MOTIVO": "text",
                           "CATEGORIA": "text", "PLANEJADA": "bool"}, ["DATA", "TURNO", "CODIGO_RECURSO", "DURACAO_MIN"], {}, None),
    "fRefugoDefeito": ("refugo_defeito", {"DATA": "date", "TURNO": "int", "CODIGO_RECURSO": "text", "CODIGO_PRODUTO": "int",
                                          "DEFEITO": "text", "QTD_REFUGO": "num", "CUSTO_REFUGO": "num"},
                       ["DATA", "TURNO", "CODIGO_RECURSO", "CODIGO_PRODUTO", "QTD_REFUGO", "CUSTO_REFUGO"], {}, None),
    "fProgramaDia": ("programa_dia", {"DATA": "date", "CODIGO_RECURSO": "text", "CODIGO_PRODUTO": "int", "NUMERO_OP": "int",
                                      "QTD_PROGRAMADA": "num", "QTD_REAL": "num", "QTD_ADERENTE": "num"},
                     ["DATA", "CODIGO_RECURSO", "CODIGO_PRODUTO", "QTD_PROGRAMADA", "QTD_REAL", "QTD_ADERENTE"], {}, None),
    "fPedido": ("pedido", {"NUMERO_PEDIDO": "int", "CLIENTE": "text", "CODIGO_PRODUTO": "int", "CODIGO_RECURSO": "text",
                           "QTD_PEDIDA": "num", "QTD_ENTREGUE": "num", "DATA_PROMETIDA": "date", "DATA_ENTREGA": "date",
                           "NO_PRAZO": "bool", "COMPLETO": "bool", "OTIF": "bool", "DIAS_ATRASO": "int"},
                ["CODIGO_PRODUTO", "CODIGO_RECURSO"], {}, None),
    "fPerdasTempo": ("an_perdas_tempo", {"ANO_MES": "text", "CODIGO_RECURSO": "text", "ORDEM": "int", "ETAPA": "text",
                                         "TIPO": "text", "HORAS": "num"}, ["ANO_MES", "CODIGO_RECURSO", "ORDEM", "HORAS"],
                     {"ETAPA": "ORDEM"}, None),
    "fIndicador": ("an_kpi_mensal", {"ANO_MES": "text", "ESCOPO": "text", "ORDEM_ESCOPO": "int", "CODIGO": "text",
                                     "FAMILIA": "text", "INDICADOR": "text", "UNIDADE": "text", "SENTIDO": "text", "VALOR": "num", "META": "num",
                                     "STATUS": "text"}, ["ANO_MES", "ORDEM_ESCOPO", "VALOR", "META", "SENTIDO"], {"ESCOPO": "ORDEM_ESCOPO"}, None),
}

RELACOES = [
    ("dCalendario.ANO_MES", "dMes.ANO_MES"),
    ("fProducaoTurno.DATA", "dCalendario.DATA"), ("fProducaoTurno.CODIGO_RECURSO", "dRecurso.CODIGO_RECURSO"), ("fProducaoTurno.TURNO", "dTurno.TURNO"),
    ("fParada.DATA", "dCalendario.DATA"), ("fParada.CODIGO_RECURSO", "dRecurso.CODIGO_RECURSO"), ("fParada.TURNO", "dTurno.TURNO"),
    ("fRefugoDefeito.DATA", "dCalendario.DATA"), ("fRefugoDefeito.CODIGO_RECURSO", "dRecurso.CODIGO_RECURSO"),
    ("fRefugoDefeito.CODIGO_PRODUTO", "dProduto.CODIGO_PRODUTO"), ("fRefugoDefeito.TURNO", "dTurno.TURNO"),
    ("fProgramaDia.DATA", "dCalendario.DATA"), ("fProgramaDia.CODIGO_RECURSO", "dRecurso.CODIGO_RECURSO"),
    ("fProgramaDia.CODIGO_PRODUTO", "dProduto.CODIGO_PRODUTO"),
    ("fPedido.DATA_PROMETIDA", "dCalendario.DATA"), ("fPedido.CODIGO_PRODUTO", "dProduto.CODIGO_PRODUTO"),
    ("fPedido.CODIGO_RECURSO", "dRecurso.CODIGO_RECURSO"),
    ("fPerdasTempo.ANO_MES", "dMes.ANO_MES"), ("fPerdasTempo.CODIGO_RECURSO", "dRecurso.CODIGO_RECURSO"),
    ("fIndicador.ANO_MES", "dMes.ANO_MES"),
]

PCT, INT, DEC, REAIS = "0.0%", "#,##0", "#,##0.0", r"\R\$ #,##0"
# tabela -> [(medida, formato, DAX)]
MEDIDAS = {
    "fProducaoTurno": [
        ("Disponibilidade", PCT, "DIVIDE(SUM(fProducaoTurno[TEMPO_PRODUZINDO_MIN]), SUM(fProducaoTurno[TEMPO_PROGRAMADO_MIN]))"),
        ("Performance", PCT, "DIVIDE(SUM(fProducaoTurno[TEMPO_TEORICO_MIN]), SUM(fProducaoTurno[TEMPO_PRODUZINDO_MIN]))"),
        ("Qualidade", PCT, "DIVIDE(SUM(fProducaoTurno[QTD_BOA]), SUM(fProducaoTurno[QTD_PRODUZIDA]))"),
        ("OEE", PCT, "[Disponibilidade] * [Performance] * [Qualidade]"),
        ("Meta OEE", PCT, "0.75"),
        ("Peças boas", INT, "SUM(fProducaoTurno[QTD_BOA])"),
        ("Peças produzidas", INT, "SUM(fProducaoTurno[QTD_PRODUZIDA])"),
        ("Refugo %", "0.00%", "DIVIDE(SUM(fProducaoTurno[QTD_REFUGO]), SUM(fProducaoTurno[QTD_PRODUZIDA]))"),
        ("FPY", PCT, "DIVIDE(SUM(fProducaoTurno[QTD_BOA]) - SUM(fProducaoTurno[QTD_RETRABALHO]), SUM(fProducaoTurno[QTD_PRODUZIDA]))"),
        ("Toneladas transformadas", DEC, "SUM(fProducaoTurno[KG_TRANSFORMADO]) / 1000"),
        ("Horas paradas não planejadas", INT, "SUM(fProducaoTurno[PARADA_NAO_PLANEJADA_MIN]) / 60"),
        ("Parada não planejada %", PCT, "DIVIDE(SUM(fProducaoTurno[PARADA_NAO_PLANEJADA_MIN]), SUM(fProducaoTurno[TEMPO_PROGRAMADO_MIN]))"),
        ("MTBF (h)", DEC, "DIVIDE(SUM(fProducaoTurno[TEMPO_PRODUZINDO_MIN]) / 60, SUM(fProducaoTurno[N_QUEBRAS]))"),
        ("MTTR (min)", DEC, "DIVIDE(SUM(fProducaoTurno[QUEBRA_MIN]), SUM(fProducaoTurno[N_QUEBRAS]))"),
        ("Quebras", INT, "SUM(fProducaoTurno[N_QUEBRAS])"),
        ("Custo do refugo", REAIS, "SUM(fProducaoTurno[CUSTO_REFUGO])"),
        ("Custo das paradas", REAIS, "SUM(fProducaoTurno[CUSTO_PARADA])"),
    ],
    "fParada": [
        ("Horas de parada não planejada", DEC, "CALCULATE(SUM(fParada[DURACAO_MIN]), fParada[PLANEJADA] = FALSE()) / 60"),
        ("Paradas não planejadas", INT, "CALCULATE(COUNTROWS(fParada), fParada[PLANEJADA] = FALSE())"),
    ],
    "fRefugoDefeito": [
        ("Peças refugadas", INT, "SUM(fRefugoDefeito[QTD_REFUGO])"),
        ("Custo do refugo por defeito", REAIS, "SUM(fRefugoDefeito[CUSTO_REFUGO])"),
    ],
    "fProgramaDia": [
        ("Qtd programada", INT, "SUM(fProgramaDia[QTD_PROGRAMADA])"),
        ("Qtd realizada", INT, "SUM(fProgramaDia[QTD_REAL])"),
        ("Aderência ao volume", PCT, "DIVIDE(SUM(fProgramaDia[QTD_REAL]), SUM(fProgramaDia[QTD_PROGRAMADA]))"),
        ("Aderência ao mix", PCT, "DIVIDE(SUM(fProgramaDia[QTD_ADERENTE]), SUM(fProgramaDia[QTD_PROGRAMADA]))"),
    ],
    "fPedido": [
        ("Pedidos", INT, "COUNTROWS(fPedido)"),
        ("OTIF %", PCT, "DIVIDE(CALCULATE(COUNTROWS(fPedido), fPedido[OTIF] = TRUE()), COUNTROWS(fPedido))"),
        ("No prazo %", PCT, "DIVIDE(CALCULATE(COUNTROWS(fPedido), fPedido[NO_PRAZO] = TRUE()), COUNTROWS(fPedido))"),
        ("Completo %", PCT, "DIVIDE(CALCULATE(COUNTROWS(fPedido), fPedido[COMPLETO] = TRUE()), COUNTROWS(fPedido))"),
        ("Meta OTIF", PCT, "0.9"),
        ("Pedidos fora do OTIF", INT, "CALCULATE(COUNTROWS(fPedido), fPedido[OTIF] = FALSE())"),
    ],
    "fPerdasTempo": [("Horas de calendário", INT, "SUM(fPerdasTempo[HORAS])")],
    "fIndicador": [
        ("Valor do indicador", None, [
            "VAR v = SELECTEDVALUE(fIndicador[VALOR])",
            "VAR u = SELECTEDVALUE(fIndicador[UNIDADE])",
            "RETURN",
            "    IF(ISBLANK(v), BLANK(),",
            "        SWITCH(u, \"%\", FORMAT(v, \"0.0%\"), \"R$\", FORMAT(v, \"R$ #,##0\"), \"ppm\", FORMAT(v, \"#,##0\"),",
            "            \"un\", FORMAT(v, \"#,##0\"), \"item-dia\", FORMAT(v, \"#,##0\"), FORMAT(v, \"#,##0.0\") & \" \" & u))"]),
        ("Meta do indicador", None, [
            "VAR m = SELECTEDVALUE(fIndicador[META])",
            "VAR u = SELECTEDVALUE(fIndicador[UNIDADE])",
            "RETURN",
            "    IF(ISBLANK(m), \"sem meta\",",
            "        SWITCH(u, \"%\", FORMAT(m, \"0.0%\"), \"ppm\", FORMAT(m, \"#,##0\"), FORMAT(m, \"#,##0.0\") & \" \" & u))"]),
        ("Indicadores no alvo", INT, "CALCULATE(COUNTROWS(fIndicador), fIndicador[STATUS] = \"No alvo\")"),
        ("Indicadores críticos", INT, "CALCULATE(COUNTROWS(fIndicador), fIndicador[STATUS] = \"Crítico\")"),
    ],
}
MEDIDAS["Painel"] = [(nome, None, linhas) for nome, linhas in H.MEDIDAS_HTML.items()]
TABELA_DA_MEDIDA = {m[0]: t for t, ms in MEDIDAS.items() for m in ms}

PAGINAS = H.PAGINAS


# ----------------------------------------------------------------------------
def escrever(caminho, texto):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8", newline="\n")


def js(caminho, obj):
    escrever(caminho, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def q(n):
    return n if n.replace("_", "").isalnum() else "'" + n.replace("'", "''") + "'"


def tmdl_tabela(nome):
    arq, cols, ocultas, ordenar, extra = TABELAS[nome]
    L = [f"table {nome}", f"\tlineageTag: {tag(nome)}", ""]
    for med, fmt, dax in MEDIDAS.get(nome, []):
        if isinstance(dax, list):
            L.append(f"\tmeasure {q(med)} =")
            L += ["\t\t\t" + x for x in dax]
        else:
            L.append(f"\tmeasure {q(med)} = {dax}")
        if fmt:
            L.append(f"\t\tformatString: {fmt}")
        L += [f"\t\tlineageTag: {tag(nome, 'm', med)}", ""]
    for c, t in cols.items():
        L.append(f"\tcolumn {c}")
        L.append(f"\t\tdataType: {T[t][0]}")
        if ocultas == "*" or c in ocultas:
            L.append("\t\tisHidden")
        if t == "date":
            L.append("\t\tformatString: dd/mm/yyyy")
        elif t == "int":
            L.append("\t\tformatString: 0")
        L += [f"\t\tlineageTag: {tag(nome, 'c', c)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {c}"]
        if c in ordenar:
            L.append(f"\t\tsortByColumn: {ordenar[c]}")
        L += ["", "\t\tannotation SummarizationSetBy = Automatic", ""]
        if t == "date":
            L += ["\t\tannotation UnderlyingDateTimeDataType = Date", ""]
    lista = ", ".join(f'"{c}"' for c in cols)
    tipos = ", ".join(f'{{"{c}", {T[t][1]}}}' for c, t in cols.items())
    L += [f"\tpartition {nome} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
          f'\t\t\t\t    Fonte = Parquet.Document(File.Contents(PastaExports & "{arq}.parquet")),',
          f"\t\t\t\t    Colunas = Table.SelectColumns(Fonte, {{{lista}}}),",
          f"\t\t\t\t    Tipos = Table.TransformColumnTypes(Colunas, {{{tipos}}})" + ("," if extra else "")]
    if extra:
        L.append(f"\t\t\t\t    Final = {extra}")
    L += ["\t\t\t\tin", f"\t\t\t\t    {'Final' if extra else 'Tipos'}", "", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(L)


def tmdl_painel():
    L = ["table Painel", f"\tlineageTag: {tag('Painel')}", ""]
    for med, _, dax in MEDIDAS["Painel"]:
        L.append(f"\tmeasure {q(med)} =")
        L += ["\t\t\t" + x for x in dax]
        L += [f"\t\tlineageTag: {tag('Painel', 'm', med)}", ""]
    L += ["\tcolumn Bloco", "\t\tdataType: string", "\t\tisHidden", f"\t\tlineageTag: {tag('Painel', 'c', 'Bloco')}",
          "\t\tsummarizeBy: none", "\t\tsourceColumn: Bloco", "", "\t\tannotation SummarizationSetBy = Automatic", "",
          "\tpartition Painel = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
          '\t\t\t\t    Fonte = #table(type table [Bloco = text], {{"HTML"}})', "\t\t\t\tin", "\t\t\t\t    Fonte", "",
          "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(L)


def modelo():
    d = PBI / f"{NOME}.SemanticModel"
    js(d / ".platform", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                         "metadata": {"type": "SemanticModel", "displayName": NOME}, "config": {"version": "2.0", "logicalId": tag("modelo")}})
    js(d / "definition.pbism", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                                "version": "4.2", "settings": {}})
    escrever(d / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1606\n\n")
    exp = d / "definition" / "expressions.tmdl"
    pasta = PASTA_PADRAO
    if exp.exists():                                         # preserva o caminho ja configurado nesta maquina
        import re
        m = re.search(r'PastaExports = "([^"]*)"', exp.read_text(encoding="utf-8"))
        pasta = m.group(1) if m else pasta
    escrever(exp, f'expression PastaExports = "{pasta}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
                  f"\tlineageTag: {tag('PastaExports')}\n\n\tannotation PBI_ResultType = Text\n\n")
    ordem = json.dumps(["PastaExports"] + list(TABELAS) + ["Painel"])
    escrever(d / "definition" / "model.tmdl", "\n".join([
        "model Model", "\tculture: pt-BR", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: pt-BR", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
        "annotation __PBI_TimeIntelligenceEnabled = 0", "", f"annotation PBI_QueryOrder = {ordem}", "",
        "annotation PBI_ProTooling = [\"DevMode\"]", ""] + [f"ref table {t}" for t in list(TABELAS) + ["Painel"]] + ["", ""]))
    escrever(d / "definition" / "relationships.tmdl", "\n".join(
        f"relationship {tag('rel', a, b)}\n\tfromColumn: {a}\n\ttoColumn: {b}\n" for a, b in RELACOES) + "\n")
    for t in TABELAS:
        escrever(d / "definition" / "tables" / f"{t}.tmdl", tmdl_tabela(t))
    escrever(d / "definition" / "tables" / "Painel.tmdl", tmdl_painel())


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def campo(spec):
    nome, _, rot = spec.partition("|")
    if "." in nome and nome.split(".")[0] in TABELAS:
        tab, col = nome.split(".", 1)
        f = {"Column": {"Expression": {"SourceRef": {"Entity": tab}}, "Property": col}}
    else:
        tab, col = TABELA_DA_MEDIDA[nome], nome
        f = {"Measure": {"Expression": {"SourceRef": {"Entity": tab}}, "Property": col}}
    p = {"field": f, "queryRef": f"{tab}.{col}", "nativeQueryRef": rot or col}
    if rot:
        p["displayName"] = rot
    return p


def cor(v):
    return {"solid": {"color": lit("'" + v + "'")}}


def visual(pag, i, spec):
    tipo, x, y, w, h, titulo, papeis, ordenar = spec
    nome = hashlib.sha1(f"{pag}/{i}/{tipo}/{papeis}".encode()).hexdigest()[:20]
    c = H.C
    objs = {}
    cont = {"title": [{"properties": {"show": lit("true"), "text": lit("'" + titulo.replace("'", "''") + "'")} if titulo
                      else {"show": lit("false")}}]}
    if tipo == "html":                                       # medida que devolve HTML, no visual HTML Content
        tipo = H.VISUAL_HTML
        query = {"queryState": {"content": {"projections": [campo(papeis)]}}}
        zero = {k: lit("0D") for k in ("top", "bottom", "left", "right")}
        cont.update({"background": [{"properties": {"show": lit("false")}}], "border": [{"properties": {"show": lit("false")}}],
                     "padding": [{"properties": zero}], "visualHeader": [{"properties": {"show": lit("false")}}]})
    else:
        query = {"queryState": {papel: {"projections": [campo(x_) for x_ in campos]} for papel, campos in papeis.items()}}
        if ordenar:
            query["sortDefinition"] = {"sort": [{"field": campo(ordenar)["field"], "direction": "Descending"}]}
        if tipo == "slicer":
            objs = {"data": [{"properties": {"mode": lit("'Dropdown'")}}],
                    "header": [{"properties": {"show": lit("true"), "fontColor": cor(c["tinta2"]), "textSize": lit("8D")}}],
                    "items": [{"properties": {"fontColor": cor(c["tinta"]), "background": cor(c["trilho"]), "textSize": lit("9D")}}]}
            cont.update({"background": [{"properties": {"show": lit("true"), "color": cor(c["trilho"]), "transparency": lit("0D")}}],
                         "border": [{"properties": {"show": lit("true"), "color": cor(c["linha"]), "radius": lit("8D")}}]})
        elif tipo == "clusteredColumnChart":
            objs = {"labels": [{"properties": {"show": lit("true"), "color": cor(c["tinta"])}}], "legend": [{"properties": {"show": lit("false")}}]}
        elif tipo == "lineChart":
            objs = {"legend": [{"properties": {"show": lit("true"), "position": lit("'Top'"), "labelColor": cor(c["tinta2"])}}]}
    return nome, {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json",
        "name": nome, "position": {"x": x, "y": y, "z": (i + 1) * 1000, "height": h, "width": w, "tabOrder": (i + 1) * 1000},
        "visual": {"visualType": tipo, "query": query, "objects": objs, "visualContainerObjects": cont, "drillFilterOtherVisuals": True}}


def eixo(c):
    return {"valueAxis": [{"gridlineColor": {"solid": {"color": c["linha"]}}, "labelColor": {"solid": {"color": c["tinta2"]}}, "showAxisTitle": False}],
            "categoryAxis": [{"labelColor": {"solid": {"color": c["tinta2"]}}, "showAxisTitle": False}]}


_c = H.C
TEMA = {
    "name": "Moldara PCP",
    "dataColors": [_c["ciano"], _c["lima"], _c["tinta"], _c["petroleo"], _c["lima2"], _c["coral"]],
    "background": _c["painel"], "foreground": _c["tinta"], "tableAccent": _c["ciano"],
    "foregroundNeutralSecondary": _c["tinta2"], "foregroundNeutralTertiary": _c["mudo"],
    "backgroundLight": _c["trilho"], "backgroundNeutral": _c["linha"],
    "good": _c["lima"], "neutral": _c["tinta"], "bad": _c["coral"],
    "textClasses": {"callout": {"fontFace": "Segoe UI Semibold", "color": _c["tinta"]},
                    "title": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": _c["tinta"]},
                    "header": {"fontFace": "Segoe UI Semibold", "fontSize": 10, "color": _c["tinta"]},
                    "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": _c["tinta2"]}},
    "visualStyles": {
        "*": {"*": {"background": [{"show": True, "color": {"solid": {"color": _c["painel"]}}, "transparency": 0}],
                    "border": [{"show": True, "color": {"solid": {"color": _c["painel"]}}, "radius": 12}],
                    "title": [{"fontColor": {"solid": {"color": _c["tinta"]}}, "fontSize": 11}],
                    "dropShadow": [{"show": False}]}},
        "lineChart": {"*": eixo(_c)}, "clusteredColumnChart": {"*": eixo(_c)},
        "page": {"*": {"background": [{"color": {"solid": {"color": _c["fundo"]}}, "transparency": 0}],
                       "outspace": [{"color": {"solid": {"color": _c["fundo"]}}, "transparency": 0}]}}},
}


def relatorio():
    d = PBI / f"{NOME}.Report"
    js(PBI / f"{NOME}.pbip", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
                              "version": "1.0", "artifacts": [{"report": {"path": f"{NOME}.Report"}}], "settings": {"enableAutoRecovery": True}})
    js(d / ".platform", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                         "metadata": {"type": "Report", "displayName": NOME}, "config": {"version": "2.0", "logicalId": tag("relatorio")}})
    js(d / "definition.pbir", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                               "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}}})
    js(d / "StaticResources" / "RegisteredResources" / "MoldaraPCP.json", TEMA)
    ver = {"visual": "2.11.0", "report": "3.4.0", "page": "2.3.1"}
    js(d / "definition" / "report.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY26SU07", "reportVersionAtImport": ver, "type": "SharedResources"},
                            "customTheme": {"name": "MoldaraPCP.json", "reportVersionAtImport": ver, "type": "RegisteredResources"}},
        "publicCustomVisuals": [H.VISUAL_HTML],
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources", "items": [{"name": "CY26SU07", "path": "BaseThemes/CY26SU07.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "MoldaraPCP.json", "path": "MoldaraPCP.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})
    js(d / "definition" / "version.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    js(d / "definition" / "pages" / "pages.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
                                                   "pageOrder": [p[0] for p in PAGINAS], "activePageName": PAGINAS[0][0]})
    for pid, titulo, visuais in PAGINAS:
        pasta = d / "definition" / "pages" / pid
        if (pasta / "visuals").exists():                   # apaga os visuais antigos da pagina
            for v in (pasta / "visuals").iterdir():
                shutil.rmtree(v, ignore_errors=True)
                if v.exists():                              # pasta sincronizada: o diretorio vazio sai na 2a tentativa
                    try:
                        v.rmdir()
                    except OSError:
                        pass
        js(pasta / "page.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
                                 "name": pid, "displayName": titulo, "displayOption": "FitToPage", "height": 720, "width": 1280,
                                 "objects": {k: [{"properties": {"color": cor(H.C["fundo"]), "transparency": lit("0D")}}]
                                             for k in ("background", "outspace")}})
        for i, spec in enumerate(visuais):
            nome, obj = visual(pid, i, spec)
            js(pasta / "visuals" / nome / "visual.json", obj)
    n = sum(len(p[2]) for p in PAGINAS)
    print(f"{NOME}: {len(TABELAS)} tabelas, {sum(len(m) for m in MEDIDAS.values())} medidas, {len(PAGINAS)} paginas, {n} visuais")


if __name__ == "__main__":
    modelo()
    relatorio()
    base = PBI / f"{NOME}.Report" / "StaticResources" / "SharedResources" / "BaseThemes" / "CY26SU07.json"
    if not base.exists():
        print(f"ATENCAO: falta o tema base do Power BI em {base}")
