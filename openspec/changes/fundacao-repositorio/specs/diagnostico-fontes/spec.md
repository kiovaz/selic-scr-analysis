## Purpose

Permite ao grupo verificar, sob demanda e sem autenticação, que as duas fontes públicas do projeto — SCR.data (Banco Central) e Selic (Ipeadata) — continuam acessíveis e no formato que o pipeline assume, e deixar essa verificação registrada nos documentos do projeto antes de qualquer código de ingestão ser escrito.

## ADDED Requirements

### Requirement: Diagnóstico de acesso às duas fontes

O projeto SHALL oferecer um comando único, executável a partir da raiz do repositório e sem credenciais, que tenta acessar o SCR.data e a Selic do Ipeadata e reporta o resultado de cada uma separadamente. As URLs SHALL vir de `src/config.py`; nenhum endereço pode estar chumbado no comando.

O comando SHALL tratar falha de rede, erro HTTP e resposta malformada como **resultado reportado**, não como exceção não tratada: a falha de uma fonte não pode impedir o diagnóstico da outra.

#### Scenario: As duas fontes respondem

- **WHEN** o diagnóstico é executado e as duas fontes respondem com sucesso
- **THEN** a saída identifica cada fonte, a URL usada e o tamanho ou a contagem de registros recebidos
- **AND** o processo termina sem exceção

#### Scenario: Uma das fontes está indisponível

- **WHEN** uma das fontes devolve erro de rede, erro HTTP ou conteúdo que não pode ser interpretado
- **THEN** a saída identifica qual fonte falhou e o motivo, em texto legível
- **AND** o diagnóstico da outra fonte é executado mesmo assim
- **AND** o processo termina sem exceção não tratada

### Requirement: Conferência do contrato do SCR.data

O diagnóstico SHALL abrir a amostra do SCR.data e reportar, para o primeiro arquivo do ZIP: o encoding que decodificou o conteúdo, o cabeçalho, a contagem total de colunas e, para cada uma das cinco colunas de `SCR_COLUNAS_USADAS`, se ela está presente.

O encoding SHALL ser determinado testando os candidatos declarados em `src/config.py`, na ordem, adotando o primeiro que decodificar o conteúdo sem erro. Quando nenhum candidato decodifica o conteúdo, isso SHALL ser reportado como divergência a investigar, não como sucesso.

A lista de candidatos SHALL estar ordenada do mais restritivo para o mais permissivo. Um encoding que aceita qualquer sequência de bytes — `latin-1` aceita — SHALL vir por último: se vier antes, ele decodifica tudo sem erro e impede que os demais sejam testados, produzindo um resultado que parece bem-sucedido e está errado.

O diagnóstico SHALL reaproveitar uma amostra já presente em `data/raw/_amostras/` quando ela existir, em vez de rebaixar o arquivo — o ZIP tem cerca de 176 MB.

#### Scenario: Layout esperado confirmado

- **WHEN** o ZIP do SCR.data é aberto e as cinco colunas de `SCR_COLUNAS_USADAS` estão no cabeçalho
- **THEN** cada coluna é listada como presente
- **AND** o encoding usado, o separador e a contagem de colunas aparecem na saída

#### Scenario: Arquivo UTF-8 não é reportado como latin-1

- **WHEN** o arquivo do SCR está em UTF-8, com ou sem BOM
- **THEN** o encoding reportado é um dos candidatos UTF-8, nunca `latin-1`
- **AND** o nome da primeira coluna sai como `data_base`, sem BOM residual
- **AND** os textos acentuados de `modalidade` saem legíveis, sem mojibake

#### Scenario: Coluna esperada ausente

- **WHEN** uma das cinco colunas de `SCR_COLUNAS_USADAS` não está no cabeçalho do arquivo
- **THEN** a saída marca essa coluna como não encontrada, nomeando-a
- **AND** o diagnóstico continua e reporta as demais colunas

#### Scenario: Amostra já baixada

