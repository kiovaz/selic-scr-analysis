# validacao-bronze Specification

## Purpose
Fornece checagens de qualidade padronizadas e um sistema de quarentena que os loaders da Bronze usam para desviar registros inválidos sem derrubar o job, preservando o registro original e o motivo da rejeição.

## Requirements

### Requirement: Checagens de domínio e tipagem

O módulo de validação SHALL oferecer funções reutilizáveis para as seguintes checagens, aplicáveis tanto ao SCR quanto à Selic:

- **UF válida:** o valor da coluna `uf` SHALL estar na lista `UFS_VALIDAS` de `src/config.py`.
- **Data no intervalo:** a data de referência SHALL ser ≥ julho/`ANO_INICIO` e ≤ a última competência plausível.
- **Valor não negativo:** colunas numéricas de negócio (e.g., `carteira_ativa`, `VALVALOR`) SHALL ser ≥ 0. Nota: `numero_de_operacoes` usa `-1` como máscara do BCB — isso não é valor negativo no sentido de negócio, e o tratamento de `-1` é responsabilidade da Silver, não da validação Bronze.
- **Tipagem válida:** colunas numéricas SHALL ser conversíveis para o tipo esperado (int ou float); colunas de data SHALL ser conversíveis para date.

Cada checagem SHALL retornar o motivo padronizado correspondente (`uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`) quando falhar, e `None` quando passar.

#### Scenario: Registro válido passa em todas as checagens

- **WHEN** um registro do SCR tem UF válida, data no intervalo, valores ≥ 0 e tipos conversíveis
- **THEN** nenhum motivo de falha é retornado
- **AND** o registro é considerado apto para a Bronze

#### Scenario: Registro com múltiplas violações

- **WHEN** um registro tem UF inválida e tipagem inválida simultaneamente
- **THEN** ao menos um dos motivos é retornado (a implementação pode retornar o primeiro ou todos)
- **AND** o registro é direcionado para a quarentena

#### Scenario: Valor -1 no numero_de_operacoes não é rejeitado na Bronze

- **WHEN** um registro do SCR tem `numero_de_operacoes` igual a `-1`
- **THEN** a checagem de valor negativo NÃO rejeita o registro
- **AND** o `-1` é preservado na Bronze como veio da fonte (tratamento na Silver)

### Requirement: Sistema de quarentena

O módulo SHALL oferecer uma função de quarentena que recebe o registro original, o motivo padronizado e metadados do job, e escreve o registro rejeitado em `data/raw/_quarentena/`.

A quarentena SHALL preservar: `_load_id`, `_source_system`, `_source_object`, `motivo`, `payload` (registro original em formato JSON) e `quarantined_at` (timestamp do momento da rejeição), conforme o dicionário de dados.

A escrita na quarentena SHALL ser append-only e SHALL nunca falhar de modo que derrube o job principal — se a própria escrita na quarentena falhar, o erro SHALL ser registrado em log e o processamento SHALL continuar.

#### Scenario: Registro rejeitado é preservado na quarentena

- **WHEN** um registro é identificado como inválido por qualquer checagem
- **THEN** ele é escrito em `data/raw/_quarentena/` com o motivo padronizado
- **AND** o campo `payload` contém o registro original completo
- **AND** `quarantined_at` registra o momento exato da rejeição

#### Scenario: Quarentena não derruba o job

- **WHEN** a própria escrita na quarentena falha (e.g., disco cheio)
- **THEN** o erro é registrado em log
- **AND** o loader continua processando os demais registros
- **AND** o job não é interrompido

#### Scenario: Motivos padronizados

- **WHEN** registros são enviados para a quarentena
- **THEN** o campo `motivo` contém exclusivamente um dos valores padronizados: `uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`, `duplicata_na_chave`
- **AND** nenhum motivo ad-hoc ou texto livre é aceito

### Requirement: Quarentena legível para investigação

A quarentena SHALL ser escrita em formato que permita consulta posterior (Parquet ou CSV). Um analista SHALL conseguir abrir a quarentena, filtrar por `motivo` ou `_load_id`, e ver o registro original no `payload`.

#### Scenario: Consulta por motivo

- **WHEN** um analista lê a quarentena e filtra por `motivo == 'uf_invalida'`
- **THEN** obtém todos os registros rejeitados por UF inválida
- **AND** cada registro tem seu `payload` original legível
