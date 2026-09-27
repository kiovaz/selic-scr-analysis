# publicacao-gold Specification

## Purpose
Publica as tabelas finais do pipeline (Gold, análise, previsão e decisão) num banco Postgres no Neon, de forma opcional e idempotente, e as mostra num site só de leitura em `web/` (Next.js na Vercel) — decisões 12 e 16 de `docs/architecture.md`.

## Requirements

### Requirement: Publicação opcional

A etapa de publicação SHALL rodar no fim do `run_pipeline.py` somente quando a variável `DATABASE_URL` estiver definida (no ambiente ou no arquivo `.env` da raiz). Sem ela, SHALL registrar um aviso e o pipeline SHALL terminar normalmente. A falta de uma saída em `data/final/` SHALL interromper só a publicação, com a lista do que falta.

#### Scenario: Sem string de conexão

- **WHEN** o pipeline roda sem `DATABASE_URL`
- **THEN** nenhuma conexão é aberta
- **AND** o pipeline termina com sucesso e avisa que a publicação foi pulada

#### Scenario: Saídas faltando

- **WHEN** `DATABASE_URL` está definida mas falta `recomendacao_trimestre.parquet`
- **THEN** nada é enviado ao banco
- **AND** o aviso cita o arquivo que falta

### Requirement: Tabelas substituídas numa transação

A publicação SHALL enviar as tabelas `gold_credito_selic`, `recomendacao_trimestre`, `ml_previsao_producao`, `sensibilidade_limiar`, `analise_brasil_modalidade`, `analise_uf_modalidade` e `frase_fechamento`, recriando cada uma por inteiro (apaga e cria de novo) **dentro de uma única transação**: ou todas são atualizadas, ou nenhuma. Valores ausentes (`NaN`) SHALL virar `NULL`. A publicação SHALL gravar uma linha em `publicacao_controle` com o `_load_id`, o momento e o número de linhas de cada tabela.

#### Scenario: Republicar não duplica

- **WHEN** a publicação roda duas vezes seguidas com os mesmos arquivos
- **THEN** cada tabela tem o mesmo número de linhas do arquivo de origem
- **AND** `publicacao_controle` tem uma linha por execução

#### Scenario: Falha no meio

- **WHEN** o envio de uma tabela falha
- **THEN** a transação é desfeita e o site continua mostrando a publicação anterior

### Requirement: Site de leitura

O site em `web/` SHALL ler o banco **apenas no servidor** (a string de conexão nunca chega ao navegador) e SHALL ter três páginas: recomendação do trimestre, Selic × crédito e exploração por estado e modalidade. Os indicadores mostrados (variações, correlações, probabilidades) SHALL vir prontos das tabelas publicadas; o site só filtra e, para o saldo do Brasil, soma os 27 estados. O saldo SHALL ser apresentado como **saldo de carteira**, nunca como financiamentos concedidos.

#### Scenario: Página de recomendação

- **WHEN** alguém abre a página inicial
- **THEN** vê a frase de fechamento, as 20 combinações "expandir" e as 20 "alerta" do trimestre, com a data da última publicação
