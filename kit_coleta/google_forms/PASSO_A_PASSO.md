# Piloto de coleta com Google Forms

Três formulários no celular (produção, parada e refugo), respostas numa Planilha Google, e o mesmo pipeline e painel do projeto. Serve para testar a coleta com o time antes de investir num aplicativo.

## 1. Criar os formulários (uma vez, uns 10 minutos)

1. Entre em https://script.google.com com a conta Google que será dona dos formulários.
2. **Novo projeto**. Apague o conteúdo do editor e cole o arquivo `criar_formularios.gs` inteiro.
3. No seletor de função, escolha **criarTudo** e clique em **Executar**.
4. O Google pede autorização para criar formulários e planilhas na sua conta. Autorize.
5. Abra o **Registro de execução**. Ele mostra o link da planilha de respostas e os três links para enviar ao time.

O resultado, no seu Google Drive: a planilha **PCP - Coleta (respostas)** e os formulários **PCP - Apontamento de produção**, **PCP - Parada de máquina** e **PCP - Refugo por defeito**.

## 2. Colocar as listas da fábrica (uns 15 minutos)

Os formulários nascem com as máquinas, produtos, motivos e defeitos da fábrica fictícia.

1. Abra a planilha de respostas, aba **Listas**.
2. Troque o conteúdo de cada coluna pelo da sua fábrica. Produto no formato `código - descrição` (ex.: `1001 - Tampa 28 mm`), com código numérico.
3. Volte ao script, escolha a função **atualizarListas** e execute.

Motivo de parada novo precisa entrar também em `config/depara_motivos_parada.csv`; sem isso o painel mostra "Não classificado".

## 3. Mandar para o time

Envie os três links (WhatsApp, QR code colado na máquina, atalho na tela do tablet). Combine a regra:

- **Produção:** uma resposta por ordem, no fim do turno ou na troca de ordem.
- **Parada:** uma resposta assim que a máquina voltar, inclusive refeição e troca.
- **Refugo:** uma resposta por defeito, no fim do turno.

## 4. Atualizar o painel

1. Na planilha de respostas: **Arquivo > Fazer download > Microsoft Excel (.xlsx)**.
2. Preencha `01_Cadastros.xlsx` do kit com máquinas, produtos e roteiros reais (uma vez) e guarde numa pasta, por exemplo `minha_fabrica/`.
3. Rode:

```bash
python kit_coleta/google_forms/importar_google.py respostas.xlsx minha_fabrica dados_fabrica
#  PowerShell: $env:PCP_DADOS = "dados_fabrica"      cmd: set PCP_DADOS=dados_fabrica
python executar_pipeline.py
```

As planilhas 04 a 07 do kit (programa, ordens, estoque, pessoas) são opcionais: se estiverem na mesma pasta do cadastro, entram junto.

## Limites do piloto

- Precisa de internet no aparelho na hora de enviar.
- O formulário não confere se a OP existe nem calcula nada na tela.
- A duração da parada é informada pelo operador; não há botão de "parou" e "voltou".
- Resposta enviada errada é corrigida direto na planilha de respostas.
- O download da planilha é manual. Dá para automatizar depois, se o piloto vingar.

## O que observar nas duas semanas de piloto

- Quais motivos de parada faltam na lista ou ninguém usa.
- Quanto tempo o operador leva por apontamento.
- Se o refugo por defeito fecha com o refugo da produção.
- Se as paradas somadas explicam o turno, ou se a performance aparece baixa sem motivo (sinal de parada não anotada).

Essas respostas definem as telas do aplicativo definitivo.
