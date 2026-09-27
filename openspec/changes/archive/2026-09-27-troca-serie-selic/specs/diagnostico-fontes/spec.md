## MODIFIED Requirements

### Requirement: Conferência do contrato da Selic

O diagnóstico SHALL requisitar a série da Selic no Ipeadata e reportar a contagem de registros, os campos disponíveis no primeiro registro, o primeiro e o último registro da série. Os registros vêm dentro da chave `value` da resposta OData.

A saída SHALL declarar explicitamente a unidade da série configurada, lida de `SELIC_UNIDADE` em `src/config.py` (hoje **% ao ano**, a meta do Copom), para que a unidade não seja confundida em nenhuma etapa seguinte. A unidade SHALL NOT ser escrita fixa no script.

#### Scenario: Série recebida

- **WHEN** a API do Ipeadata responde com registros
- **THEN** a saída mostra a contagem de registros, os campos `SERCODIGO`, `VALDATA` e `VALVALOR`, e o primeiro e o último registro
- **AND** a última competência disponível (`VALDATA` do último registro) é destacada

#### Scenario: Resposta vazia

- **WHEN** a API responde com sucesso mas a chave `value` vem vazia
- **THEN** a saída reporta que a série veio vazia e precisa ser investigada
- **AND** o processo termina sem exceção

#### Scenario: Unidade vinda da configuração

- **WHEN** o diagnóstico da Selic é executado
- **THEN** a saída mostra a série e a unidade definidas em `src/config.py`
