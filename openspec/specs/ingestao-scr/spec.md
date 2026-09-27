# ingestao-scr Specification

## Purpose
Ingere a série histórica do SCR.data (Banco Central) a partir dos ZIPs anuais publicados, produzindo a tabela `bronze_scr` em disco com metadados técnicos de rastreabilidade, pronta para a camada Silver consumir.

## Requirements

### Requirement: Download e descompactação dos ZIPs anuais

O loader SHALL baixar os ZIPs do SCR.data para cada ano no intervalo `ANO_INICIO` a `ANO_FIM` (definidos em `src/config.py`), usando o template de URL `SCR_URL_TEMPLATE`. O loader SHALL aceitar, opcionalmente, uma lista explícita de anos a processar; sem ela, processa o intervalo inteiro.

O download SHALL ter tempo limite de conexão e de leitura definido em `src/config.py`. Estourar o tempo limite SHALL ser tratado como qualquer outra falha de rede. O download SHALL tratar erros HTTP e de rede como falha reportada com o ano e o motivo, sem derrubar o job — a falha de um ano não SHALL impedir o processamento dos demais. Um download interrompido não SHALL deixar no caminho final um ZIP incompleto que seria reaproveitado na execução seguinte.

A pasta de download e o nome do arquivo ZIP SHALL vir de `src/config.py`. O nome do arquivo SHALL ser o mesmo usado pelo script de amostras da Sprint 1 (`scrdata_{ano}.zip`, igual ao nome publicado pelo BCB).

Antes de baixar, o loader SHALL consultar a versão publicada do ZIP (cabeçalho `ETag` de uma requisição `HEAD`, sem baixar o arquivo) e compará-la com a registrada na tabela de controle. O ZIP SHALL ser baixado somente quando não existir em disco ou quando a versão publicada for diferente da registrada. Se a consulta de versão falhar e o ZIP existir em disco, o loader SHALL usar o arquivo local e registrar o aviso em log. Um modo explícito de forçar o redownload SHALL existir.

#### Scenario: Download bem-sucedido de todos os anos

- **WHEN** o loader é executado pela primeira vez e todos os ZIPs do intervalo respondem 200
- **THEN** cada ZIP é salvo localmente e lido, produzindo os CSVs mensais
- **AND** a versão (`ETag`) de cada ZIP é registrada na tabela de controle
- **AND** o número de CSVs encontrados é registrado em log

#### Scenario: ZIP de um ano responde 404

- **WHEN** o ZIP de um determinado ano devolve 404 ou outro erro HTTP
- **THEN** o loader registra o ano e o código de erro em log
- **AND** os demais anos continuam sendo processados normalmente
- **AND** o job não é interrompido

#### Scenario: Servidor não responde

- **WHEN** o servidor do BCB aceita a conexão mas para de enviar dados por mais tempo que o limite configurado
- **THEN** o download daquele ano é abortado e registrado em log como falha
- **AND** nenhum ZIP incompleto fica no caminho final
- **AND** os demais anos continuam sendo processados

#### Scenario: ZIP já existe localmente

- **WHEN** o `ETag` publicado do ZIP de um ano é igual ao registrado na tabela de controle e o ZIP está em disco
- **THEN** o loader não baixa o ZIP
- **AND** a saída indica que o arquivo foi reaproveitado porque o ano não mudou

#### Scenario: ZIP foi republicado

- **WHEN** o `ETag` publicado do ZIP de um ano é diferente do registrado na tabela de controle
- **THEN** o loader baixa o ZIP novo, substituindo o arquivo local
- **AND** passa à comparação CSV a CSV

#### Scenario: Consulta de versão falha com ZIP em disco

- **WHEN** a requisição `HEAD` falha por erro de rede e o ZIP do ano está em disco
- **THEN** o loader usa o ZIP local e registra o aviso em log
- **AND** o job não é interrompido

#### Scenario: Processamento de anos escolhidos

- **WHEN** o loader é chamado com a lista de anos `[2024]`
- **THEN** apenas o ZIP de 2024 é consultado, baixado (ou reaproveitado) e processado
- **AND** nenhum outro ano é requisitado

