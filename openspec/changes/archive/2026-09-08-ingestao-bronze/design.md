## Context

A Sprint 1 confirmou que as duas fontes estão acessíveis e no formato documentado (ver `proposal.md — Why`). Os diretórios `src/ingestion/` e `src/validation/` existem mas estão vazios — só têm `__init__.py`. As constantes de leitura (encoding, separador, colunas, URLs) já estão em `src/config.py`, conferidas na Sprint 1 sobre a amostra de 2024.

O que existe hoje:
- `scripts/baixar_amostras.py` — baixa e inspeciona uma amostra de um ano. Não faz ingestão.
- `src/config.py` — caminhos, URLs, constantes de negócio. Inclui `DIR_QUARENTENA` já definido.
- `notebooks/01_exploracao_amostras.ipynb` — exploração da amostra de 2024, com saídas gravadas.
- `docs/architecture.md` — especificação completa (seções 3, 4, 8).

Restrições da stack: Python 3.11, pandas, requests, pytest. Nada além do que está no `requirements.txt`. Retry com backoff é feito com lógica interna (loop + `time.sleep`), sem biblioteca adicional.

## Goals / Non-Goals

**Goals:**
- Produzir `bronze_scr` e `bronze_selic` em Parquet, particionados por `_ingestion_date`, em `data/raw/`.
- Cada linha com os 7 metadados técnicos da seção 3.1.
- Quarentena funcional: registro sujo vai para `data/raw/_quarentena/` sem derrubar o job.
- Conferir cabeçalho de cada ano do SCR individualmente.
- Testes cobrindo os cenários da spec, incluindo injeção de registro sujo.

**Non-Goals:**
- **Idempotência e deduplicação** — Sprint 3. O `_record_hash` é calculado e gravado agora, mas a checagem de "já ingerido" fica para a Sprint 3 com `test_idempotencia.py`.
- **Carga incremental da Selic** — Sprint 3 (watermark).
- **Transformação Silver/Gold** — Sprint 4.
- **Validações de negócio avançadas** (e.g., tratar `-1` como nulo) — responsabilidade da Silver, não da Bronze.

## Decisions

### 1. Formato de saída: Parquet (não CSV)

A Bronze grava em Parquet, não CSV.

**Rationale:** Parquet preserva tipos nativamente (date, int64, float64, string), comprime por coluna (~3–5× menor que CSV), e `pd.read_parquet()` reconstrói o DataFrame sem `dtype=` manual. CSV exigiria re-parsear tipagem na Silver — o que é exatamente o tipo de retrabalho que a Bronze evita.

**Alternativa descartada:** CSV com `_schema.json` ao lado — manteria a legibilidade humana, mas o dado já foi inspecionado na Sprint 1 (notebook). A partir daqui, quem lê a Bronze é código, não pessoa.

### 2. Particionamento por `_ingestion_date` (não por `data_base`)

Particionamos pelo **dia da ingestão**, não pelo mês de referência dos dados.

**Rationale:** a Bronze registra "quando o dado entrou", não "quando o dado aconteceu". Isso permite, na Sprint 3, identificar e apagar/reprocessar uma execução inteira (todos os arquivos de um `_ingestion_date`) sem misturar com execuções anteriores. Particionar por `data_base` criaria pastas que misturam linhas de execuções diferentes, dificultando rollback.

**Alternativa considerada:** duplo nível `_ingestion_date/data_base` — granularidade fina demais para o volume deste projeto (~3,7M linhas/ano) e sem benefício prático enquanto não houver carga incremental.

### 3. Retry da Selic: loop interno com backoff exponencial

A API do Ipeadata não exige autenticação, mas é instável (há relatos de timeout e 500 intermitentes). O retry usa um loop com `time.sleep(base * 2^tentativa)`, máximo de 3 tentativas, sem biblioteca adicional.

