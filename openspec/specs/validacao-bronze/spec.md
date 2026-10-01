# validacao-bronze Specification

## Purpose
Fornece checagens de qualidade padronizadas e um sistema de quarentena que a construção da Silver usa para desviar registros inválidos sem derrubar o job, preservando o registro original e o motivo da rejeição. Os loaders da Bronze não aplicam essas checagens (seção 3.3 de `docs/architecture.md`).

## Requirements

### Requirement: Checagens de domínio e tipagem

O módulo de validação SHALL oferecer funções reutilizáveis para as seguintes checagens, aplicáveis tanto ao SCR quanto à Selic. Essas checagens SHALL ser aplicadas na construção da **Silver**, sobre os dados lidos da Bronze — os loaders da Bronze não as aplicam (seção 4.1 de `docs/architecture.md`).

- **UF válida:** o valor da coluna `uf` SHALL estar na lista `UFS_VALIDAS` de `src/config.py`.
- **Data no intervalo:** a data de referência SHALL ser ≥ julho/`ANO_INICIO` e ≤ a última competência plausível.
- **Valor não negativo:** colunas numéricas de negócio (e.g., `carteira_ativa`, `VALVALOR`) SHALL ser ≥ 0. Nota: `numero_de_operacoes` usa `-1` como máscara do BCB — isso não é valor negativo no sentido de negócio; a Silver converte `-1` em nulo, e a checagem de valor negativo não o rejeita.
- **Tipagem válida:** colunas numéricas SHALL ser conversíveis para o tipo esperado (int ou float); colunas de data SHALL ser conversíveis para date.

Cada checagem SHALL retornar o motivo padronizado correspondente (`uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`) quando falhar, e `None` quando passar.

#### Scenario: Registro válido passa em todas as checagens

- **WHEN** um registro do SCR tem UF válida, data no intervalo, valores ≥ 0 e tipos conversíveis
- **THEN** nenhum motivo de falha é retornado
- **AND** o registro é considerado apto para a Silver

#### Scenario: Registro com múltiplas violações

- **WHEN** um registro tem UF inválida e tipagem inválida simultaneamente
- **THEN** ao menos um dos motivos é retornado (a implementação pode retornar o primeiro ou todos)
- **AND** o registro é direcionado para a quarentena

#### Scenario: Valor -1 no numero_de_operacoes não é rejeitado na Bronze

- **WHEN** um registro do SCR tem `numero_de_operacoes` igual a `-1`
- **THEN** a checagem de valor negativo NÃO rejeita o registro
- **AND** o `-1` continua preservado na Bronze como veio da fonte

### Requirement: Sistema de quarentena

O módulo SHALL oferecer uma função de quarentena que recebe o registro original, o motivo padronizado e metadados do job, e escreve o registro rejeitado em `data/raw/_quarentena/`. Quem chama a quarentena é a construção da Silver; o registro original continua existindo na Bronze.

O módulo SHALL oferecer também a gravação de um **lote** de registros rejeitados de uma tabela da Silver num único arquivo, que **substitui** o arquivo da execução anterior da mesma tabela. Como a Silver é reconstruída inteira a cada execução, a sua quarentena também é: reprocessar SHALL NOT duplicar registros rejeitados.

A quarentena SHALL preservar: `_load_id`, `_source_system`, `_source_object`, `motivo`, `payload` (registro original em formato JSON) e `quarantined_at` (timestamp do momento da rejeição), conforme o dicionário de dados. O formato das linhas SHALL ser o mesmo para envio individual e em lote.

A escrita na quarentena SHALL nunca falhar de modo que derrube o job principal — se a própria escrita na quarentena falhar, o erro SHALL ser registrado em log e o processamento SHALL continuar.

#### Scenario: Registro rejeitado é preservado na quarentena

- **WHEN** um registro é identificado como inválido por qualquer checagem
- **THEN** ele é escrito em `data/raw/_quarentena/` com o motivo padronizado
- **AND** o campo `payload` contém o registro original completo
- **AND** `quarantined_at` registra o momento exato da rejeição

#### Scenario: Quarentena não derruba o job

- **WHEN** a própria escrita na quarentena falha (e.g., disco cheio)
- **THEN** o erro é registrado em log
- **AND** o job continua processando os demais registros
- **AND** o job não é interrompido

#### Scenario: Motivos padronizados

- **WHEN** registros são enviados para a quarentena
- **THEN** o campo `motivo` contém exclusivamente um dos valores padronizados: `uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`, `duplicata_na_chave`
- **AND** nenhum motivo ad-hoc ou texto livre é aceito

#### Scenario: Reprocessar a Silver não duplica a quarentena

- **WHEN** a construção da `silver_scr` roda duas vezes e rejeita as mesmas 3 linhas nas duas
- **THEN** a quarentena da `silver_scr` tem 3 linhas, não 6

### Requirement: Quarentena legível para investigação

A quarentena SHALL ser escrita em formato que permita consulta posterior (Parquet ou CSV). Um analista SHALL conseguir abrir a quarentena, filtrar por `motivo` ou `_load_id`, e ver o registro original no `payload`.

#### Scenario: Consulta por motivo

- **WHEN** um analista lê a quarentena e filtra por `motivo == 'uf_invalida'`
- **THEN** obtém todos os registros rejeitados por UF inválida
- **AND** cada registro tem seu `payload` original legível

### Requirement: Checagens aplicadas a uma coluna inteira

O módulo de validação SHALL oferecer, além das checagens registro a registro, versões que avaliam uma coluna inteira de uma vez e devolvem, para cada linha, se ela falhou. Essas versões SHALL seguir as mesmas regras das checagens registro a registro, incluindo a exceção do `-1` em `numero_de_operacoes`, e SHALL aceitar o separador decimal como parâmetro (o SCR usa vírgula).

#### Scenario: Mesmo resultado que a checagem registro a registro

- **WHEN** a mesma lista de valores (vazio, `abc`, `-5`, `-1` em `numero_de_operacoes`, `sp`, `XX`, `SP`) é avaliada pela checagem por coluna e pela checagem registro a registro
- **THEN** as duas apontam exatamente as mesmas linhas como inválidas, com o mesmo motivo

#### Scenario: Decimal com vírgula

- **WHEN** a coluna `carteira_ativa` contém `1234,56` e a checagem recebe o separador decimal `,`
- **THEN** o valor é considerado numérico e não negativo
