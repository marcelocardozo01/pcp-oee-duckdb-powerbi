# Kit de coleta: como levar o painel para uma fábrica de verdade

O projeto roda com dados fictícios. Este kit é a ponte para dados reais: as planilhas que uma fábrica pequena precisa preencher, uma ficha de papel para o chão de fábrica e um importador que converte tudo para o formato que o pipeline já lê. Nenhuma regra de negócio muda.

## O que tem na pasta

| Pasta ou arquivo | Para que serve |
|---|---|
| `modelos/` | As 7 planilhas em branco. Cada uma tem uma aba "Como preencher", listas de escolha e uma linha de exemplo em cinza |
| `exemplo_preenchido/` | As mesmas planilhas com uma semana da fábrica fictícia (5 a 10/10/2026). Serve para ver como fica preenchido e para testar o caminho inteiro |
| `imprimir/ficha_de_turno.html` | Ficha A4 para o operador anotar à mão. Abrir no navegador e imprimir |
| `importar_planilhas.py` | Lê as planilhas preenchidas, confere, e grava a pasta de dados que o pipeline usa |
| `esquema.py` | A definição das planilhas (abas, colunas, tipos). Modelos e importador saem dela |
| `gerar_modelos.py` | Recria `modelos/`, `exemplo_preenchido/` e a ficha a partir do esquema |

## As planilhas, por ordem de prioridade

| # | Planilha | Quem preenche | Frequência | O que libera no painel |
|---|---|---|---|---|
| 1 | Cadastros (máquinas, produtos, roteiros) | PCP ou engenharia | Uma vez | Base de tudo. O ciclo padrão do roteiro é o que define a performance |
| 2 | Apontamento de produção | Operador ou líder | A cada turno | Produção, qualidade, refugo, performance |
| 3 | Diário de bordo (paradas e refugo por defeito) | Líder do turno | A cada parada | Disponibilidade, OEE, MTBF, MTTR, setup, Pareto de paradas e de defeitos |
| 4 | Programa semanal | PCP | Sexta-feira | Aderência ao volume e ao mix, sequência |
| 5 | Ordens e pedidos | PCP e comercial | Ao abrir e ao encerrar | Pontualidade das ordens, OTIF, lead time, ordens em atraso |
| 6 | Materiais e estoque | Almoxarifado | Diária e semanal | Giro, cobertura, acuracidade, rupturas, rendimento de matéria-prima |
| 7 | Pessoas e previsão | RH e comercial | Diária e mensal | Horas extras, absenteísmo, produtividade, acurácia da previsão |

## Três degraus de implantação

Não precisa começar com tudo. Cada degrau já entrega painel.

**Degrau 1: OEE (planilhas 1, 2 e 3).** É o mínimo. Com cadastro, apontamento e diário de bordo saem 21 dos 44 indicadores: todos os de eficiência, qualidade e paradas. Testado com o exemplo do kit: o pipeline roda e o painel abre só com essas três planilhas. As abas e os indicadores das outras famílias ficam sem valor.

**Degrau 2: programa e entrega (planilhas 4 e 5).** Entra o que é próprio do PCP: se a fábrica cumpriu o programa e se o pedido saiu no prazo e completo.

**Degrau 3: materiais, pessoas e demanda (planilhas 6 e 7).** Completa os 44 indicadores.

Sobre o degrau 1: sem a planilha de ordens, o importador cria uma ordem para cada OP apontada só para o pipeline rodar. Os indicadores que dependem de datas programadas (pontualidade, atraso, lead time, sequência, carga) aparecem com valor, mas não significam nada até a planilha 5 ser preenchida.

## Como a coleta acontece no dia a dia

1. **No chão de fábrica.** O operador anota na ficha de turno (papel) ou direto na planilha: o que produziu, quanto refugou e cada parada com o motivo.
2. **No fim do turno.** O líder confere e digita a ficha nas planilhas 2 e 3.
3. **Uma vez por dia.** Alguém do PCP roda o importador e o pipeline. O painel atualiza.