**Rationale:** `tenacity` ou `urllib3.Retry` resolveriam com menos código, mas a stack do projeto (seção 7 de `architecture.md`) é deliberadamente enxuta — cada dependência precisa ser justificável na apresentação. Um loop de 15 linhas é mais fácil de explicar que uma dependência.

**Alternativa descartada:** `requests.adapters.HTTPAdapter` com `Retry` do `urllib3` — tecnicamente correto, mas exige saber explicar o adapter pattern do `requests.Session`, o que não agrega para o escopo do projeto.

### 4. Validação como módulo separado, não inline nos loaders

As checagens ficam em `src/validation/quality_checks.py`, chamadas pelos loaders via import. Isso separa a decisão "o que é válido" de "como ler a fonte".

**Rationale:** quando a Silver implementar suas próprias validações (Sprint 4), ela pode importar ou compor com o mesmo módulo. Se as checagens estivessem inline no loader do SCR, a Selic teria que duplicar a lógica — e a Silver não teria acesso a nenhuma delas.

**Alternativa descartada:** classe `Validator` com herança por fonte — overengineering. Funções simples com assinatura `(row, config) → Optional[str]` bastam para o volume de regras deste projeto.

### 5. Quarentena em Parquet append-only

A quarentena grava em `data/raw/_quarentena/` como Parquet, um arquivo por `_load_id`. Não usa CSV para manter consistência de formato com a Bronze.

**Rationale:** um analista pode abrir a quarentena com `pd.read_parquet()` e filtrar por `motivo`, sem se preocupar com quoting de JSON no payload. O payload original é serializado como string JSON dentro de uma coluna `payload` do tipo string.

**Trade-off aceito:** Parquet não é tão legível "a olho" quanto CSV. Como a quarentena é para investigação e não para consumo visual rotineiro, é um trade-off aceitável.

### 6. _record_hash inclui _source_object

O hash SHA-256 concatena o conteúdo do registro com o `_source_object` (nome do arquivo CSV ou URL).

**Rationale:** sem isso, duas linhas de conteúdo idêntico vindas de CSVs de meses diferentes produziriam o mesmo hash e a deduplicação da Sprint 3 descartaria uma delas. Incluir o arquivo de origem garante que só o reprocessamento do **mesmo** arquivo gere hash repetido. Está na seção 3.2 de `docs/architecture.md`.

### 7. SCR: download sequencial, processamento por CSV

Os ZIPs são baixados ano a ano sequencialmente. Dentro de cada ZIP, os CSVs mensais são lidos um por vez, validados e gravados.

**Rationale:** download paralelo é desnecessário (são no máximo 11 ZIPs, ~168 MiB cada) e complicaria o logging e o tratamento de erro por ano. O processamento sequencial é simples, previsível e rastreável.

**Alternativa considerada:** `concurrent.futures.ThreadPoolExecutor` para download paralelo — descartado porque a rede doméstica do grupo não é o gargalo, e threads adicionam complexidade de debug que ninguém precisa explicar na apresentação.

## Risks / Trade-offs

- **O ZIP de 2016 pode ter layout diferente dos demais** → Mitigação: cada CSV é conferido individualmente contra `SCR_COLUNAS_USADAS`. Se o layout divergir, o CSV vai para log como rejeitado e os demais anos continuam. O grupo investiga manualmente.
- **A API do Ipeadata pode mudar o formato OData** → Mitigação: o parser espera `value[].VALDATA` e `value[].VALVALOR`. Se a estrutura mudar, o job falha com erro claro (KeyError no parsing), não silenciosamente.
- **Volume de ~1 GB+ em Parquet pode ser grande para disco** → Mitigação: Parquet comprime ~3–5× comparado a CSV. O volume total com todos os anos (~10 anos × ~1 GB CSV) fica em ~2–3 GB em Parquet, aceitável para um projeto acadêmico.
- **A quarentena pode acumular volume se houver muitos registros sujos** → Trade-off aceito: a quarentena é para investigação, não para armazenamento de longo prazo. Limpeza manual quando necessário.
