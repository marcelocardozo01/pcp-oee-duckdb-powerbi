"""Gera a base ficticia da Moldara Embalagens (fabrica de embalagens plasticas).

Tudo aqui e inventado: empresa, maquinas, produtos, clientes, operadores e numeros.
A semente e fixa, entao a base sai sempre igual.

O gerador simula o chao de fabrica turno a turno (12 maquinas, 3 celulas, 6 meses)
e grava os dados do jeito que cada origem entregaria na vida real:

  dados/brutos/erp/          parquet  cadastros, ordens, pedidos, requisicoes, estoque
  dados/brutos/mes/          csv      apontamento automatico do coletor, 1 arquivo por dia
  dados/brutos/diario_bordo/ xlsx     paradas e refugo digitados pelo lider, 1 arquivo por mes
  dados/brutos/programa/     xlsx     programa semanal do PCP, 1 arquivo por semana
  dados/brutos/planilhas/    xlsx/csv inventario ciclico, previsao de vendas, ponto (RH)

Uso: python gerador/gerar_dados.py
"""
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
BRUTOS = RAIZ / "dados" / "brutos"
rng = np.random.default_rng(2026)

INICIO, FIM = date(2026, 5, 1), date(2026, 10, 31)
FERIADOS = {date(2026, 5, 1), date(2026, 6, 4), date(2026, 9, 7), date(2026, 10, 12)}
HORA_TURNO = {1: 6, 2: 14, 3: 22}
MIN_TURNO = 480

# ----------------------------------------------------------------------------
# Cadastros
# ----------------------------------------------------------------------------
# codigo, descricao, celula, eventos de parada por turno, fator de ciclo, taxa de refugo, custo hora (R$)
RECURSOS = [
    ("INJ-01", "Injetora 180 t", "Injeção", 1.25, 1.05, 0.018, 185.0),
    ("INJ-02", "Injetora 180 t", "Injeção", 1.35, 1.06, 0.020, 185.0),
    ("INJ-03", "Injetora 250 t", "Injeção", 1.45, 1.08, 0.025, 230.0),
    ("INJ-04", "Injetora 250 t", "Injeção", 1.25, 1.05, 0.020, 230.0),
    ("INJ-05", "Injetora 350 t", "Injeção", 2.30, 1.14, 0.045, 290.0),
    ("SOP-01", "Sopradora 2 cavidades", "Sopro", 1.45, 1.07, 0.030, 210.0),
    ("SOP-02", "Sopradora 2 cavidades", "Sopro", 1.55, 1.08, 0.032, 210.0),
    ("SOP-03", "Sopradora 4 cavidades", "Sopro", 1.35, 1.06, 0.028, 260.0),
    ("SOP-04", "Sopradora de galões", "Sopro", 1.95, 1.12, 0.040, 280.0),
    ("DEC-01", "Serigrafia rotativa", "Decoração", 1.35, 1.09, 0.022, 120.0),
    ("DEC-02", "Serigrafia rotativa", "Decoração", 1.45, 1.10, 0.025, 120.0),
    ("DEC-03", "Rotuladora automática", "Decoração", 1.25, 1.07, 0.020, 140.0),
]
# A INJ-05 passa por uma reforma em agosto e melhora dali em diante.
REFORMA_INJ05 = date(2026, 8, 17)
# Quinzena de julho com falta de resina no mercado.
CRISE_RESINA = (date(2026, 7, 6), date(2026, 7, 17))

# codigo, descricao, familia, celula, peso (g), custo padrao (R$/un), preco (R$/un), ciclo (s), cavidades, maquinas
PRODUTOS = [
    (1001, "Tampa flip-top 28 mm", "Tampas", "Injeção", 3.2, 0.052, 0.085, 14.0, 16, ["INJ-01", "INJ-02"]),
    (1002, "Tampa rosca 38 mm", "Tampas", "Injeção", 4.1, 0.064, 0.105, 15.0, 16, ["INJ-01", "INJ-02", "INJ-03"]),
    (1003, "Tampa disc-top 24 mm", "Tampas", "Injeção", 2.8, 0.049, 0.082, 13.0, 24, ["INJ-03", "INJ-04"]),
    (1004, "Tampa galão 5 L com lacre", "Tampas", "Injeção", 9.5, 0.138, 0.220, 18.0, 8, ["INJ-04", "INJ-05"]),
    (1005, "Válvula dosadora", "Componentes", "Injeção", 1.9, 0.041, 0.074, 12.0, 24, ["INJ-03", "INJ-04"]),
    (1006, "Alça para galão", "Componentes", "Injeção", 12.0, 0.165, 0.260, 20.0, 8, ["INJ-05"]),
    (1007, "Pote 250 g com tampa", "Potes", "Injeção", 18.5, 0.262, 0.410, 22.0, 4, ["INJ-05", "INJ-03"]),
    (2001, "Frasco 500 mL PEAD natural", "Frascos", "Sopro", 28.0, 0.385, 0.590, 11.0, 2, ["SOP-01", "SOP-02"]),
    (2002, "Frasco 1 L PEAD natural", "Frascos", "Sopro", 42.0, 0.560, 0.860, 12.5, 2, ["SOP-01", "SOP-02", "SOP-03"]),
    (2003, "Frasco 1 L PEAD branco", "Frascos", "Sopro", 42.0, 0.585, 0.900, 12.5, 4, ["SOP-03"]),
    (2004, "Frasco 2 L PEAD branco", "Frascos", "Sopro", 68.0, 0.910, 1.380, 14.0, 4, ["SOP-03", "SOP-02"]),
    (2005, "Galão 5 L PEAD natural", "Galões", "Sopro", 135.0, 1.780, 2.650, 17.0, 1, ["SOP-04"]),
    (2006, "Galão 5 L PEAD azul", "Galões", "Sopro", 135.0, 1.830, 2.720, 17.0, 1, ["SOP-04"]),
    (3001, "Frasco 500 mL serigrafado", "Decorados", "Decoração", 28.0, 0.455, 0.720, 1.3, 1, ["DEC-01", "DEC-02"]),
    (3002, "Frasco 1 L serigrafado", "Decorados", "Decoração", 42.0, 0.645, 1.010, 1.5, 1, ["DEC-01", "DEC-02"]),
    (3003, "Frasco 2 L rotulado", "Decorados", "Decoração", 68.0, 0.985, 1.520, 1.8, 1, ["DEC-03"]),
    (3004, "Galão 5 L rotulado", "Decorados", "Decoração", 135.0, 1.905, 2.890, 2.4, 1, ["DEC-03"]),
]
SETUP_PADRAO = {"Injeção": 75, "Sopro": 55, "Decoração": 25}

