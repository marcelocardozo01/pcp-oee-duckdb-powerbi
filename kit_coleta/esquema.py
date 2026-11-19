"""Desenho das planilhas de coleta: uma definicao so, usada pelo gerador dos modelos e pelo importador.

Cada planilha: arquivo -> abas -> colunas (titulo, tipo, obrigatoria, o que preencher).
Tipos: texto, inteiro, numero, data, datahora, hora.
"""

TURNOS = {1: 6, 2: 14, 3: 22}        # hora de inicio de cada turno
MIN_TURNO = 480

MOTIVOS = ["Refeição", "Manutenção preventiva", "Sem programação", "Reunião DDS",
           "Troca de molde", "Troca de cor", "Quebra mecânica", "Quebra elétrica", "Falha hidráulica",
           "Ajuste de processo", "Limpeza de molde", "Aguardando qualidade",
           "Falta de matéria-prima", "Falta de embalagem", "Falta de operador", "Falta de energia"]
STATUS_OP = ["Liberada", "Em produção", "Encerrada"]
TIPOS_ITEM = ["Matéria-prima", "Produto acabado"]

PLANILHAS = {
    "01_Cadastros.xlsx": {
        "quem": "PCP ou engenharia, uma vez; revisar quando entrar máquina ou produto novo",
        "abas": {
            "Máquinas": ("Uma linha por máquina ou posto que será medido.", [
                ("Código", "texto", True, "Como a máquina é chamada no chão de fábrica. Ex.: INJ-01"),
                ("Descrição", "texto", True, "Nome por extenso"),
                ("Célula", "texto", True, "Setor ou célula. Vira o filtro do painel"),
                ("Custo hora (R$)", "numero", False, "Custo de uma hora parada. Sem ele, o custo das paradas fica zerado")]),
            "Produtos": ("Uma linha por produto fabricado.", [
                ("Código", "inteiro", True, "Código numérico do produto"),
                ("Descrição", "texto", True, ""),
                ("Família", "texto", True, "Agrupamento comercial"),
                ("Célula", "texto", True, "A mesma célula da máquina que o produz"),
                ("Peso (g)", "numero", False, "Peso da peça. Base das toneladas produzidas"),
                ("Custo padrão (R$)", "numero", False, "Custo por peça. Base do custo do refugo e do WIP"),
                ("Preço de venda (R$)", "numero", False, "")]),
            "Roteiros": ("Uma linha por produto e máquina em que ele pode rodar. É daqui que sai o ritmo ideal (performance do OEE).", [
                ("Cód. produto", "inteiro", True, ""),
                ("Máquina", "texto", True, "Código da aba Máquinas"),
                ("Ciclo padrão (s)", "numero", True, "Segundos por ciclo no ritmo ideal. Cronometrar se não houver ficha técnica"),
                ("Cavidades", "inteiro", True, "Peças por ciclo. Use 1 se não se aplica"),
                ("Setup padrão (min)", "numero", False, "Tempo esperado de troca")]),
            "Materiais": ("Matérias-primas controladas. Opcional: só para os indicadores de estoque e rendimento.", [
                ("Código", "texto", True, ""), ("Descrição", "texto", True, ""), ("Unidade", "texto", True, "kg, un, L..."),
                ("Custo unitário (R$)", "numero", True, ""), ("Lead time (dias)", "inteiro", False, "Prazo de compra")]),
            "Estrutura": ("Quanto de cada material vai em uma peça. Opcional: só para o rendimento de matéria-prima.", [
                ("Cód. produto", "inteiro", True, ""), ("Cód. material", "texto", True, ""),
                ("Qtd. por peça", "numero", True, "Na unidade do material. Ex.: 0,028 kg")]),
            "Clientes": ("Opcional: só para o OTIF por cliente.", [
                ("Código", "inteiro", True, ""), ("Razão social", "texto", True, "")]),
        }},
    "02_Apontamento de Producao.xlsx": {
        "quem": "Operador ou líder, a cada turno. Dispensa esta planilha quem tem coletor: o pipeline lê o CSV do coletor direto",
        "abas": {
            "Apontamentos": ("Uma linha por máquina, turno e ordem. Trocou de ordem no meio do turno: nova linha.", [
                ("Data", "data", True, "Data em que o turno começou"),
                ("Turno", "inteiro", True, "1, 2 ou 3"),
                ("Máquina", "texto", True, "Código do cadastro"),
                ("OP", "inteiro", True, "Número da ordem de produção"),
                ("Cód. produto", "inteiro", True, ""),
                ("Operador", "inteiro", False, "Matrícula"),
                ("Hora início", "hora", True, "HH:MM em que a ordem começou a rodar neste turno"),
                ("Hora fim", "hora", True, "HH:MM em que parou de rodar ou o turno acabou"),
                ("Peças produzidas", "inteiro", True, "Total que saiu da máquina, boas + refugo. Ideal: leitura do contador"),
                ("Refugo", "inteiro", True, "Peças descartadas"),
                ("Retrabalho", "inteiro", False, "Peças que voltaram para conserto"),
                ("Tempo produzindo (min)", "numero", False, "Só se a máquina tiver horímetro. Em branco, o importador calcula: turno menos paradas")]),
        }},
    "03_Diario de Bordo.xlsx": {
        "quem": "Líder do turno, a cada parada",
        "abas": {
            "Paradas": ("Uma linha por parada, inclusive refeição e troca. Parada não anotada não some: aparece como máquina lenta e esconde o motivo.", [
                ("Data", "data", True, "Data em que o turno começou"),
                ("Turno", "inteiro", True, "1, 2 ou 3"),
                ("Máquina", "texto", True, ""),
                ("Hora início", "hora", True, "HH:MM"),
                ("Duração (min)", "inteiro", True, "Minutos parados"),
                ("Motivo", "texto", True, "Escolher da lista. Motivo novo: pedir ao PCP para incluir no de-para"),
                ("OP", "inteiro", False, "Ordem que estava na máquina"),
                ("Líder", "texto", False, "")]),
            "Refugo": ("Uma linha por defeito encontrado no turno. Opcional: sem ela o refugo aparece sem o Pareto de defeitos.", [
                ("Data", "data", True, ""), ("Turno", "inteiro", True, ""), ("Máquina", "texto", True, ""),
                ("OP", "inteiro", True, ""), ("Defeito", "texto", True, "Nome do defeito, sempre escrito igual"),
                ("Quantidade", "inteiro", True, "Peças refugadas por este defeito")]),
        }},
    "04_Programa Semanal.xlsx": {
        "quem": "PCP, toda sexta-feira, para a semana seguinte",
        "abas": {
            "PROGRAMA": ("Uma linha por dia, máquina e ordem. Ordem que atravessa dias: uma linha por dia, com a quantidade daquele dia.", [
                ("Data", "data", True, "Dia em que a quantidade deve ser produzida"),
                ("Máquina", "texto", True, ""),
                ("Seq.", "inteiro", True, "Ordem de entrada na máquina na semana: 1, 2, 3..."),
                ("OP", "inteiro", True, ""),
                ("Cód. produto", "inteiro", True, ""),
                ("Produto", "texto", False, "Só para leitura de quem recebe o programa"),
                ("Qtd. programada", "inteiro", True, "Peças boas esperadas no dia")]),
        }},
    "05_Ordens e Pedidos.xlsx": {
        "quem": "PCP e comercial. Quem tem ERP exporta estas duas listas em vez de digitar",
        "abas": {
            "Ordens": ("Uma linha por ordem de produção.", [
                ("OP", "inteiro", True, ""), ("Cód. produto", "inteiro", True, ""), ("Máquina", "texto", True, ""),
                ("Pedido", "inteiro", False, "Pedido de venda que a ordem atende"),
                ("Qtd. planejada", "inteiro", True, ""),
                ("Data de abertura", "data", True, ""),
                ("Início programado", "datahora", True, "Data e hora"),
                ("Fim programado", "datahora", True, "Data e hora. Base da pontualidade das ordens"),
                ("Data de necessidade", "data", True, "Quando a peça precisa estar pronta"),
                ("Status", "texto", True, "Liberada, Em produção ou Encerrada"),
                ("Data de encerramento", "datahora", False, "Preencher ao encerrar")]),
            "Pedidos": ("Uma linha por pedido de venda. Opcional: só para OTIF e lead time do pedido.", [
                ("Pedido", "inteiro", True, ""), ("Cód. cliente", "inteiro", True, ""), ("Cód. produto", "inteiro", True, ""),
                ("Qtd. pedida", "inteiro", True, ""), ("Data do pedido", "data", True, ""),
                ("Data prometida", "data", True, "A data combinada com o cliente"),
                ("Data de entrega", "data", False, "Preencher quando sair"),
                ("Qtd. entregue", "inteiro", False, "")]),
        }},
    "06_Materiais e Estoque.xlsx": {
        "quem": "Almoxarifado. Opcional: só para giro, cobertura, acuracidade e rendimento",
        "abas": {
            "Requisições": ("Uma linha por retirada de material para uma ordem.", [
                ("Data", "data", True, ""), ("OP", "inteiro", True, ""), ("Cód. material", "texto", True, ""),
                ("Quantidade", "numero", True, "Na unidade do material")]),
            "Saldo diário": ("Saldo de fechamento de cada item, uma linha por dia e item.", [
                ("Data", "data", True, ""), ("Código do item", "texto", True, "Código do material ou do produto"),
                ("Tipo", "texto", True, "Matéria-prima ou Produto acabado"),
                ("Saldo", "numero", True, ""), ("Custo unitário", "numero", True, "")]),
            "Inventário": ("Conferência cíclica: alguns itens por semana, contados e comparados com o sistema.", [
                ("Data", "data", True, ""), ("Código do item", "texto", True, ""), ("Tipo", "texto", True, ""),
                ("Saldo sistema", "numero", True, "O que o sistema dizia na hora"),
                ("Qtd. contada", "numero", True, "O que foi contado"), ("Contador", "texto", False, "Quem contou")]),
        }},
    "07_Pessoas e Previsao.xlsx": {
        "quem": "RH (ponto) e comercial (previsão). Opcional",
        "abas": {
            "Ponto": ("Uma linha por dia, turno e célula.", [
                ("Data", "data", True, ""), ("Turno", "inteiro", True, ""), ("Célula", "texto", True, ""),
                ("Quadro previsto", "inteiro", True, "Quantas pessoas deveriam estar"),
                ("Presentes", "inteiro", True, ""), ("Horas normais", "numero", True, "Soma das horas da equipe"),
                ("Horas extras", "numero", True, "")]),
            "Previsão": ("Uma linha por produto e mês de entrega.", [
                ("Mês", "texto", True, "AAAA-MM. Ex.: 2026-10"), ("Cód. produto", "inteiro", True, ""),
                ("Qtd. prevista", "inteiro", True, "")]),
        }},
}
