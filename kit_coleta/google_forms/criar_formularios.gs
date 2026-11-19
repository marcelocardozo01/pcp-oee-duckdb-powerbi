/**
 * Piloto de coleta com Google Forms.
 *
 * Cria, de uma vez:
 *   - a planilha "PCP - Coleta (respostas)", com a aba "Listas" (máquinas, produtos, motivos, defeitos)
 *   - três formulários: Produção, Parada e Refugo, com as respostas caindo nessa planilha
 *
 * Como usar:
 *   1. Abra https://script.google.com, crie um projeto novo e cole este arquivo inteiro.
 *   2. Escolha a função criarTudo e clique em Executar. Autorize quando o Google pedir.
 *   3. Abra o registro de execução: lá estão os links da planilha e dos três formulários.
 *   4. Troque as listas da aba "Listas" pelas da sua fábrica e execute atualizarListas.
 *
 * As listas abaixo são as da fábrica fictícia do projeto. Servem só para o primeiro teste.
 */

const MAQUINAS = ['INJ-01', 'INJ-02', 'INJ-03', 'INJ-04', 'INJ-05', 'SOP-01', 'SOP-02', 'SOP-03', 'SOP-04', 'DEC-01', 'DEC-02', 'DEC-03'];
const PRODUTOS = ['1001 - Tampa flip-top 28 mm', '1002 - Tampa rosca 38 mm', '1003 - Tampa disc-top 24 mm', '1004 - Tampa galão 5 L com lacre',
  '1005 - Válvula dosadora', '1006 - Alça para galão', '1007 - Pote 250 g com tampa', '2001 - Frasco 500 mL PEAD natural',
  '2002 - Frasco 1 L PEAD natural', '2003 - Frasco 1 L PEAD branco', '2004 - Frasco 2 L PEAD branco', '2005 - Galão 5 L PEAD natural',
  '2006 - Galão 5 L PEAD azul', '3001 - Frasco 500 mL serigrafado', '3002 - Frasco 1 L serigrafado', '3003 - Frasco 2 L rotulado',
  '3004 - Galão 5 L rotulado'];
const MOTIVOS = ['Refeição', 'Manutenção preventiva', 'Sem programação', 'Reunião DDS', 'Troca de molde', 'Troca de cor', 'Quebra mecânica',
  'Quebra elétrica', 'Falha hidráulica', 'Ajuste de processo', 'Limpeza de molde', 'Aguardando qualidade', 'Falta de matéria-prima',
  'Falta de embalagem', 'Falta de operador', 'Falta de energia'];
const DEFEITOS = ['Rebarba', 'Falha de injeção', 'Chupado', 'Mancha / contaminação', 'Dimensional fora', 'Início de processo', 'Parede fina',
  'Furo', 'Deformação', 'Falha de impressão', 'Fora de registro', 'Rótulo torto', 'Bolha no rótulo', 'Risco / arranhão'];
const TURNOS = ['1', '2', '3'];

// coluna da aba Listas -> título da pergunta que usa a lista
const LISTAS = { 'Máquina': MAQUINAS, 'Produto': PRODUTOS, 'Motivo': MOTIVOS, 'Defeito': DEFEITOS };