# codigo, descricao, unidade, custo (R$), lead time de compra (dias)
MATERIAIS = [
    ("MP-PP-H", "Polipropileno homopolímero", "kg", 8.40, 6),
    ("MP-PP-C", "Polipropileno copolímero", "kg", 9.10, 6),
    ("MP-PEAD", "Polietileno de alta densidade (sopro)", "kg", 8.90, 7),
    ("MP-MB-BR", "Masterbatch branco", "kg", 21.50, 10),
    ("MP-MB-AZ", "Masterbatch azul", "kg", 26.00, 10),
    ("MP-TINTA", "Tinta para serigrafia UV", "kg", 148.00, 12),
    ("MP-ROT", "Rótulo BOPP autoadesivo", "un", 0.038, 9),
]
# produto -> [(material, quantidade por peca)]  (kg por peca; rotulo em unidades)
def estrutura(prod):
    cod, _, fam, cel, peso = prod[0], prod[1], prod[2], prod[3], prod[4]
    kg = peso / 1000
    if cel == "Injeção":
        resina = "MP-PP-C" if cod in (1004, 1006, 1007) else "MP-PP-H"
        return [(resina, kg * 0.98), ("MP-MB-BR", kg * 0.02)]
    if cel == "Sopro":
        if cod in (2003, 2004):
            return [("MP-PEAD", kg * 0.97), ("MP-MB-BR", kg * 0.03)]
        if cod == 2006:
            return [("MP-PEAD", kg * 0.97), ("MP-MB-AZ", kg * 0.03)]
        return [("MP-PEAD", kg)]
    if cod in (3001, 3002):
        return [("MP-TINTA", 0.00035 if cod == 3001 else 0.00050)]
    return [("MP-ROT", 1.0)]

CLIENTES = [
    (501, "Lumar Higiene"), (502, "Casa Clara Produtos de Limpeza"), (503, "Brisa Química"),
    (504, "Solare Cosméticos"), (505, "Vitalim Indústria"), (506, "Aquaflor Saneantes"),
    (507, "Petalis Cuidados Pessoais"), (508, "Domus Care"), (509, "Quimera Laboratório"),
    (510, "Norte Limp Distribuição"),
]

# Motivos de parada: codigo, descricao, categoria, planejada, duracao media (min), peso, celulas, grafias na planilha
MOTIVOS = [
    ("P01", "Refeição", "Planejada", True, 30, 0, None, ["Refeição", "REFEICAO", "refeição", "Intervalo refeição"]),
    ("P02", "Manutenção preventiva", "Planejada", True, 180, 0, None, ["Manutenção preventiva", "PREVENTIVA", "Manut. preventiva"]),
    ("P03", "Sem programação", "Planejada", True, 0, 0, None, ["Sem programação", "SEM PROGRAMA", "Máquina sem programa"]),
    ("P04", "Reunião / DDS", "Planejada", True, 15, 0, None, ["DDS", "Reunião DDS", "dds"]),
    ("S01", "Troca de molde / ferramenta", "Setup", False, 0, 0, None, ["Troca de molde", "TROCA MOLDE", "Setup", "setup - troca de ferramenta", "Troca de tela"]),
    ("S02", "Troca de cor / material", "Setup", False, 30, 6, None, ["Troca de cor", "TROCA DE COR", "Troca de material", "Limpeza p/ troca de cor"]),
    ("M01", "Quebra mecânica", "Manutenção corretiva", False, 70, 10, None, ["Quebra mecânica", "QUEBRA MECANICA", "Manut. mecânica", "Mecânica"]),
    ("M02", "Quebra elétrica / eletrônica", "Manutenção corretiva", False, 55, 7, None, ["Quebra elétrica", "ELETRICA", "Falha elétrica", "Painel / CLP"]),
    ("M03", "Falha hidráulica", "Manutenção corretiva", False, 60, 5, ["Injeção"], ["Falha hidráulica", "VAZAMENTO DE OLEO", "Hidráulica"]),
    ("O01", "Ajuste de processo", "Processo", False, 22, 28, None, ["Ajuste de processo", "AJUSTE", "Regulagem", "Ajuste de parâmetros"]),
    ("O02", "Limpeza de molde / tela", "Processo", False, 25, 14, None, ["Limpeza de molde", "LIMPEZA MOLDE", "Limpeza de tela", "Limpeza"]),
    ("O03", "Aguardando liberação da qualidade", "Processo", False, 20, 8, None, ["Aguardando qualidade", "AG. QUALIDADE", "Liberação CQ"]),
    ("L01", "Falta de matéria-prima", "Materiais", False, 50, 7, None, ["Falta de matéria-prima", "FALTA MP", "Falta de resina", "Sem material"]),
    ("L02", "Falta de embalagem", "Materiais", False, 25, 4, None, ["Falta de embalagem", "FALTA CAIXA", "Sem caixa / palete"]),
    ("G01", "Falta de operador", "Pessoas", False, 35, 8, None, ["Falta de operador", "SEM OPERADOR", "Operador ausente"]),
    ("U01", "Falta de energia / utilidades", "Utilidades", False, 40, 4, None, ["Falta de energia", "QUEDA DE ENERGIA", "Sem ar comprimido", "Água gelada"]),
]
TEXTOS_SEM_DEPARA = ["outros", "ver com o líder", "parada", "??"]

