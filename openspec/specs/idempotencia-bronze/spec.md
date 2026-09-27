# idempotencia-bronze Specification

## Purpose
Garante que a camada Bronze pode ser reconstruída e reexecutada com segurança: rodar a ingestão de novo não duplica linhas, versões republicadas pela fonte são preservadas sem se misturar, e uma execução interrompida é completada sem duplicar (seção 3.2 de `docs/architecture.md`).

## Requirements

### Requirement: Reexecução não altera a contagem

Rodar a ingestão das duas fontes duas vezes seguidas, sem mudança nas fontes, SHALL deixar a `bronze_scr` e a `bronze_selic` com exatamente a mesma contagem de linhas da primeira execução.

#### Scenario: Pipeline rodado duas vezes

- **WHEN** o pipeline é executado e, em seguida, executado de novo sem que o BCB ou o Ipeadata tenham publicado nada novo
- **THEN** a contagem de linhas de `bronze_scr` e de `bronze_selic` é igual à da primeira execução
- **AND** a segunda execução não baixa nenhum ZIP do SCR

#### Scenario: Tabela de controle apagada

- **WHEN** a tabela de controle do SCR é apagada, mas a `bronze_scr` continua em disco, e o pipeline é executado de novo
- **THEN** o loader reconstrói o controle a partir das versões (`_source_object`) presentes na Bronze antes de ingerir
- **AND** a contagem de linhas da `bronze_scr` não muda

### Requirement: Chave da Bronze sem duplicata

A chave `(_source_object, _record_hash)` de `bronze_scr` e de `bronze_selic` (seção 4.2 de `docs/architecture.md`) SHALL NOT ter duplicatas.

#### Scenario: Prova da chave

- **WHEN** a Bronze é lida depois de qualquer sequência de execuções (inclusive repetidas e interrompidas)
- **THEN** `df.duplicated(["_source_object", "_record_hash"]).sum() == 0` nas duas tabelas

### Requirement: Versões republicadas são preservadas

Quando a fonte republica um conteúdo já ingerido com alterações, a Bronze SHALL guardar a versão nova completa **e** manter a versão anterior. Nenhuma linha já gravada SHALL ser apagada ou alterada.

#### Scenario: Mês republicado pelo BCB

- **WHEN** `scrdata_202408.csv` já foi ingerido com 310.266 linhas e o BCB o republica com 310.263 linhas
- **THEN** a Bronze passa a ter as 310.266 linhas da versão antiga e as 310.263 da versão nova, identificadas por `_source_object` diferentes
- **AND** a contagem total aumenta exatamente em 310.263

### Requirement: Execução interrompida é completada sem duplicar

Se uma execução for interrompida no meio da gravação de uma versão de arquivo, a execução seguinte SHALL gravar apenas as linhas que faltam daquela versão, comparando `_record_hash` somente entre linhas do mesmo `_source_object`.

#### Scenario: Queda no meio de um CSV

- **WHEN** a gravação de um CSV de 300 mil linhas é interrompida depois do primeiro bloco de 200 mil
- **THEN** a execução seguinte grava apenas as 100 mil linhas restantes daquela versão
- **AND** ao final a versão tem as 300 mil linhas, sem duplicata na chave