### Requirement: Leitura dos CSVs com contrato explícito

O loader SHALL ler cada CSV mensal (`scrdata_AAAAMM.csv`) usando encoding e separador vindos de `src/config.py` — nunca valores chumbados no código do loader. O encoding SHALL ser determinado testando os candidatos de `SCR_ENCODINGS_CANDIDATOS` na ordem declarada.

O loader SHALL ler **todas** as colunas do CSV e SHALL mantê-las **como texto**, exatamente como vieram da fonte, sem conversão de tipo nem de separador decimal. A seleção das cinco colunas de `SCR_COLUNAS_USADAS` e a tipagem são responsabilidade da Silver (seção 4.1 de `docs/architecture.md`).

A leitura SHALL ser feita em blocos de tamanho limitado, sem carregar o CSV inteiro em memória, e SHALL NOT deixar arquivos temporários em disco depois de terminar, com ou sem erro.

O loader SHALL conferir o cabeçalho de **cada** CSV individualmente, comparando com `SCR_COLUNAS_USADAS`. Se uma coluna esperada estiver ausente, o CSV SHALL ser rejeitado com registro do motivo em log e o processamento dos demais CSVs SHALL continuar. Essa é uma rejeição **estrutural** (o arquivo não serve ao projeto), não uma regra de negócio sobre registros.

#### Scenario: CSV com layout esperado

- **WHEN** um CSV do SCR é lido e as cinco colunas de `SCR_COLUNAS_USADAS` estão presentes
- **THEN** o resultado contém todas as colunas do CSV, não apenas as cinco usadas
- **AND** o encoding é resolvido sem fallback para `latin-1` em arquivo UTF-8

#### Scenario: Valores preservados como texto

- **WHEN** um CSV traz `carteira_ativa` igual a `1234,56` e `numero_de_operacoes` igual a `-1`
- **THEN** a Bronze guarda exatamente os textos `1234,56` e `-1`
- **AND** nenhum valor é convertido para número ou data na Bronze

#### Scenario: CSV com coluna ausente

- **WHEN** um CSV do SCR não contém uma ou mais colunas de `SCR_COLUNAS_USADAS`
- **THEN** o CSV é rejeitado e o motivo é registrado em log, nomeando as colunas ausentes
- **AND** os demais CSVs do mesmo ano continuam sendo processados

#### Scenario: Cabeçalho de ano antigo difere de 2024

- **WHEN** o CSV de um ano anterior a 2024 tem cabeçalho diferente do de 2024 (colunas extras ou reordenadas), mas contém as cinco colunas usadas
- **THEN** a leitura é bem-sucedida e preserva as colunas daquele arquivo como vieram
- **AND** nenhuma suposição sobre a posição das colunas é feita

#### Scenario: Nenhum arquivo temporário sobra

- **WHEN** o loader termina de processar um ZIP, com sucesso ou com erro
- **THEN** nenhum CSV descompactado permanece em pasta temporária do sistema

### Requirement: Metadados técnicos na Bronze

Toda linha da `bronze_scr` SHALL conter os metadados técnicos definidos na seção 3.1 de `docs/architecture.md`: `_ingestion_timestamp`, `_ingestion_date`, `_source_system` (fixo em `scr_data`), `_source_object`, `_load_id` (identificador único da execução), `_ingestion_mode` (fixo em `full`) e `_record_hash`.

`_source_object` SHALL identificar a **versão** do CSV de origem no formato `<nome do CSV>@<data do arquivo dentro do ZIP em ISO 8601>` (e.g., `scrdata_202408.csv@2026-09-15T02:38:32`). Duas publicações diferentes do mesmo mês SHALL gerar `_source_object` diferentes.

O `_record_hash` SHALL ser o SHA-256 do conteúdo do registro concatenado com `_source_object`, conforme a seção 3.2 de `docs/architecture.md`.

#### Scenario: Metadados presentes em toda linha

- **WHEN** o loader produz a `bronze_scr`
- **THEN** todas as sete colunas de metadados estão presentes em cada linha
- **AND** `_source_object` identifica o CSV e a versão de origem (e.g., `scrdata_202401.csv@2026-03-25T17:29:40`)
- **AND** `_record_hash` é um hash SHA-256 hexadecimal de 64 caracteres