DEFEITOS = {
    "Injeção": [("Rebarba", 24), ("Falha de injeção", 22), ("Chupado", 14), ("Mancha / contaminação", 13),
                ("Dimensional fora", 9), ("Início de processo", 18)],
    "Sopro": [("Parede fina", 21), ("Furo", 15), ("Rebarba", 17), ("Deformação", 14),
              ("Mancha / contaminação", 12), ("Início de processo", 21)],
    "Decoração": [("Falha de impressão", 30), ("Fora de registro", 24), ("Rótulo torto", 16),
                  ("Bolha no rótulo", 12), ("Risco / arranhão", 18)],
}
QUADRO = {"Injeção": 6, "Sopro": 5, "Decoração": 4}

REC = {r[0]: dict(codigo=r[0], descricao=r[1], celula=r[2], lam=r[3] * 1.6, fator=r[4] + 0.03, refugo=r[5], custo_hora=r[6]) for r in RECURSOS}
PROD = {p[0]: dict(codigo=p[0], descricao=p[1], familia=p[2], celula=p[3], peso=p[4], custo=p[5], preco=p[6],
                   ciclo=p[7], cav=p[8], maquinas=p[9], bom=estrutura(p)) for p in PRODUTOS}


def turnos_do_dia(maq, d):
    if d in FERIADOS or d.weekday() == 6:
        return []
    if d.weekday() == 5:
        return [1] if REC[maq]["celula"] != "Decoração" else []
    return [1, 2, 3]


def inicio_turno(d, turno):
    return datetime(d.year, d.month, d.day, HORA_TURNO[turno])


def proximo_dia_util(d, n=1):
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in FERIADOS:
            n -= 1
    return d


# ----------------------------------------------------------------------------
# Simulacao
# ----------------------------------------------------------------------------
ordens, programa, apontamentos, paradas, refugos = {}, [], [], [], []
EFIC_PLANO_DISP, EFIC_PLANO_RITMO = 0.80, 0.92 * 0.97
contador_op = [41000]


def nova_op(maq, ultimo_produto):
    cands = [p for p in PROD.values() if maq in p["maquinas"]]
    if len(cands) > 1 and ultimo_produto is not None:
        cands = [p for p in cands if p["codigo"] != ultimo_produto]
    pesos = np.array([1.0 / len(p["maquinas"]) + 0.5 for p in cands])
    p = cands[rng.choice(len(cands), p=pesos / pesos.sum())]
    taxa = p["cav"] * 60 / p["ciclo"]                                   # pecas por minuto no ciclo padrao
    dias = rng.uniform(0.8, 3.2)
    qtd = taxa * EFIC_PLANO_RITMO * dias * 3 * 450 * EFIC_PLANO_DISP
    mult = 1000 if qtd >= 20000 else 500 if qtd >= 5000 else 100
    qtd = int(max(mult, round(qtd / mult) * mult))
    contador_op[0] += 1
    op = dict(op=contador_op[0], produto=p["codigo"], maquina=maq, qtd=qtd,
              alvo=qtd * (rng.uniform(1.0, 1.03) if rng.random() < 0.88 else rng.uniform(0.90, 0.99)),
              boas=0, total=0, inicio_prog=None, fim_prog=None, inicio_real=None, fim_real=None,
              abertura=None, semana_prog=None, seq_prog=None)
    ordens[op["op"]] = op
    return op


