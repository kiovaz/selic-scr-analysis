## 1. Módulo de validação e quarentena

- [x] 1.1 Criar `src/validation/quality_checks.py` com as funções de checagem: `checar_uf(valor, config) → Optional[str]`, `checar_data_no_intervalo(valor, config) → Optional[str]`, `checar_valor_nao_negativo(valor, coluna) → Optional[str]`, `checar_tipagem(valor, tipo_esperado) → Optional[str]`. Cada uma retorna o motivo padronizado (`uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`) ou `None`. A checagem de valor negativo NÃO deve rejeitar `-1` em `numero_de_operacoes` (é máscara do BCB, tratada na Silver). Verificar: `pytest tests/test_validation.py` passa com casos de sucesso e falha para cada checagem.

- [x] 1.2 Criar a função `enviar_para_quarentena(registro, motivo, load_id, source_system, source_object, dir_quarentena)` no mesmo módulo. Escreve em Parquet append-only em `data/raw/_quarentena/`, com colunas `_load_id`, `_source_system`, `_source_object`, `motivo`, `payload` (JSON string do registro original) e `quarantined_at`. A escrita na quarentena NUNCA deve levantar exceção que derrube o job — erro de I/O é logado e ignorado. Verificar: `pytest tests/test_validation.py` confirma que um registro rejeitado aparece na quarentena com motivo e payload corretos.

- [x] 1.3 Criar `tests/test_validation.py` cobrindo: registro válido passa em todas as checagens; UF inválida retorna `uf_invalida`; data fora do intervalo retorna `data_fora_do_intervalo`; valor negativo retorna `valor_negativo`; tipo inconversível retorna `tipagem_invalida`; `-1` em `numero_de_operacoes` NÃO é rejeitado; registro vai para quarentena com payload e motivo corretos; motivos são exclusivamente os 5 padronizados. Verificar: `pytest tests/test_validation.py -v` com todos os testes passando.

## 2. Funções auxiliares de metadados

- [x] 2.1 Criar funções auxiliares (em `src/ingestion/` ou `src/utils/`) para: gerar `_load_id` (UUID4 por execução), calcular `_record_hash` (SHA-256 do conteúdo concatenado com `_source_object`), e anexar as 7 colunas de metadados (`_ingestion_timestamp`, `_ingestion_date`, `_source_system`, `_source_object`, `_load_id`, `_ingestion_mode`, `_record_hash`) a um DataFrame. Verificar: teste unitário confirma que o hash de dois registros iguais com `_source_object` diferente produz hashes diferentes, e que as 7 colunas estão presentes.

## 3. Loader do SCR.data

- [x] 3.1 Implementar `src/ingestion/scr_file_loader.py` — função de download que baixa o ZIP de cada ano (`ANO_INICIO` a `ANO_FIM`) usando `SCR_URL_TEMPLATE` do `config.py`. Salva em um diretório local. Se o ZIP já existir, reaproveita sem rebaixar (com flag para forçar redownload). Erros HTTP de um ano são logados e não impedem os demais. Verificar: executar o loader com um ano válido confirma que o ZIP é salvo em disco; executar com um ano inválido (e.g., 2099) loga o erro sem exceção.

- [x] 3.2 Implementar a descompactação do ZIP e leitura de cada CSV mensal. Usar encoding de `SCR_ENCODINGS_CANDIDATOS` (testando na ordem), separador `SCR_SEPARADOR`, e conferir o cabeçalho de cada CSV contra `SCR_COLUNAS_USADAS`. CSV com coluna ausente é rejeitado com log e os demais continuam. Verificar: criar um CSV de teste com cabeçalho correto e um com coluna ausente; o primeiro é lido com sucesso, o segundo é rejeitado com log.

- [x] 3.3 Integrar validação: após ler cada CSV, submeter os registros às checagens de `quality_checks.py`. Registros inválidos vão para a quarentena; registros válidos recebem metadados técnicos (task 2.1) e são escritos em Parquet em `data/raw/bronze_scr/`, particionados por `_ingestion_date`. Verificar: após execução, `pd.read_parquet("data/raw/bronze_scr/")` devolve DataFrame com as 7 colunas de metadados; injetar um registro com UF `"XX"` confirma que ele aparece na quarentena e não na Bronze.

## 4. Loader da Selic

- [x] 4.1 Implementar `src/ingestion/selic_api_loader.py` — função de requisição à API do Ipeadata usando `SELIC_URL` do `config.py`, com timeout de 30s e retry com backoff exponencial (3 tentativas, base 2s). Cada tentativa e resultado são logados. Se todas falharem, registra a falha e encerra sem exceção. Verificar: em condições normais de rede, a requisição retorna os registros; simular falha (URL errada) confirma que 3 tentativas são feitas com log de cada uma.

- [x] 4.2 Implementar parsing da resposta OData: extrair `VALDATA` (→ date) e `VALVALOR` (→ float) da chave `value`. Aplicar recorte temporal (`>= julho/ANO_INICIO`). Campo malformado é desviado para quarentena com motivo `tipagem_invalida`. Verificar: parsing de uma resposta de exemplo produz DataFrame com colunas `VALDATA` (date) e `VALVALOR` (float), sem registros anteriores a jul/2016.

- [x] 4.3 Integrar validação e escrita: submeter registros às checagens de `quality_checks.py`, desviar inválidos para quarentena, anexar metadados técnicos (com `_source_system = "ipeadata"` e `_source_object` = URL), escrever em Parquet em `data/raw/bronze_selic/` particionado por `_ingestion_date`. Verificar: `pd.read_parquet("data/raw/bronze_selic/")` devolve DataFrame com metadados completos; `_source_system` é `"ipeadata"` em toda linha.

## 5. Testes de integração

- [x] 5.1 Criar `tests/test_ingestion.py` com testes para ambos os loaders: SCR carrega ao menos um CSV e produz Bronze com metadados; Selic requisita a API e produz Bronze com metadados; registro sujo injetado de propósito (UF inválida no SCR, valor negativo na Selic) cai na quarentena sem derrubar o job; `_load_id` é consistente dentro de uma execução. Verificar: `pytest tests/test_ingestion.py -v` com todos os testes passando.

- [x] 5.2 Testar o cenário da definição de pronto: "os dois loaders rodam do zero e produzem `bronze_scr` e `bronze_selic` em disco, e um registro sujo injetado de propósito cai na quarentena sem derrubar o job". Verificar: `pytest tests/test_ingestion.py::test_definicao_de_pronto_sprint2 -v` passa.

## 6. Integração com o pipeline e documentação

- [x] 6.1 Atualizar `scripts/run_pipeline.py` para chamar os dois loaders na etapa de ingestão Bronze, em vez de apenas imprimir o checklist. Verificar: `python scripts/run_pipeline.py` executa a ingestão e produz os arquivos em `data/raw/`.

- [x] 6.2 Preencher as seções `bronze_scr` e `bronze_selic` de `docs/data_dictionary.md` marcadas como "Preencher na Sprint 2": listar as colunas de origem do CSV e da API, com tipo, domínio e significado, conforme o formato já existente no dicionário. Verificar: `docs/data_dictionary.md` não contém mais nenhum texto "Preencher na Sprint 2".

- [x] 6.3 Exportar `__init__.py` de `src/ingestion/` e `src/validation/` com os imports públicos dos módulos criados. Verificar: `from src.ingestion.scr_file_loader import carregar_scr` e `from src.validation.quality_checks import checar_uf` funcionam sem erro de import.
