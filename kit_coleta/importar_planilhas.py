"""Converte as planilhas de coleta preenchidas para o formato que o pipeline le (a pasta "brutos").

  python kit_coleta/importar_planilhas.py <pasta com as planilhas> <pasta de dados de destino>

Exemplo, com o exemplo que vem no kit:

  python kit_coleta/importar_planilhas.py kit_coleta/exemplo_preenchido dados_fabrica
  set PCP_DADOS=dados_fabrica          (PowerShell: $env:PCP_DADOS = "dados_fabrica")
  python executar_pipeline.py

O que o importador faz alem de copiar:
  * confere colunas obrigatorias e mostra, por planilha, quantas linhas leu e quais recusou
  * junta "Hora inicio" e "Hora fim" com a data do turno (3o turno atravessa a meia-noite)
  * calcula o tempo produzindo quando a maquina nao tem horimetro:
        tempo produzindo do turno = 480 min - paradas anotadas no diario de bordo
    repartido entre as ordens do turno na proporcao do tempo que cada uma ficou na maquina
  * ciclos = pecas produzidas / cavidades do roteiro
  * planilha opcional vazia ou ausente vira tabela vazia: os indicadores dela ficam sem valor,
    os outros continuam saindo
"""
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from esquema import MIN_TURNO, PLANILHAS, TURNOS

avisos = []


def ler(pasta, arquivo, aba):
    """Le uma aba pelo nome das colunas; devolve DataFrame so com as colunas do esquema."""
    _, colunas = PLANILHAS[arquivo]["abas"][aba]
    nomes = [c[0] for c in colunas]
    caminho = pasta / arquivo
    if not caminho.exists():
        avisos.append(f"{arquivo}: arquivo ausente, {aba} fica vazia")
        return pd.DataFrame(columns=nomes)
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        if aba not in wb.sheetnames:
            avisos.append(f"{arquivo}: aba {aba} ausente, fica vazia")
            return pd.DataFrame(columns=nomes)
        linhas = list(wb[aba].iter_rows(values_only=True))
    finally:
        wb.close()
    limpa = lambda r: [str(x).strip() if x is not None else "" for x in r]
    obrig = {c[0] for c in colunas if c[2]}
    h = next((i for i, r in enumerate(linhas[:20]) if obrig <= set(limpa(r))), None)
    if h is None:
        raise SystemExit(f"{arquivo} / {aba}: nao achei a linha de cabecalho com as colunas {sorted(obrig)}")
    cab = limpa(linhas[h])
    df = pd.DataFrame([r for r in linhas[h + 1:] if r and any(x not in (None, "") for x in r)], columns=cab)
    for n in nomes:
        if n not in df.columns:
            df[n] = None
    df = df[nomes]
    ruins = df[list(obrig)].isna().any(axis=1) | (df[list(obrig)].astype(str) == "").any(axis=1)
    if ruins.any():
        avisos.append(f"{arquivo} / {aba}: {int(ruins.sum())} linha(s) recusada(s) por campo obrigatorio em branco "
                      f"(primeira: linha {h + 2 + int(ruins.idxmax())} da planilha)")
    df = df[~ruins].reset_index(drop=True)
    for nome, tipo, _, _ in colunas:
        if tipo == "inteiro":
            df[nome] = pd.to_numeric(df[nome], errors="coerce").astype("Int64")
        elif tipo == "numero":
            df[nome] = pd.to_numeric(df[nome], errors="coerce").astype(float)
        elif tipo in ("data", "datahora"):
            df[nome] = pd.to_datetime(df[nome], errors="coerce", dayfirst=True)
        elif tipo == "texto":
            df[nome] = df[nome].map(lambda x: None if x is None else str(x).strip())
    print(f"  {arquivo} / {aba}: {len(df):,} linhas")
    return df


def hora(v):
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, time):
        return v
    h, m = str(v).strip().split(":")[:2]
    return time(int(h), int(m))