A fábrica que já tem coletor ou contador ligado à máquina pula a planilha 2: o pipeline lê direto um CSV por dia no formato do coletor (veja `dados/brutos/mes/`).

## Como rodar

```bash
# 1. converter as planilhas preenchidas (aqui, o exemplo do kit) para uma pasta de dados
python kit_coleta/importar_planilhas.py kit_coleta/exemplo_preenchido dados_fabrica

# 2. apontar o pipeline para essa pasta e rodar
#    PowerShell: $env:PCP_DADOS = "dados_fabrica"      cmd: set PCP_DADOS=dados_fabrica
python executar_pipeline.py
```

O painel sai em `painel_html/saida/index.html`. Para gravar em outro lugar e não sobrepor a demonstração, defina também `PCP_SAIDA` com a pasta de destino. Para o Power BI, aponte o parâmetro `PastaExports` para `dados_fabrica\exports\`.

A etapa de validação reclama de "cobertura do catálogo" enquanto houver planilha opcional vazia. É esperado: ela lista exatamente quais indicadores ainda não têm dado.

## O que o importador faz por você

- **Confere o preenchimento.** Linha com campo obrigatório em branco é recusada e aparece no relatório, com o número da linha.
- **Monta data e hora.** Junta "Hora início" e "Hora fim" com a data do turno, inclusive no 3º turno, que atravessa a meia-noite.
- **Calcula o tempo produzindo** quando a máquina não tem horímetro: 480 minutos do turno menos as paradas anotadas no diário de bordo, repartido entre as ordens do turno.
- **Calcula os ciclos**: peças produzidas dividido pelas cavidades do roteiro.

## Limitações que vale conhecer antes

- **Parada não anotada vira máquina lenta.** Sem horímetro, o importador supõe que a máquina rodou em todo o tempo que não está no diário. A parada esquecida não some: aparece como performance baixa em vez de disponibilidade baixa. O OEE fica igual, o diagnóstico fica errado. No teste com o exemplo, a disponibilidade saiu 81,5% contra 80,8% da base com horímetro, e a performance 89,8% contra 90,6%. Com horímetro ou coletor, a coluna "Tempo produzindo (min)" resolve.
- **Turno de 480 minutos, três turnos fixos** (06h, 14h, 22h). Outra jornada exige ajustar `esquema.py` e a regra `04_producao_turno.sql`.
- **Código de produto, OP, pedido e cliente são numéricos.** Código com letra precisa de uma tabela de conversão antes.
- **Motivos de parada** fora da lista viram "Não classificado" até entrarem em `config/depara_motivos_parada.csv`. A lista da planilha e da ficha de papel sai de `esquema.py`.
- **Metas** são as da fábrica fictícia. Ajuste em `config/indicadores.csv`. Feriados em `config/feriados.csv`.
- **Uma pessoa edita por vez.** Planilha em pasta compartilhada não aguenta dois líderes digitando ao mesmo tempo. Uma planilha por turno ou por célula, juntadas depois, evita o conflito; o importador hoje espera um arquivo de cada tipo.
- **O importador reprocessa tudo a cada rodada.** Para uma fábrica pequena isso leva segundos. As planilhas 2 e 3 crescem todo dia; vale abrir um arquivo novo por mês e guardar os anteriores.

## Quando a planilha deixa de bastar

A planilha serve para começar e provar o valor do indicador. Os sinais de que é hora de trocar a coleta:

- o líder gasta mais de 15 minutos por turno digitando;
- o refugo da ficha nunca fecha com o contador;
- a performance cai sem motivo aparente (parada não anotada).

O caminho natural é um contador de ciclos por máquina (sensor ou CLP) gravando o CSV diário que o pipeline já lê, mantendo o diário de bordo só para o motivo da parada. Nada do pipeline, dos indicadores ou dos painéis precisa mudar.
