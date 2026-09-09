## Why

A Sprint 1 confirmou que as duas fontes públicas (SCR.data e Selic) existem, estão acessíveis e no formato documentado. Mas os diretórios `src/ingestion/` e `src/validation/` ainda estão vazios: não há código que transforme essas fontes em dados Bronze prontos para a Silver consumir. Sem os loaders, o pipeline inteiro é um diagrama — nenhuma sprint seguinte pode avançar.

A Sprint 2 existe para fechar essa lacuna: produzir `bronze_scr` e `bronze_selic` em disco, com metadados técnicos rastreáveis e quarentena funcionando, de modo que a Sprint 3 (idempotência e CI) e a Sprint 4 (Silver/Gold) tenham dado real para processar.

## What Changes

- **Novo:** `src/ingestion/scr_file_loader.py` — loader que baixa o ZIP do SCR.data ano a ano (de `ANO_INICIO` a `ANO_FIM`), descompacta, lê cada CSV mensal com encoding, separador e tipagem explícitos (via `src/config.py`), anexa metadados técnicos (seção 3.1) e escreve `bronze_scr` em `data/raw/`. Confere o cabeçalho de cada ano individualmente — não assume o layout de 2024.
- **Novo:** `src/ingestion/selic_api_loader.py` — loader que requisita a série `BM12_TJOVER12` no Ipeadata com timeout, tratamento de erro e retry com backoff exponencial, anexa metadados técnicos e escreve `bronze_selic` em `data/raw/`.
- **Novo:** `src/validation/quality_checks.py` — módulo de validação reutilizável com checagens padronizadas (UF válida, data no intervalo, tipagem, valores negativos) que os loaders consomem antes de escrever a Bronze.
- **Novo:** sistema de quarentena em `data/raw/_quarentena/` — registros com problemas são desviados com motivo padronizado e payload original preservado, sem derrubar o job.
- **Novo:** `tests/test_ingestion.py` — testes dos dois loaders, incluindo cenário de registro sujo injetado de propósito caindo na quarentena.
- **Atualização:** `docs/data_dictionary.md` — preencher as seções `bronze_scr` e `bronze_selic` marcadas como "Preencher na Sprint 2".
- **Atualização:** `scripts/run_pipeline.py` — integrar a chamada dos dois loaders no script de execução.

## Capabilities

### New Capabilities
- `ingestao-scr`: Ingestão do SCR.data — download do ZIP, descompactação, leitura de CSVs com encoding/separador/tipagem explícitos, conferência de cabeçalho por ano, metadados técnicos e escrita na Bronze.
- `ingestao-selic`: Ingestão da Selic via API — requisição com timeout/retry/backoff, metadados técnicos e escrita na Bronze.
- `validacao-bronze`: Validação e quarentena na camada Bronze — checagens padronizadas de domínio, tipagem e faixa, com desvio para quarentena sem interrupção do job.

### Modified Capabilities
*(Nenhuma — as capabilities da Sprint 1 (diagnostico-fontes) não mudam de requisitos. Os loaders consomem as constantes de `config.py` que a Sprint 1 conferiu, mas não alteram a spec de diagnóstico.)*

## Impact

- **Código novo:** três módulos em `src/` (dois loaders + validação), testes em `tests/`.
- **Dados em disco:** após a primeira execução, `data/raw/` passa a conter arquivos Parquet particionados (~1 GB+ para a série completa do SCR, ~50 KB para a Selic).
- **Dependências:** nenhuma biblioteca nova além do que já está em `requirements.txt` (pandas, requests). Retry com backoff usa lógica interna (loop com `time.sleep`), sem biblioteca adicional.
- **Documentação:** `docs/data_dictionary.md` ganha as colunas concretas das tabelas Bronze.
- **Pipeline:** `scripts/run_pipeline.py` passa a executar a ingestão de fato, não apenas imprimir o checklist.