def planejar_semana(maq, segunda, estado):
    """Programa semanal do PCP: enche a capacidade da semana com a fila + ordens novas."""
    dias = [segunda + timedelta(days=i) for i in range(7)]
    dias = [d for d in dias if INICIO <= d <= FIM and turnos_do_dia(maq, d)]
    if not dias:
        return
    cap = {d: len(turnos_do_dia(maq, d)) * 450 * EFIC_PLANO_DISP for d in dias}
    cap_total = dict(cap)
    seq = 0
    ultimo = estado["ultimo_produto"]

    def instante(d, usado):
        horas = len(turnos_do_dia(maq, d)) * 8 * min(1.0, usado / cap_total[d])
        return datetime(d.year, d.month, d.day, 6) + timedelta(hours=horas)

    def alocar(op, em_andamento):
        nonlocal seq, ultimo
        p = PROD[op["produto"]]
        ritmo = p["cav"] * 60 / p["ciclo"] * EFIC_PLANO_RITMO
        falta_min = max(0.0, (op["qtd"] - op["boas"]) / ritmo)
        setup = 0 if (em_andamento or ultimo == op["produto"]) else SETUP_PADRAO[p["celula"]]
        ultimo = op["produto"]
        seq += 1
        ini = fim = None
        for d in dias:
            if cap[d] <= 1:
                continue
            if setup > 0:
                usa = min(setup, cap[d])
                cap[d] -= usa
                setup -= usa
                if cap[d] <= 1:
                    continue
            if ini is None:
                ini = instante(d, cap_total[d] - cap[d])
            usa = min(falta_min, cap[d])
            if usa > 0:
                cap[d] -= usa
                falta_min -= usa
                programa.append(dict(semana=segunda, data=d, maquina=maq, seq=seq, op=op["op"],
                                     produto=op["produto"], qtd=usa * ritmo))
            if falta_min <= 0.01:
                fim = instante(d, cap_total[d] - cap[d])
                break
        if fim is None:                                    # passa da semana: estima o fim nos dias seguintes
            d = dias[-1]
            resto = falta_min + setup
            while resto > 0:
                d += timedelta(days=1)
                resto -= len(turnos_do_dia(maq, d)) * 450 * EFIC_PLANO_DISP
            fim = datetime(d.year, d.month, d.day, 18)
            if ini is None:
                ini = datetime(d.year, d.month, d.day, 6)
        if op["inicio_prog"] is None:
            op.update(inicio_prog=ini, fim_prog=fim, semana_prog=segunda, seq_prog=seq,
                      abertura=segunda - timedelta(days=int(rng.integers(3, 8))))

    if estado["atual"] is not None:
        alocar(estado["atual"], True)
    for op in estado["fila"]:
        alocar(op, False)
    while sum(cap.values()) > 120:
        op = nova_op(maq, ultimo)
        estado["fila"].append(op)
        alocar(op, False)


def duracao(media):
    return float(np.clip(rng.lognormal(np.log(media) - 0.18, 0.6), 4, 420))


def simular_turno(maq, d, turno, estado):
    r = REC[maq]
    cel = r["celula"]
    t0 = inicio_turno(d, turno)
    lam, fator, tx_ref = r["lam"], r["fator"], r["refugo"]
    if maq == "INJ-05" and d >= REFORMA_INJ05:
        lam, fator, tx_ref = 2.3, 1.10, 0.024
    if turno == 3:
        lam, tx_ref = lam * 1.18, tx_ref * 1.12
    crise = CRISE_RESINA[0] <= d <= CRISE_RESINA[1] and cel != "Decoração"

    # paradas planejadas
    planejadas = [("P01", 30.0)]
    if turno == 1 and d.weekday() == 0:
        planejadas.append(("P04", 15.0))
    if turno == 1 and d == estado["preventiva"]:
        planejadas.append(("P02", float(rng.integers(150, 241))))
        estado["preventiva"] = proximo_dia_util(d, int(rng.integers(22, 30)))
    carga = MIN_TURNO - sum(m for _, m in planejadas)

    # paradas nao planejadas (fora setup de troca de ordem)
    cands = [m for m in MOTIVOS if m[5] > 0 and (m[6] is None or cel in m[6])]
    pesos = np.array([m[5] * (5.0 if (crise and m[0] == "L01") else 1.0) for m in cands], dtype=float)
    n = rng.poisson(lam * (1.25 if crise else 1.0))
    nao_plan = []
    for _ in range(n):
        m = cands[rng.choice(len(cands), p=pesos / pesos.sum())]
        nao_plan.append((m[0], duracao(m[4])))
    while sum(x for _, x in nao_plan) > 0.62 * carga:
        nao_plan.pop()
    disponivel = carga - sum(x for _, x in nao_plan)

    # producao: consome a fila de ordens
    itens = []                                              # ("setup", min) | ("prod", min, apontamento)
    fator_turno = max(1.0, rng.normal(fator, 0.03))
    while disponivel > 1.0:
        if estado["setup_pendente"] > 0:
            usa = min(estado["setup_pendente"], disponivel)
            estado["setup_pendente"] -= usa
            disponivel -= usa
            itens.append(("setup", usa, None))
            continue
        if estado["atual"] is None:
            if not estado["fila"]:
                planejadas.append(("P03", disponivel))
                disponivel = 0
                break
            i = 1 if (len(estado["fila"]) > 1 and rng.random() < 0.07) else 0      # ordem urgente fura a fila
            op = estado["fila"].pop(i)
            estado["atual"] = op
            if estado["ultimo_produto"] not in (None, op["produto"]):
                estado["setup_pendente"] = duracao(SETUP_PADRAO[cel] * 1.1)
            estado["ultimo_produto"] = op["produto"]
            continue
        op = estado["atual"]
        p = PROD[op["produto"]]
        ciclo_real = p["ciclo"] * fator_turno
        tx = float(np.clip(rng.normal(tx_ref, tx_ref * 0.35), 0.002, 0.2))
        if op["total"] == 0:
            tx *= 1.6                                       # inicio de ordem refuga mais
        por_min_boas = p["cav"] * 60 / ciclo_real * (1 - tx)
        precisa = max(0.0, op["alvo"] - op["boas"]) / por_min_boas
        t = min(disponivel, precisa)
        ciclos = int(round(t * 60 / ciclo_real))
        total = ciclos * p["cav"]
        ref = int(round(total * tx))
        retrab = int(round(total * (rng.uniform(0.012, 0.030) if cel == "Decoração" else rng.uniform(0.002, 0.006))))
        boas = total - ref
        ap = dict(data=d, turno=turno, maquina=maq, op=op["op"], produto=op["produto"], operador=estado["operadores"][turno],
                  min_prod=t, ciclos=ciclos, total=total, refugo=ref, retrabalho=retrab)
        itens.append(("prod", t, ap))
        op["boas"] += boas
        op["total"] += total
        disponivel -= t
        if precisa <= t + 1e-6:
            ap["conclui"] = True
            estado["atual"] = None

    # linha do tempo do turno: distribui as paradas dentro dos trechos de producao
    soltas = planejadas + nao_plan
    prods = [i for i, it in enumerate(itens) if it[0] == "prod" and it[1] > 0]
    dentro = {i: [] for i in prods}
    fora = []
    for cod, m in soltas:
        if prods:
            w = np.array([itens[i][1] for i in prods])
            dentro[prods[rng.choice(len(prods), p=w / w.sum())]].append((cod, m))
        else:
            fora.append((cod, m))
    cursor = t0
    op_atual = [None]

    def grava_parada(cod, m, quando):
        paradas.append(dict(data=d, turno=turno, maquina=maq, motivo=cod, inicio=quando, minutos=m, op=op_atual[0]))

    for cod, m in fora:
        grava_parada(cod, m, cursor)
        cursor += timedelta(minutes=m)
    for i, (tipo, m, ap) in enumerate(itens):
        op_atual[0] = ap["op"] if ap else None
        if tipo == "setup":
            grava_parada("S01", m, cursor)
            cursor += timedelta(minutes=m)
            continue
        ps = dentro.get(i, [])
        cortes = np.sort(rng.uniform(0, m, len(ps)))
        ini = cursor
        feito = 0.0
        for (cod, pm), c in zip(ps, cortes):
            cursor += timedelta(minutes=float(c - feito))
            feito = float(c)
            grava_parada(cod, pm, cursor)
            cursor += timedelta(minutes=pm)
        cursor += timedelta(minutes=float(m - feito))
        ap.update(inicio=ini, fim=cursor)
        op = ordens[ap["op"]]
        if op["inicio_real"] is None:
            op["inicio_real"] = ini
        if ap.pop("conclui", False):
            op["fim_real"] = cursor
        apontamentos.append(ap)
        if ap["refugo"] > 0:
            defs = DEFEITOS[cel]
            w = np.array([x[1] for x in defs], dtype=float)
            partes = rng.multinomial(ap["refugo"], w / w.sum())
            for (nome, _), q in zip(defs, partes):
                if q > 0:
                    refugos.append(dict(data=d, turno=turno, maquina=maq, op=ap["op"], defeito=nome, qtd=int(q)))


