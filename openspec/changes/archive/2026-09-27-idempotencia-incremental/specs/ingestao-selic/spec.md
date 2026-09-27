## MODIFIED Requirements

### Requirement: Metadados técnicos na Bronze

Toda linha da `bronze_selic` SHALL conter os metadados técnicos da seção 3.1: `_ingestion_timestamp`, `_ingestion_date`, `_source_system` (fixo em `ipeadata`), `_source_object` (URL do endpoint), `_load_id`, `_ingestion_mode` e `_record_hash`.

`_ingestion_mode` SHALL ser `full` na primeira carga (quando ainda não há watermark) e `incremental` nas cargas seguintes.

O `_record_hash` SHALL ser o SHA-256 do conteúdo do registro concatenado com `_source_object`.

#### Scenario: Metadados presentes em toda linha

- **WHEN** o loader produz a `bronze_selic`
- **THEN** todas as sete colunas de metadados estão presentes em cada linha
- **AND** `_source_system` é `ipeadata`
- **AND** `_source_object` é a URL usada na requisição

#### Scenario: Modo da carga

- **WHEN** o loader roda pela primeira vez e depois roda de novo
- **THEN** as linhas da primeira execução têm `_ingestion_mode` igual a `full`
- **AND** as linhas gravadas nas execuções seguintes têm `_ingestion_mode` igual a `incremental`

## ADDED Requirements

### Requirement: Carga incremental por watermark

O loader SHALL manter uma tabela de controle com o watermark da Selic: a maior `VALDATA` já gravada na Bronze. Como a API do Ipeadata não aplica filtros (`$filter`, `$top`, `$orderby` são ignorados), o loader SHALL continuar requisitando a série inteira, mas SHALL gravar somente os registros com `VALDATA` maior ou igual ao watermark cujo `_record_hash` ainda não exista na `bronze_selic`.

O registro do mês do watermark SHALL ser reavaliado a cada execução, porque o mês corrente muda de valor até fechar: se o valor mudou, a nova leitura entra como uma nova linha (hash diferente), e a anterior é preservada. A escolha da leitura mais recente de cada mês é responsabilidade da Silver.

O watermark SHALL ser atualizado somente depois que a gravação na Bronze terminar com sucesso.

#### Scenario: Nada mudou na API

- **WHEN** o loader roda duas vezes seguidas e a API devolve exatamente os mesmos registros
- **THEN** a segunda execução não grava nenhuma linha
- **AND** a contagem da `bronze_selic` não muda

#### Scenario: Mês corrente mudou de valor

- **WHEN** na primeira execução setembro/2026 vale `0.88` e na execução seguinte vale `1.05`
- **THEN** a segunda execução grava uma única linha nova, a de setembro com `1.05`
- **AND** a linha de setembro com `0.88` continua na Bronze

#### Scenario: Mês novo publicado

- **WHEN** a API passa a devolver outubro/2026, posterior ao watermark
- **THEN** a linha de outubro é gravada
- **AND** o watermark passa a ser outubro/2026

#### Scenario: Registros antigos não são regravados

- **WHEN** a API devolve os registros de 1974 a 2026 numa execução incremental
- **THEN** nenhum registro com `VALDATA` anterior ao watermark é gravado de novo
