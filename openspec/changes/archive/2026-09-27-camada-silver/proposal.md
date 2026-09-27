## Why

A Bronze está completa e idempotente (Sprints 2 e 3), mas guarda o dado **como veio**: 24 colunas de texto, 13 modalidades, meses fora do recorte e versões antigas de meses republicados. Nada disso responde à pergunta do trabalho. A Silver é a camada que transforma esse material num dado limpo, tipado e com chave declarada (seção 4.1). A Gold e a análise da Sprint 4 dependem dela.

A Sprint 4 foi dividida em duas changes: **esta constrói a Silver**, e a próxima constrói a Gold e a análise. A Silver tem muitas regras e cada uma precisa de teste. A Gold depende do contrato da Silver (nomes, tipos e chave), então fechá-lo antes evita retrabalho. A definição de pronto da Sprint 4 (seção 8) só é cumprida quando as duas estiverem prontas.

**Achado que exigiu decisão do grupo** (perfil da Bronze real, 2026-09-27): 28% das linhas de financiamento trazem `numero_de_operacoes = -1`, a quantidade escondida pelo BCB, e **99,9% dos grupos mês × estado × modalidade têm ao menos uma linha assim**. O saldo dessas linhas é divulgado normalmente e soma 10,8% do total. A regra atual do dicionário ("`-1` vira nulo") zeraria a quantidade de praticamente todo o projeto. **Decisão do grupo:** somar só as quantidades divulgadas, tratar o resultado como **limite inferior** e documentar isso. A análise principal usa o **volume**, que está 100% completo.

## What Changes

- **`silver_scr`** (`src/transformation/silver_scr.py`), uma linha por `(ano_mes, uf, modalidade)`:
  - lê da Bronze só a **versão mais recente** de cada CSV (regra da seção 3.2);
  - fica só com as 5 colunas de `SCR_COLUNAS_USADAS`, as 8 modalidades `Financiamentos%` e o recorte **jul/2016 a jun/2026**;
  - converte os tipos: decimal com vírgula para número e `data_base` para `ano_mes`, o primeiro dia do mês;
  - agrega: `volume_rs` = soma do saldo; `qtd_operacoes` = soma **só das quantidades divulgadas**, um limite inferior; `linhas_qtd_nao_divulgada` = quantas linhas do grupo vieram com `-1`.
- **`silver_selic`** (`src/transformation/silver_selic.py`), uma linha por `ano_mes`: a **leitura mais recente** de cada mês (maior `_ingestion_timestamp`), `selic_pct` numérico e o mesmo recorte. Nunca inclui um mês ainda não fechado.
- **Quarentena na Silver** (seção 3.3): registros inválidos saem com o motivo padronizado (`uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`, `duplicata_na_chave`) e o registro original. **A quarentena da Silver é refeita a cada execução**, como a própria Silver, para reprocessar não duplicar registros rejeitados.
- **O que fica fora do escopo não vai para a quarentena, é filtrado e contado:** modalidades que não são de financiamento, meses fora do recorte e versões antigas. Não são dados inválidos, só estão fora do que o projeto usa.
- **Relatório da Silver** (`data/processed/_relatorio_silver.json`): contagens de cada etapa (lidas, filtradas por motivo, em quarentena por motivo, linhas finais) e as combinações `uf × modalidade` com meses faltando (hoje, 42 de 216). **Meses faltando não são preenchidos**; quem calcular variações precisa saber disso (Gold).
- **Checagens por coluna** em `src/validation/quality_checks.py`, com as mesmas regras das checagens registro a registro. Com 12 milhões de linhas de financiamento, validar linha a linha é inviável.
- **Etapa Silver** no `scripts/run_pipeline.py`.
- **Testes:** `tests/test_transformation.py` cobre as regras acima, e `tests/test_no_duplicates.py` ganha a prova da chave `(ano_mes, uf, modalidade)` e `(ano_mes)`.
- **Documentação:** `architecture.md` (5.1, 5.2, 3.3 e 11) e `data_dictionary.md`, com a decisão sobre a quantidade e a nova coluna.

Fora do escopo: a Gold (`gold_credito_selic`), o join com a contagem de órfãos e a análise estatística ficam para a próxima change da Sprint 4.

## Capabilities

### New Capabilities
- `silver-scr`: construção da `silver_scr` a partir da Bronze (versão vigente, recorte, modalidades, tipagem, agregação com quantidade como limite inferior, quarentena e relatório).
- `silver-selic`: construção da `silver_selic` a partir da Bronze (leitura vigente de cada mês, recorte, tipagem, nunca mês não fechado, quarentena).

### Modified Capabilities
- `validacao-bronze`: ganha as checagens aplicadas a uma coluna inteira. A quarentena da Silver passa a ser **substituída a cada execução**, e não mais só acrescentada, para o reprocessamento não duplicar registros rejeitados.

## Impact

- **Código novo:** `src/transformation/silver_scr.py`, `src/transformation/silver_selic.py`; funções novas em `src/validation/quality_checks.py`; etapa nova em `scripts/run_pipeline.py`. `src/config.py` ganha os caminhos das saídas da Silver.
- **Testes:** `tests/test_transformation.py` (novo) e `tests/test_no_duplicates.py`.
- **Dados:** `data/processed/silver_scr.parquet` (até 25.920 linhas), `data/processed/silver_selic.parquet` (120 linhas), o relatório e a quarentena da Silver. Tudo fora do Git.
- **Documentação:** `docs/architecture.md` (5.1, 5.2, 3.3, 11), `docs/data_dictionary.md`.
- **Dependências:** nenhuma nova.