def simular():
    mat = 7000
    estados = {}
    for maq in REC:
        ops = {}
        for t in (1, 2, 3):
            mat += 1
            ops[t] = mat
        estados[maq] = dict(atual=None, fila=[], ultimo_produto=None, setup_pendente=0.0, operadores=ops,
                            preventiva=proximo_dia_util(INICIO, int(rng.integers(3, 24))))
    d = INICIO
    while d <= FIM:
        for maq in REC:
            if d.weekday() == 0 or d == INICIO:
                planejar_semana(maq, d - timedelta(days=d.weekday()), estados[maq])
            for turno in turnos_do_dia(maq, d):
                simular_turno(maq, d, turno, estados[maq])
        d += timedelta(days=1)


# ----------------------------------------------------------------------------
# Saidas
# ----------------------------------------------------------------------------
def limpar():
    # apaga so os arquivos: em pasta sincronizada com a nuvem remover o diretorio costuma ser negado
    for sub in ("erp", "mes", "diario_bordo", "programa", "planilhas"):
        (BRUTOS / sub).mkdir(parents=True, exist_ok=True)
        for f in (BRUTOS / sub).iterdir():
            if f.is_file():
                f.unlink()


def gravar_erp(df_ap):
    erp = BRUTOS / "erp"
    pd.DataFrame([dict(CODIGO_RECURSO=r["codigo"], DESCRICAO=r["descricao"], CELULA=r["celula"],
                       CUSTO_HORA=r["custo_hora"]) for r in REC.values()]).to_parquet(erp / "recursos.parquet", index=False)
    pd.DataFrame([dict(CODIGO_PRODUTO=p["codigo"], DESCRICAO=p["descricao"], FAMILIA=p["familia"], CELULA=p["celula"],
                       PESO_G=p["peso"], CUSTO_PADRAO=p["custo"], PRECO_VENDA=p["preco"]) for p in PROD.values()]
                 ).to_parquet(erp / "produtos.parquet", index=False)
    pd.DataFrame([dict(CODIGO_PRODUTO=p["codigo"], CODIGO_RECURSO=m, CICLO_PADRAO_S=p["ciclo"], CAVIDADES=p["cav"],
                       SETUP_PADRAO_MIN=SETUP_PADRAO[p["celula"]]) for p in PROD.values() for m in p["maquinas"]]
                 ).to_parquet(erp / "roteiros.parquet", index=False)
    pd.DataFrame([dict(CODIGO_PRODUTO=p["codigo"], CODIGO_MATERIAL=m, QTD_POR_PECA=q) for p in PROD.values() for m, q in p["bom"]]
                 ).to_parquet(erp / "estrutura.parquet", index=False)
    pd.DataFrame([dict(CODIGO_MATERIAL=m[0], DESCRICAO=m[1], UNIDADE=m[2], CUSTO_UNITARIO=m[3], LEAD_TIME_DIAS=m[4])
                  for m in MATERIAIS]).to_parquet(erp / "materiais.parquet", index=False)
    pd.DataFrame([dict(CODIGO_CLIENTE=c, RAZAO_SOCIAL=n) for c, n in CLIENTES]).to_parquet(erp / "clientes.parquet", index=False)

    # ordens e pedidos (1 pedido por ordem: a fabrica produz contra pedido)
    linhas_op, linhas_ped = [], []
    for n, op in enumerate(sorted(ordens.values(), key=lambda o: o["op"])):
        if op["inicio_prog"] is None:
            continue
        status = "Encerrada" if op["fim_real"] else ("Em produção" if op["inicio_real"] else "Liberada")
        prometida = proximo_dia_util(op["fim_prog"].date() - timedelta(days=1), int(rng.choice([1, 1, 2, 2, 3])))
        pedido = 880000 + n
        linhas_op.append(dict(NUMERO_OP=op["op"], CODIGO_PRODUTO=op["produto"], CODIGO_RECURSO=op["maquina"],
                              NUMERO_PEDIDO=pedido, QTD_PLANEJADA=op["qtd"], DATA_ABERTURA=pd.Timestamp(op["abertura"]),
                              INICIO_PROGRAMADO=op["inicio_prog"], FIM_PROGRAMADO=op["fim_prog"],
                              DATA_NECESSIDADE=pd.Timestamp(prometida), STATUS=status,
                              DATA_ENCERRAMENTO=op["fim_real"]))
        entrega = qtd_ent = None
        if op["fim_real"]:
            base = op["fim_real"].date() if op["fim_real"].hour < 14 else op["fim_real"].date() + timedelta(days=1)
            entrega = proximo_dia_util(base - timedelta(days=1), 1 if rng.random() < 0.8 else 2)
            qtd_ent = int(op["boas"])
        linhas_ped.append(dict(NUMERO_PEDIDO=pedido, CODIGO_CLIENTE=int(rng.choice([c for c, _ in CLIENTES])),
                               CODIGO_PRODUTO=op["produto"], QTD_PEDIDA=op["qtd"],
                               DATA_PEDIDO=pd.Timestamp(op["abertura"] - timedelta(days=int(rng.integers(2, 9)))),
                               DATA_PROMETIDA=pd.Timestamp(prometida),
                               DATA_ENTREGA=pd.Timestamp(entrega) if entrega else pd.NaT,
                               QTD_ENTREGUE=qtd_ent))
    df_op = pd.DataFrame(linhas_op)
    df_ped = pd.DataFrame(linhas_ped)
    df_ped["QTD_ENTREGUE"] = df_ped["QTD_ENTREGUE"].astype("Int64")
    depois = df_ped["DATA_ENTREGA"] > pd.Timestamp(FIM)
    df_ped.loc[depois, "QTD_ENTREGUE"] = pd.NA
    df_ped.loc[depois, "DATA_ENTREGA"] = pd.NaT
    df_op.to_parquet(erp / "ordens_producao.parquet", index=False)
    df_ped.to_parquet(erp / "pedidos_venda.parquet", index=False)

    # requisicoes de material: consumo real por dia, ordem e material
    perda = {m: rng.uniform(0.005, 0.03) for m in REC}
    req = []
    for (d, op, maq, prod), g in df_ap.groupby(["data", "op", "maquina", "produto"]):
        for mp, q in PROD[prod]["bom"]:
            extra = 1.0 if mp == "MP-ROT" else 1 + perda[maq] + rng.uniform(0, 0.01)
            qtd = g["total"].sum() * q * extra
            req.append(dict(DATA=pd.Timestamp(d), NUMERO_OP=op, CODIGO_MATERIAL=mp,
                            QUANTIDADE=round(qtd, 0 if mp == "MP-ROT" else 2)))
    df_req = pd.DataFrame(req)
    df_req.to_parquet(erp / "requisicoes_material.parquet", index=False)

    # estoque diario: materia-prima (simulada com ponto de pedido) e produto acabado (producao - expedicao)
    dias = pd.date_range(INICIO, FIM)
    est = []
    cons = df_req.groupby(["CODIGO_MATERIAL", "DATA"])["QUANTIDADE"].sum()
    for cod, _, _, custo, lead in MATERIAIS:
        serie = cons[cod].reindex(dias, fill_value=0.0) if cod in cons.index.get_level_values(0) else pd.Series(0.0, dias)
        media = serie[serie > 0].mean()
        saldo = media * rng.uniform(9, 14)
        chegadas = {}
        for dia in dias:
            saldo += chegadas.pop(dia, 0.0)
            saldo = max(0.0, saldo - serie[dia])
            transito = sum(chegadas.values())
            if saldo + transito < media * (lead + 4):
                atraso = int(rng.choice([0, 0, 0, 1, 2, 4]))
                if CRISE_RESINA[0] - timedelta(days=8) <= dia.date() <= CRISE_RESINA[1] and cod.startswith(("MP-PP", "MP-PEAD")):
                    atraso += 5
                quando = dia + timedelta(days=lead + atraso)
                chegadas[quando] = chegadas.get(quando, 0.0) + media * rng.uniform(9, 13)
            est.append(dict(DATA=dia, CODIGO_ITEM=cod, TIPO_ITEM="Matéria-prima", SALDO=round(saldo, 2), CUSTO_UNITARIO=custo))
    prod_dia = df_ap.assign(boas=df_ap["total"] - df_ap["refugo"]).groupby(["produto", "data"])["boas"].sum()
    ent = df_ped.dropna(subset=["DATA_ENTREGA"]).groupby(["CODIGO_PRODUTO", "DATA_ENTREGA"])["QTD_ENTREGUE"].sum()
    for p in PROD.values():
        entra = prod_dia[p["codigo"]].reindex(dias.date, fill_value=0) if p["codigo"] in prod_dia.index.get_level_values(0) else pd.Series(0, dias.date)
        sai = ent[p["codigo"]].reindex(dias, fill_value=0) if p["codigo"] in ent.index.get_level_values(0) else pd.Series(0, dias)
        saldo = (entra.to_numpy().cumsum() - sai.to_numpy().astype(float).cumsum()).clip(min=0)
        for dia, s in zip(dias, saldo):
            est.append(dict(DATA=dia, CODIGO_ITEM=str(p["codigo"]), TIPO_ITEM="Produto acabado", SALDO=float(s), CUSTO_UNITARIO=p["custo"]))
    df_est = pd.DataFrame(est)
    df_est.to_parquet(erp / "estoque_diario.parquet", index=False)
    return df_op, df_ped, df_est


