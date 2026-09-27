## MODIFIED Requirements

### Requirement: Requisição à API com resiliência

O loader SHALL requisitar a série definida em `SELIC_SERIE` de `src/config.py` — hoje `BM366_TJOVER366`, a **Selic meta fixada pelo Copom, diária, em % ao ano** (seção 2.2 de `docs/architecture.md`) — no endpoint OData v4 do Ipeadata, usando a URL definida em `src/config.py` (`SELIC_URL`). A requisição SHALL usar timeout configurável e, em caso de falha de rede ou erro HTTP, SHALL fazer retry com backoff exponencial até um número máximo de tentativas.

Cada tentativa e seu resultado (sucesso ou erro) SHALL ser registrados em log.

#### Scenario: API responde com sucesso

- **WHEN** o loader requisita a série e a API responde 200 com registros na chave `value`
- **THEN** todos os registros são extraídos
- **AND** a contagem de registros recebidos é registrada em log

#### Scenario: API falha temporariamente

- **WHEN** a API devolve erro de rede ou HTTP 5xx nas primeiras tentativas
- **THEN** o loader faz retry com backoff exponencial
- **AND** cada tentativa é registrada em log com o motivo da falha
- **AND** se uma tentativa subsequente tiver sucesso, o processamento continua normalmente

#### Scenario: API falha em todas as tentativas

- **WHEN** todas as tentativas de requisição são esgotadas sem sucesso
- **THEN** o loader registra a falha final em log
- **AND** o job é encerrado sem exceção não tratada, com mensagem clara do motivo

#### Scenario: Resposta vazia

- **WHEN** a API responde com sucesso mas a chave `value` está vazia
- **THEN** o loader registra que a série veio vazia
- **AND** nenhum arquivo Bronze é escrito para esta execução
- **AND** o job é encerrado sem exceção

#### Scenario: Série diária

- **WHEN** a série configurada é diária
- **THEN** cada dia devolvido pela API vira uma linha da `bronze_selic`, como veio
- **AND** o watermark da carga incremental passa a ser um dia (`AAAA-MM-DD`)