def instante(data, turno, hh):
    """Data do turno + hora. No 3o turno, hora antes das 22h pertence ao dia seguinte."""
    t = hora(hh)
    d = pd.Timestamp(data).normalize() + timedelta(hours=t.hour, minutes=t.minute)
    return d + timedelta(days=1) if int(turno) == 3 and t.hour < TURNOS[3] else d


def parquet(df, mapa, destino, tipos=None):
    out = df.rename(columns=mapa)[list(mapa.values())]
    for c, t in (tipos or {}).items():
        out[c] = out[c].astype(t)
    out.to_parquet(destino, index=False)


def planilha(caminho, aba, titulo, cab, linhas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = aba[0]
    for i, (a, t, c, ls) in enumerate(zip(aba, titulo, cab, linhas)):
        if i:
            ws = wb.create_sheet(a)
        ws.append([t])
        ws.append([])
        ws.append(c)
        for l in ls:
            ws.append(l)
    wb.save(caminho)


def nulo(v):
    return None if pd.isna(v) else v


def main(origem, destino):
    origem, destino = Path(origem), Path(destino)
    brutos = destino / "brutos"
    for sub in ("erp", "mes", "diario_bordo", "programa", "planilhas"):
        (brutos / sub).mkdir(parents=True, exist_ok=True)
        for f in (brutos / sub).iterdir():
            if f.is_file():
                f.unlink()
    print("Lendo as planilhas:")
    L = lambda arq, aba: ler(origem, arq, aba)
    erp = brutos / "erp"

    # ---- cadastros ----
    C = "01_Cadastros.xlsx"
    maq, prod, rot = L(C, "Máquinas"), L(C, "Produtos"), L(C, "Roteiros")
    parquet(maq.fillna({"Custo hora (R$)": 0.0}), {"Código": "CODIGO_RECURSO", "Descrição": "DESCRICAO", "Célula": "CELULA",
                                                  "Custo hora (R$)": "CUSTO_HORA"}, erp / "recursos.parquet")
    parquet(prod.fillna({"Peso (g)": 0.0, "Custo padrão (R$)": 0.0, "Preço de venda (R$)": 0.0}),
            {"Código": "CODIGO_PRODUTO", "Descrição": "DESCRICAO", "Família": "FAMILIA", "Célula": "CELULA", "Peso (g)": "PESO_G",
             "Custo padrão (R$)": "CUSTO_PADRAO", "Preço de venda (R$)": "PRECO_VENDA"}, erp / "produtos.parquet", {"CODIGO_PRODUTO": "int64"})
    parquet(rot.fillna({"Setup padrão (min)": 0.0}),
            {"Cód. produto": "CODIGO_PRODUTO", "Máquina": "CODIGO_RECURSO", "Ciclo padrão (s)": "CICLO_PADRAO_S", "Cavidades": "CAVIDADES",
             "Setup padrão (min)": "SETUP_PADRAO_MIN"}, erp / "roteiros.parquet", {"CODIGO_PRODUTO": "int64", "CAVIDADES": "int64"})
    parquet(L(C, "Materiais").fillna({"Lead time (dias)": 0}),
            {"Código": "CODIGO_MATERIAL", "Descrição": "DESCRICAO", "Unidade": "UNIDADE", "Custo unitário (R$)": "CUSTO_UNITARIO",
             "Lead time (dias)": "LEAD_TIME_DIAS"}, erp / "materiais.parquet", {"CODIGO_MATERIAL": "object", "LEAD_TIME_DIAS": "int64"})
    parquet(L(C, "Estrutura"), {"Cód. produto": "CODIGO_PRODUTO", "Cód. material": "CODIGO_MATERIAL", "Qtd. por peça": "QTD_POR_PECA"},
            erp / "estrutura.parquet", {"CODIGO_PRODUTO": "int64", "CODIGO_MATERIAL": "object"})
    parquet(L(C, "Clientes"), {"Código": "CODIGO_CLIENTE", "Razão social": "RAZAO_SOCIAL"}, erp / "clientes.parquet",
            {"CODIGO_CLIENTE": "int64", "RAZAO_SOCIAL": "object"})

    # ---- diario de bordo: regrava no formato de 1 planilha por mes ----
    D = "03_Diario de Bordo.xlsx"
    par, ref = L(D, "Paradas"), L(D, "Refugo")
    par["mes"] = par["Data"].dt.strftime("%Y-%m")
    ref["mes"] = ref["Data"].dt.strftime("%Y-%m")
    cab_p = ["Data", "Turno", "Máquina", "Hora início", "Duração (min)", "Motivo", "OP", "Líder"]
    cab_r = ["Data", "Turno", "Máquina", "OP", "Defeito", "Quantidade"]
    for mes in sorted(set(par["mes"].dropna()) | set(ref["mes"].dropna())):
        lp = [[r["Data"].to_pydatetime(), int(r["Turno"]), r["Máquina"], hora(r["Hora início"]).strftime("%H:%M"), int(r["Duração (min)"]),
               r["Motivo"], nulo(r["OP"]) and int(r["OP"]), nulo(r["Líder"])] for _, r in par[par["mes"] == mes].iterrows()]
        lr = [[r["Data"].to_pydatetime(), int(r["Turno"]), r["Máquina"], int(r["OP"]), r["Defeito"], int(r["Quantidade"])]
              for _, r in ref[ref["mes"] == mes].iterrows()]
        planilha(brutos / "diario_bordo" / f"Diario de Bordo_{mes}.xlsx", ["Paradas", "Refugo"],
                 [f"DIÁRIO DE BORDO - PARADAS - {mes}", f"DIÁRIO DE BORDO - REFUGO - {mes}"], [cab_p, cab_r], [lp, lr])

    # ---- apontamento -> CSV diario no formato do coletor ----
    ap = L("02_Apontamento de Producao.xlsx", "Apontamentos")
    if len(ap):
        ap["INICIO"] = [instante(d, t, h) for d, t, h in zip(ap["Data"], ap["Turno"], ap["Hora início"])]
        ap["FIM"] = [instante(d, t, h) for d, t, h in zip(ap["Data"], ap["Turno"], ap["Hora fim"])]
        ap.loc[ap["FIM"] <= ap["INICIO"], "FIM"] += timedelta(days=1)
        ap["dur"] = (ap["FIM"] - ap["INICIO"]).dt.total_seconds() / 60
        chave = ["Data", "Turno", "Máquina"]
        paradas = par.groupby(chave)["Duração (min)"].sum().rename("paradas").reset_index() if len(par) else pd.DataFrame(columns=chave + ["paradas"])
        ap = ap.merge(paradas, on=chave, how="left").fillna({"paradas": 0})
        soma = ap.groupby(chave)["dur"].transform("sum")
        calc = ((MIN_TURNO - ap["paradas"]).clip(lower=0).clip(upper=soma) * ap["dur"] / soma).round(1)
        sem = ap["Tempo produzindo (min)"].isna()
        ap["TEMPO"] = ap["Tempo produzindo (min)"].where(~sem, calc)
        print(f"  tempo produzindo: {int((~sem).sum())} linhas com horimetro, {int(sem.sum())} calculadas pelo diario de bordo")
        ap = ap.merge(rot[["Cód. produto", "Máquina", "Cavidades"]], on=["Cód. produto", "Máquina"], how="left")
        falta = ap["Cavidades"].isna()
        if falta.any():
            avisos.append(f"Apontamentos: {int(falta.sum())} linha(s) de produto x maquina sem roteiro no cadastro; o pipeline descarta essas linhas")
        fmt = "%d/%m/%Y %H:%M"
        for d, g in ap.groupby(ap["Data"].dt.date):
            pd.DataFrame({
                "DATA": g["Data"].dt.strftime("%d/%m/%Y"), "TURNO": g["Turno"], "RECURSO": g["Máquina"], "OP": g["OP"],
                "PRODUTO": g["Cód. produto"], "OPERADOR": g["Operador"].fillna(0), "INICIO": g["INICIO"].dt.strftime(fmt),
                "FIM": g["FIM"].dt.strftime(fmt), "TEMPO_PRODUCAO_MIN": g["TEMPO"],
                "CICLOS": (g["Peças produzidas"] / g["Cavidades"].fillna(1)).round().astype("Int64"),
                "QTD_PRODUZIDA": g["Peças produzidas"], "QTD_REFUGO": g["Refugo"].fillna(0), "QTD_RETRABALHO": g["Retrabalho"].fillna(0),
            }).to_csv(brutos / "mes" / f"apontamento_{d:%Y%m%d}.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
    else:
        raise SystemExit("Sem apontamentos de producao nao ha o que calcular.")

    # ---- programa semanal: 1 planilha por semana ISO ----
    pg = L("04_Programa Semanal.xlsx", "PROGRAMA")
    cab_g = ["Data", "Máquina", "Seq.", "OP", "Cód. produto", "Produto", "Qtd. programada"]
    if len(pg):
        iso = pg["Data"].dt.isocalendar()
        pg["sem"] = iso["year"].astype(str) + "-S" + iso["week"].astype(str).str.zfill(2)
    for sem, g in (pg.groupby("sem") if len(pg) else []):
        lg = [[r["Data"].to_pydatetime(), r["Máquina"], int(r["Seq."]), int(r["OP"]), int(r["Cód. produto"]), nulo(r["Produto"]),
               int(r["Qtd. programada"])] for _, r in g.iterrows()]
        planilha(brutos / "programa" / f"Programa Semanal_{sem}.xlsx", ["PROGRAMA"], [f"PROGRAMA SEMANAL - {sem}"], [cab_g], [lg])
    if not len(pg):
        planilha(brutos / "programa" / "Programa Semanal_0000-S00.xlsx", ["PROGRAMA"], ["SEM PROGRAMA"], [cab_g], [[]])

    # ---- ordens e pedidos ----
    O = "05_Ordens e Pedidos.xlsx"
    ordens, pedidos = L(O, "Ordens"), L(O, "Pedidos")
    if not len(ordens):                                  # sem cadastro de ordens: cria uma por OP apontada
        g = ap.groupby("OP").agg(prod=("Cód. produto", "first"), maq=("Máquina", "first"), ini=("INICIO", "min"), fim=("FIM", "max"),
                                 q=("Peças produzidas", "sum")).reset_index()
        ordens = pd.DataFrame({"OP": g["OP"], "Cód. produto": g["prod"], "Máquina": g["maq"], "Pedido": pd.NA, "Qtd. planejada": g["q"],
                               "Data de abertura": g["ini"].dt.normalize(), "Início programado": g["ini"], "Fim programado": g["fim"],
                               "Data de necessidade": g["fim"].dt.normalize(), "Status": "Encerrada", "Data de encerramento": g["fim"]})
        avisos.append("Ordens: planilha vazia; criei uma ordem por OP apontada, so para o pipeline rodar. Pontualidade e atraso nao valem.")
    ordens["Pedido"] = pd.to_numeric(ordens["Pedido"], errors="coerce").astype("Int64").fillna(0)
    parquet(ordens, {"OP": "NUMERO_OP", "Cód. produto": "CODIGO_PRODUTO", "Máquina": "CODIGO_RECURSO", "Pedido": "NUMERO_PEDIDO",
                     "Qtd. planejada": "QTD_PLANEJADA", "Data de abertura": "DATA_ABERTURA", "Início programado": "INICIO_PROGRAMADO",
                     "Fim programado": "FIM_PROGRAMADO", "Data de necessidade": "DATA_NECESSIDADE", "Status": "STATUS",
                     "Data de encerramento": "DATA_ENCERRAMENTO"}, erp / "ordens_producao.parquet",
            {"NUMERO_OP": "int64", "CODIGO_PRODUTO": "int64", "NUMERO_PEDIDO": "int64", "QTD_PLANEJADA": "int64",
             "DATA_ABERTURA": "datetime64[ns]", "INICIO_PROGRAMADO": "datetime64[ns]", "FIM_PROGRAMADO": "datetime64[ns]",
             "DATA_NECESSIDADE": "datetime64[ns]", "DATA_ENCERRAMENTO": "datetime64[ns]", "STATUS": "object", "CODIGO_RECURSO": "object"})
    parquet(pedidos, {"Pedido": "NUMERO_PEDIDO", "Cód. cliente": "CODIGO_CLIENTE", "Cód. produto": "CODIGO_PRODUTO", "Qtd. pedida": "QTD_PEDIDA",
                      "Data do pedido": "DATA_PEDIDO", "Data prometida": "DATA_PROMETIDA", "Data de entrega": "DATA_ENTREGA",
                      "Qtd. entregue": "QTD_ENTREGUE"}, erp / "pedidos_venda.parquet",
            {"NUMERO_PEDIDO": "int64", "CODIGO_CLIENTE": "int64", "CODIGO_PRODUTO": "int64", "QTD_PEDIDA": "int64",
             "DATA_PEDIDO": "datetime64[ns]", "DATA_PROMETIDA": "datetime64[ns]", "DATA_ENTREGA": "datetime64[ns]", "QTD_ENTREGUE": "Int64"})

    # ---- materiais e estoque ----
    M = "06_Materiais e Estoque.xlsx"
    parquet(L(M, "Requisições"), {"Data": "DATA", "OP": "NUMERO_OP", "Cód. material": "CODIGO_MATERIAL", "Quantidade": "QUANTIDADE"},
            erp / "requisicoes_material.parquet", {"DATA": "datetime64[ns]", "NUMERO_OP": "int64", "CODIGO_MATERIAL": "object", "QUANTIDADE": "float64"})
    parquet(L(M, "Saldo diário"), {"Data": "DATA", "Código do item": "CODIGO_ITEM", "Tipo": "TIPO_ITEM", "Saldo": "SALDO",
                                   "Custo unitário": "CUSTO_UNITARIO"}, erp / "estoque_diario.parquet",
            {"DATA": "datetime64[ns]", "CODIGO_ITEM": "object", "TIPO_ITEM": "object", "SALDO": "float64", "CUSTO_UNITARIO": "float64"})
    inv = L(M, "Inventário")
    planilha(brutos / "planilhas" / "Inventario Ciclico_2026.xlsx", ["CONTAGENS"], ["INVENTÁRIO CÍCLICO"],
             [["Data", "Código do item", "Tipo", "Saldo sistema", "Qtd. contada", "Contador"]],
             [[[r["Data"].to_pydatetime(), str(r["Código do item"]), r["Tipo"], float(r["Saldo sistema"]), float(r["Qtd. contada"]),
                nulo(r["Contador"])] for _, r in inv.iterrows()]])

    # ---- pessoas e previsao ----
    P = "07_Pessoas e Previsao.xlsx"
    pt = L(P, "Ponto")
    pd.DataFrame({"DATA": pt["Data"].dt.strftime("%d/%m/%Y") if len(pt) else [], "TURNO": pt["Turno"], "CELULA": pt["Célula"],
                  "QUADRO_PREVISTO": pt["Quadro previsto"], "PRESENTES": pt["Presentes"], "HORAS_NORMAIS": pt["Horas normais"],
                  "HORAS_EXTRAS": pt["Horas extras"]}).to_csv(brutos / "planilhas" / "ponto_horas_trabalhadas.csv", sep=";", decimal=",",
                                                              index=False, encoding="utf-8-sig")
    pv = L(P, "Previsão")
    meses = sorted(pv["Mês"].dropna().unique()) if len(pv) else [ap["Data"].min().strftime("%Y-%m")]
    larga = pv.pivot_table(index="Cód. produto", columns="Mês", values="Qtd. prevista", aggfunc="sum") if len(pv) else pd.DataFrame()
    nomes = dict(zip(prod["Código"], prod["Descrição"]))
    planilha(brutos / "planilhas" / "Previsao de Vendas_2026.xlsx", ["PREVISAO"], ["PREVISÃO DE VENDAS"], [["Cód. produto", "Produto"] + list(meses)],
             [[[int(c), nomes.get(c, "")] + [None if pd.isna(larga.loc[c, m]) else int(larga.loc[c, m]) for m in meses] for c in larga.index]])

    print(f"\nGravado em {brutos}")
    if avisos:
        print("\nAvisos:")
        for a in avisos:
            print("  -", a)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