def gravar_mes(df_ap):
    """Coletor de chao de fabrica: 1 CSV por dia, separador ; e virgula decimal."""
    fmt = "%d/%m/%Y %H:%M"
    dup_dias = set(rng.choice(sorted(df_ap["data"].unique()), 3, replace=False))
    for d, g in df_ap.groupby("data"):
        out = pd.DataFrame({
            "DATA": pd.to_datetime(g["data"]).dt.strftime("%d/%m/%Y"), "TURNO": g["turno"], "RECURSO": g["maquina"],
            "OP": g["op"], "PRODUTO": g["produto"], "OPERADOR": g["operador"],
            "INICIO": g["inicio"].dt.strftime(fmt), "FIM": g["fim"].dt.strftime(fmt),
            "TEMPO_PRODUCAO_MIN": g["min_prod"].round(1), "CICLOS": g["ciclos"],
            "QTD_PRODUZIDA": g["total"], "QTD_REFUGO": g["refugo"], "QTD_RETRABALHO": g["retrabalho"]})
        if d in dup_dias:                                   # reenvio do coletor: linhas repetidas no arquivo
            out = pd.concat([out, out.sample(frac=0.25, random_state=7)])
        out.to_csv(BRUTOS / "mes" / f"apontamento_{d:%Y%m%d}.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")