#### Scenario: Mesmo load_id em toda a execução

- **WHEN** o loader processa vários CSVs em uma única execução
- **THEN** todas as linhas dessa execução compartilham o mesmo `_load_id`
- **AND** execuções diferentes geram `_load_id` distintos

#### Scenario: Linha igual em versões diferentes do mesmo mês

- **WHEN** uma linha tem o mesmo conteúdo na versão antiga e na versão republicada de `scrdata_202408.csv`
- **THEN** as duas ocorrências têm `_record_hash` diferentes, porque o `_source_object` difere pela versão

### Requirement: Escrita em disco particionada por data

O loader SHALL escrever a `bronze_scr` em `data/raw/` no formato Parquet, particionada por `_ingestion_date`. A escolha de Parquet é intencional: comprime bem e é lido nativamente pelo pandas. As colunas vindas da fonte SHALL ser gravadas como texto.

#### Scenario: Arquivos particionados em disco

- **WHEN** o loader conclui uma execução com sucesso
- **THEN** os arquivos Parquet estão em `data/raw/bronze_scr/`
- **AND** existe uma subpasta por `_ingestion_date`
- **AND** o dado pode ser lido de volta com `pd.read_parquet()` com os mesmos textos da fonte

### Requirement: Bronze sem regra de negócio

O loader SHALL gravar na Bronze todo registro de um CSV legível, sem aplicar checagens de negócio (UF, intervalo de datas, sinal ou tipo dos valores) e sem desviar registros para a quarentena. Validação de negócio e quarentena são responsabilidade da Silver (seção 4.1 de `docs/architecture.md`). O job não SHALL ser interrompido por registros com conteúdo inesperado.

#### Scenario: Registro sujo entra intacto na Bronze

- **WHEN** um CSV legível contém um registro com `uf` igual a `XX` e `carteira_ativa` igual a `abc`
- **THEN** o registro é gravado na `bronze_scr` com os textos `XX` e `abc`, como vieram
- **AND** nenhum arquivo é escrito na quarentena pelo loader
- **AND** o job conclui sem exceção não tratada

#### Scenario: Registros fora do recorte temporal são preservados

- **WHEN** o ZIP de 2016 contém CSVs de janeiro a junho, anteriores ao recorte do projeto
- **THEN** esses registros são gravados na Bronze como vieram
- **AND** o recorte a partir de julho/2016 fica a cargo da Silver

#### Scenario: Definição de pronto da Sprint 2 exercita o loader real

- **WHEN** o loader do SCR é executado de ponta a ponta sobre um ZIP local com um CSV válido, um registro de UF `XX` e um CSV sem a coluna `uf`
- **THEN** a `bronze_scr` é criada em disco com todas as linhas do CSV válido, inclusive a de UF `XX`
- **AND** o CSV sem a coluna `uf` não aparece na Bronze e sua rejeição consta no log
- **AND** o job conclui sem exceção

### Requirement: Ingestão por versão de CSV

O loader SHALL manter, na tabela de controle do SCR, para cada CSV já ingerido: o nome, a data do arquivo dentro do ZIP e o CRC32 informado pelo índice do ZIP. Ao processar um ZIP, o loader SHALL ingerir somente os CSVs novos ou cuja data ou CRC32 difira do registrado. CSVs sem alteração SHALL ser pulados sem serem lidos.

O registro de um CSV na tabela de controle SHALL ser gravado somente depois que todas as suas linhas tiverem sido gravadas na Bronze.

#### Scenario: Republicação de um único mês

- **WHEN** o ZIP de 2024 é republicado e só `scrdata_202408.csv` mudou (nova data e novo CRC32)
- **THEN** apenas `scrdata_202408.csv` é lido e gravado, como uma nova versão
- **AND** as linhas da versão anterior de agosto continuam na Bronze
- **AND** os outros 11 meses de 2024 não são lidos

#### Scenario: Mês novo publicado

- **WHEN** o ZIP de 2026 passa a conter `scrdata_202608.csv`, que não está na tabela de controle
- **THEN** somente esse CSV é ingerido