- **WHEN** o diagnóstico é executado e `data/raw/_amostras/` já contém o ZIP do ano da amostra
- **THEN** o arquivo local é usado
- **AND** nenhum download de 176 MB é refeito

### Requirement: Conferência do contrato da Selic

O diagnóstico SHALL requisitar a série da Selic no Ipeadata e reportar a contagem de registros, os campos disponíveis no primeiro registro, o primeiro e o último registro da série. Os registros vêm dentro da chave `value` da resposta OData.

A saída SHALL declarar explicitamente que `BM12_TJOVER12` está em **% ao mês**, para que a unidade não seja confundida com % ao ano em nenhuma etapa seguinte.

#### Scenario: Série recebida

- **WHEN** a API do Ipeadata responde com registros
- **THEN** a saída mostra a contagem de registros, os campos `SERCODIGO`, `VALDATA` e `VALVALOR`, e o primeiro e o último registro
- **AND** a última competência disponível (`VALDATA` do último registro) é destacada

#### Scenario: Resposta vazia

- **WHEN** a API responde com sucesso mas a chave `value` vem vazia
- **THEN** a saída reporta que a série veio vazia e precisa ser investigada
- **AND** o processo termina sem exceção

### Requirement: Registro das respostas nos documentos do projeto

O resultado do diagnóstico SHALL ser registrado em `docs/architecture.md` e `docs/data_dictionary.md`. Enquanto qualquer marcador `[PREENCHER]` da Sprint 1 permanecer no `docs/architecture.md`, a Sprint 1 SHALL ser considerada não concluída.

As respostas registradas SHALL incluir, no mínimo: a data real de coleta de cada fonte, a licença ou termos de uso do Ipeadata, o encoding e o separador decimal do CSV do SCR, a unidade de `carteira_ativa` (reais ou milhares), a última competência publicada do SCR e a decisão do grupo sobre o Docker.

#### Scenario: Sprint 1 concluída

- **WHEN** o diagnóstico foi executado e as respostas foram escritas nos documentos
- **THEN** `docs/architecture.md` não contém nenhum marcador `[PREENCHER]` da Sprint 1
- **AND** `docs/data_dictionary.md` declara a unidade e o formato numérico de `carteira_ativa` e `numero_de_operacoes`
- **AND** a nota de proveniência da Selic (Ipeadata redistribui série produzida pelo Banco Central) consta do dicionário

#### Scenario: Divergência entre a amostra e a configuração

- **WHEN** o diagnóstico revela que uma constante de `src/config.py` não corresponde ao arquivo real — encoding fora dos candidatos, nome de coluna diferente ou última competência além de `ANO_FIM`
- **THEN** a constante é corrigida em `src/config.py`
- **AND** a divergência encontrada é registrada em `docs/architecture.md`

### Requirement: Exploração reproduzível da amostra

O projeto SHALL manter um notebook de exploração que abre a amostra local já baixada e demonstra, com saída visível, as respostas da definição de pronto da Sprint 1: encoding, separador de campo, separador decimal, unidade de `carteira_ativa`, contagem de linhas de um ano, presença das cinco colunas usadas e presença das oito modalidades `Financiamentos%`.

O notebook SHALL ler caminhos e constantes de `src/config.py` e SHALL ler a amostra de `data/raw/_amostras/`. Nenhum dado da amostra pode ser versionado no Git.

#### Scenario: Notebook demonstra o recorte de modalidades

- **WHEN** o notebook lista as modalidades distintas presentes na amostra do SCR
- **THEN** as modalidades que começam com o prefixo de `PREFIXO_MODALIDADE` são identificadas e contadas
- **AND** a contagem encontrada é comparada com as 8 modalidades que o projeto espera

#### Scenario: Notebook não versiona dado

- **WHEN** o notebook é commitado
- **THEN** nenhum arquivo de `data/` acompanha o commit
- **AND** os caminhos usados vêm de `src/config.py`, não chumbados no notebook