def gravar_diario_bordo(df_ap):
    """Diario de bordo: o lider digita as paradas e o refugo por defeito numa planilha por mes."""
    grafias = {m[0]: m[7] for m in MOTIVOS}
    df_par = pd.DataFrame(paradas)
    df_ref = pd.DataFrame(refugos)
    # o lider erra a conta do refugo em alguns turnos (a planilha nao fecha com o contador)
    idx = df_ref.sample(frac=0.02, random_state=11).index
    df_ref.loc[idx, "qtd"] = (df_ref.loc[idx, "qtd"] * rng.uniform(0.6, 1.5, len(idx))).round().astype(int).clip(lower=1)
    lider = {"Injeção": {1: "Rui", 2: "Sandra", 3: "Tiago"}, "Sopro": {1: "Marta", 2: "Jonas", 3: "Ivo"},
             "Decoração": {1: "Lia", 2: "Caio", 3: "Nara"}}
    for mes, g in df_par.groupby(df_par["data"].map(lambda x: x.strftime("%Y-%m"))):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Paradas"
        ws.append([f"DIÁRIO DE BORDO - PARADAS DE MÁQUINA - {mes}"])
        ws.append(["Preencher uma linha por parada. Duração em minutos."])
        ws.append([])
        ws.append(["Data", "Turno", "Máquina", "Hora início", "Duração (min)", "Motivo", "OP", "Líder"])
        for r in g.sort_values(["data", "maquina", "inicio"]).itertuples():
            if not r.motivo.startswith("P") and r.minutos > 35 and rng.random() < 0.03:
                continue                                    # o lider esqueceu de anotar a parada
            texto = rng.choice(grafias[r.motivo])
            if not r.motivo.startswith("P") and rng.random() < 0.004:
                texto = rng.choice(TEXTOS_SEM_DEPARA)
            if rng.random() < 0.08:
                texto = f" {texto} "
            ws.append([datetime(r.data.year, r.data.month, r.data.day), r.turno, r.maquina, r.inicio.strftime("%H:%M"),
                       int(round(r.minutos)), str(texto), None if pd.isna(r.op) else int(r.op),
                       lider[REC[r.maquina]["celula"]][r.turno]])
        ws2 = wb.create_sheet("Refugo")
        ws2.append([f"DIÁRIO DE BORDO - REFUGO POR DEFEITO - {mes}"])
        ws2.append([])
        ws2.append(["Data", "Turno", "Máquina", "OP", "Defeito", "Quantidade"])
        gr = df_ref[df_ref["data"].map(lambda x: x.strftime("%Y-%m")) == mes]
        for r in gr.sort_values(["data", "maquina", "turno"]).itertuples():
            ws2.append([datetime(r.data.year, r.data.month, r.data.day), r.turno, r.maquina, r.op, r.defeito, r.qtd])
        wb.save(BRUTOS / "diario_bordo" / f"Diario de Bordo_{mes}.xlsx")