function criarTudo() {
  const planilha = SpreadsheetApp.create('PCP - Coleta (respostas)');
  const listas = planilha.getSheets()[0].setName('Listas');
  const nomes = Object.keys(LISTAS);
  listas.getRange(1, 1, 1, nomes.length).setValues([nomes]).setFontWeight('bold');
  nomes.forEach((nome, j) => listas.getRange(2, j + 1, LISTAS[nome].length, 1).setValues(LISTAS[nome].map(v => [v])));
  listas.setFrozenRows(1);

  const inteiro = FormApp.createTextValidation().setHelpText('Digite um número inteiro.').requireWholeNumber().build();
  const ids = {};

  // ---- Produção ----
  let f = FormApp.create('PCP - Apontamento de produção');
  f.setDescription('Uma resposta por máquina, turno e ordem. Trocou de ordem no meio do turno: envie outra resposta.');
  f.addDateItem().setTitle('Data').setHelpText('Data em que o turno começou').setRequired(true);
  f.addListItem().setTitle('Turno').setChoiceValues(TURNOS).setRequired(true);
  f.addListItem().setTitle('Máquina').setChoiceValues(MAQUINAS).setRequired(true);
  f.addTextItem().setTitle('OP').setHelpText('Número da ordem de produção').setValidation(inteiro).setRequired(true);
  f.addListItem().setTitle('Produto').setChoiceValues(PRODUTOS).setRequired(true);
  f.addTextItem().setTitle('Operador').setHelpText('Matrícula (opcional)').setValidation(inteiro);
  f.addTimeItem().setTitle('Hora início').setHelpText('Quando a ordem começou a rodar neste turno').setRequired(true);
  f.addTimeItem().setTitle('Hora fim').setHelpText('Quando parou de rodar ou o turno acabou').setRequired(true);
  f.addTextItem().setTitle('Peças produzidas').setHelpText('Total que saiu da máquina, boas + refugo. Ideal: leitura do contador').setValidation(inteiro).setRequired(true);
  f.addTextItem().setTitle('Refugo').setHelpText('Peças descartadas').setValidation(inteiro).setRequired(true);
  f.addTextItem().setTitle('Retrabalho').setHelpText('Peças que voltaram para conserto (opcional)').setValidation(inteiro);
  ids.Producao = finalizar_(f, planilha);

  // ---- Parada ----
  f = FormApp.create('PCP - Parada de máquina');
  f.setDescription('Uma resposta por parada, inclusive refeição e troca. Envie assim que a máquina voltar.');
  f.addDateItem().setTitle('Data').setHelpText('Data em que o turno começou').setRequired(true);
  f.addListItem().setTitle('Turno').setChoiceValues(TURNOS).setRequired(true);
  f.addListItem().setTitle('Máquina').setChoiceValues(MAQUINAS).setRequired(true);
  f.addTimeItem().setTitle('Hora início').setHelpText('Quando a máquina parou').setRequired(true);
  f.addTextItem().setTitle('Duração (min)').setHelpText('Minutos parados').setValidation(inteiro).setRequired(true);
  f.addListItem().setTitle('Motivo').setChoiceValues(MOTIVOS).setRequired(true);
  f.addTextItem().setTitle('OP').setHelpText('Ordem que estava na máquina (opcional)').setValidation(inteiro);
  f.addTextItem().setTitle('Líder').setHelpText('Nome (opcional)');
  ids.Paradas = finalizar_(f, planilha);

  // ---- Refugo ----
  f = FormApp.create('PCP - Refugo por defeito');
  f.setDescription('Uma resposta por defeito encontrado no turno.');
  f.addDateItem().setTitle('Data').setHelpText('Data em que o turno começou').setRequired(true);
  f.addListItem().setTitle('Turno').setChoiceValues(TURNOS).setRequired(true);
  f.addListItem().setTitle('Máquina').setChoiceValues(MAQUINAS).setRequired(true);
  f.addTextItem().setTitle('OP').setValidation(inteiro).setRequired(true);
  f.addListItem().setTitle('Defeito').setChoiceValues(DEFEITOS).setRequired(true);
  f.addTextItem().setTitle('Quantidade').setHelpText('Peças refugadas por este defeito').setValidation(inteiro).setRequired(true);
  ids.Refugo = finalizar_(f, planilha);

  // dá nome fixo às abas de resposta (o Google cria como "Respostas ao formulário N")
  SpreadsheetApp.flush();
  planilha.getSheets().forEach(aba => {
    const url = aba.getFormUrl();
    if (!url) return;
    Object.keys(ids).forEach(nome => { if (url.indexOf(ids[nome]) >= 0) aba.setName(nome); });
  });

  PropertiesService.getScriptProperties().setProperties({ PLANILHA: planilha.getId(), FORMULARIOS: JSON.stringify(ids) });
  Logger.log('Planilha de respostas: ' + planilha.getUrl());
  Object.keys(ids).forEach(nome => Logger.log(nome + ' (enviar ao time): ' + FormApp.openById(ids[nome]).getPublishedUrl()));
}

function finalizar_(formulario, planilha) {
  formulario.setCollectEmail(false);
  formulario.setShowLinkToRespondAgain(true);
  formulario.setConfirmationMessage('Apontamento registrado.');
  formulario.setDestination(FormApp.DestinationType.SPREADSHEET, planilha.getId());
  return formulario.getId();
}

/** Depois de editar a aba "Listas", execute esta função para levar as listas novas aos três formulários. */
function atualizarListas() {
  const props = PropertiesService.getScriptProperties();
  const aba = SpreadsheetApp.openById(props.getProperty('PLANILHA')).getSheetByName('Listas');
  const dados = aba.getDataRange().getValues();
  const listas = {};
  dados[0].forEach((titulo, j) => {
    listas[titulo] = dados.slice(1).map(l => String(l[j]).trim()).filter(v => v !== '');
  });
  const ids = JSON.parse(props.getProperty('FORMULARIOS'));
  Object.keys(ids).forEach(nome => {
    FormApp.openById(ids[nome]).getItems(FormApp.ItemType.LIST).forEach(item => {
      const lista = listas[item.getTitle()];
      if (lista && lista.length) item.asListItem().setChoiceValues(lista);
    });
  });
  Logger.log('Listas atualizadas: ' + Object.keys(listas).map(k => k + ' ' + listas[k].length).join(', '));
}