def gravar_programa():
    """Programa semanal do PCP: uma planilha por semana, uma linha por dia, maquina e ordem."""
    df = pd.DataFrame(programa)
    for semana, g in df.groupby("semana"):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "PROGRAMA"
        iso = semana.isocalendar()
        ws.append([f"PROGRAMA SEMANAL DE PRODUÇÃO - SEMANA {iso[1]:02d}/{iso[0]}"])
        ws.append([f"Emitido pelo PCP em {(semana - timedelta(days=3)):%d/%m/%Y}", None, None, "Revisão", 0])
        ws.append([])
        ws.append(["Data", "Máquina", "Seq.", "OP", "Cód. produto", "Produto", "Qtd. programada"])
        for r in g.sort_values(["maquina", "seq", "data"]).itertuples():
            ws.append([datetime(r.data.year, r.data.month, r.data.day), r.maquina, r.seq, r.op, r.produto,
                       PROD[r.produto]["descricao"], int(round(r.qtd))])
        wb.save(BRUTOS / "programa" / f"Programa Semanal_{iso[0]}-S{iso[1]:02d}.xlsx")


def gravar_planilhas(df_ap, df_ped, df_est):
    pl = BRUTOS / "planilhas"
    # ponto (RH): presentes e horas por dia, turno e celula
    linhas = []
    for (d, turno, cel), _ in df_ap.assign(cel=df_ap["maquina"].map(lambda m: REC[m]["celula"])).groupby(["data", "turno", "cel"]):
        quadro = QUADRO[cel]
        ausentes = int(rng.binomial(quadro, 0.038 if turno != 3 else 0.055))
        presentes = quadro - ausentes
        sabado = d.weekday() == 5
        normais = 0.0 if sabado else presentes * 7.5
        extras = presentes * 7.5 if sabado else (presentes * rng.uniform(0.5, 2.0) if rng.random() < 0.18 else 0.0)
        linhas.append(dict(DATA=d.strftime("%d/%m/%Y"), TURNO=turno, CELULA=cel, QUADRO_PREVISTO=quadro,
                           PRESENTES=presentes, HORAS_NORMAIS=round(normais, 1), HORAS_EXTRAS=round(extras, 1)))
    pd.DataFrame(linhas).to_csv(pl / "ponto_horas_trabalhadas.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")

    # inventario ciclico: conferencia semanal de alguns itens contra o saldo do sistema
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CONTAGENS"
    ws.append(["INVENTÁRIO CÍCLICO - CONTAGENS 2026"])
    ws.append([])
    ws.append(["Data", "Código do item", "Tipo", "Saldo sistema", "Qtd. contada", "Contador"])
    itens = df_est["CODIGO_ITEM"].unique()
    for dia in pd.date_range(INICIO, FIM, freq="W-FRI"):
        if dia.date() in FERIADOS:
            continue
        for cod in rng.choice(itens, 9, replace=False):
            linha = df_est[(df_est["DATA"] == dia) & (df_est["CODIGO_ITEM"] == cod)].iloc[0]
            if linha["SALDO"] <= 0:
                continue
            erro = rng.normal(0, 0.006) if rng.random() < 0.86 else rng.normal(0, 0.06)
            contado = max(0.0, linha["SALDO"] * (1 + erro))
            casas = 2 if linha["TIPO_ITEM"] == "Matéria-prima" and cod != "MP-ROT" else 0
            ws.append([dia.to_pydatetime(), cod, linha["TIPO_ITEM"], round(float(linha["SALDO"]), casas),
                       round(float(contado), casas), str(rng.choice(["Almox 1", "Almox 2", "Expedição"]))])
    wb.save(pl / "Inventario Ciclico_2026.xlsx")

    # previsao de vendas do comercial: produtos nas linhas, meses nas colunas
    real = df_ped.assign(MES=df_ped["DATA_PROMETIDA"].dt.strftime("%Y-%m")).groupby(["CODIGO_PRODUTO", "MES"])["QTD_PEDIDA"].sum()
    meses = [m.strftime("%Y-%m") for m in pd.date_range(INICIO, FIM, freq="MS")]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PREVISAO"
    ws.append(["PREVISÃO DE VENDAS (S&OP) - unidades por mês de entrega"])
    ws.append([])
    ws.append(["Cód. produto", "Produto"] + meses)
    for p in PROD.values():
        linha = [p["codigo"], p["descricao"]]
        for m in meses:
            r = real.get((p["codigo"], m), 0)
            base = r if r > 0 else p["cav"] * 60 / p["ciclo"] * 60 * 24 * 2
            prev = base * rng.lognormal(0.03, 0.17)
            linha.append(int(round(prev, -3)))
        ws.append(linha)
    wb.save(pl / "Previsao de Vendas_2026.xlsx")


def main():
    limpar()
    simular()
    df_ap = pd.DataFrame(apontamentos)
    df_ap = df_ap[df_ap["ciclos"] > 0].reset_index(drop=True)
    df_op, df_ped, df_est = gravar_erp(df_ap)
    gravar_mes(df_ap)
    gravar_diario_bordo(df_ap)
    gravar_programa()
    gravar_planilhas(df_ap, df_ped, df_est)
    print(f"ordens: {len(df_op):,} | apontamentos: {len(df_ap):,} | paradas: {len(paradas):,} | "
          f"refugo (linhas): {len(refugos):,} | programa (linhas): {len(programa):,}")
    print(f"arquivos em {BRUTOS}: " + ", ".join(f"{p.name} {len(list(p.iterdir()))}" for p in sorted(BRUTOS.iterdir())))


if __name__ == "__main__":
    main()
