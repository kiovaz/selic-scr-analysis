## Why

A Silver está pronta (PR #12): `silver_scr` com 24.578 linhas e `silver_selic` com 120 meses, os dois no recorte jul/2016 a jun/2026. Falta a parte que responde à pergunta do trabalho: cruzar crédito e Selic, calcular as variações e medir a associação entre elas. É a segunda metade da Sprint 4, e a definição de pronto da sprint (seção 8) só é cumprida com ela: "o `assert` de duplicata passa nas três tabelas e existe um primeiro gráfico da relação Selic × variação do crédito".

**Decisões do grupo (2026-09-27):**
1. **Meses faltando:** 42 combinações UF × modalidade têm buracos no meio da série (15% das linhas, 0,005% do volume). A Gold **mantém tudo**, calcula a variação **só quando o mês anterior existe** e deixa a célula vazia quando ele não existe. Uma coluna `tem_mes_anterior` mostra isso linha a linha.
2. **Análise em dois níveis:** (a) **Brasil por modalidade**, somando as 27 UFs, com a Selic do mesmo mês e de 1 a 6 meses antes; (b) **UF × modalidade**, num mapa de calor que mostra onde o crédito reage mais à Selic.

**Achado que entra como regra:** em 7.945 grupos (32%) toda a quantidade estava escondida, e a `qtd_operacoes` é 0. A variação % da quantidade não existe a partir de zero, então `var_qtd_pct` fica vazia nesses casos. Isso reforça o **volume** como indicador principal (decisão já registrada na seção 5.1).

A publicação da Gold na nuvem (Neon + Next.js na Vercel) foi aprovada pelo tech lead, mas fica para uma sprint futura, numa change própria.

## What Changes

- **`gold_credito_selic`** (`src/transformation/gold_credito_selic.py` → `data/final/gold_credito_selic.parquet`), uma linha por `(ano_mes, uf, modalidade)`:
  - junta a `silver_scr` e a `silver_selic` por `ano_mes`;
  - conta os **órfãos dos dois lados**: meses do SCR sem Selic e meses da Selic sem SCR;
  - colunas da seção 5.3, mais `linhas_qtd_nao_divulgada` (vinda da Silver) e `tem_mes_anterior`;
  - `var_volume_pct` e `var_qtd_pct` calculadas por UF × modalidade, só entre meses consecutivos; `var_qtd_pct` fica vazia quando a quantidade anterior é 0;
  - `var_selic_pp` = diferença da Selic para o mês anterior, em pontos percentuais;
  - `selic_lag_1` a `selic_lag_6` = Selic de 1 a 6 meses antes **pelo calendário** (a Selic é nacional e não tem buracos). Nos primeiros meses do recorte ficam vazias e não são preenchidas.
- **Análise estatística da seção 5.4** (`src/analise/`, com resultados em `data/final/`):
  - **Brasil por modalidade:** para cada modalidade e cada defasagem k de 0 a 6 meses, correlação entre `var_volume_pct(t)` e `var_selic_pp(t − k)`, com o tamanho da amostra e o valor-p;
  - **UF × modalidade:** a mesma medida por combinação, na defasagem de maior associação da modalidade no nível Brasil, exigindo um mínimo de meses válidos;
  - valor-p **ajustado para muitos testes** (Benjamini-Hochberg), porque são centenas de correlações ao mesmo tempo;
  - relatado como **associação**, nunca como causa.
- **Gráficos:** o primeiro gráfico (correlação por modalidade e defasagem) e o mapa de calor UF × modalidade, salvos em `docs/figuras/` e mostrados no `notebooks/02_analise_estatistica.ipynb`, com as saídas gravadas.
- **Relatório da Gold** (`data/final/_relatorio_gold.json`): linhas, órfãos dos dois lados e quantas linhas não têm mês anterior.
- **`scipy`** fixado no `requirements.txt`, para as correlações e os valores-p. Já está instalado como dependência do `scikit-learn`, só não estava declarado.
- **Etapa Gold e análise** no `scripts/run_pipeline.py`.
- **Testes:** as regras da Gold e da análise, e a prova de chave sem duplicata das **três** tabelas (definição de pronto).

## Capabilities

### New Capabilities
- `gold-credito-selic`: construção da `gold_credito_selic` (join, órfãos, variações só entre meses consecutivos, lags da Selic pelo calendário, relatório).
- `analise-estatistica`: correlações entre variação do crédito e variação da Selic nos dois níveis, com defasagens, amostra mínima, valor-p ajustado e gráficos.

### Modified Capabilities
*(Nenhuma — a Silver e a Bronze não mudam de requisitos.)*

## Impact

- **Código novo:** `src/transformation/gold_credito_selic.py`, `src/analise/__init__.py` e `src/analise/correlacao.py`. O pacote `src/analise/` é novo e entra na seção 9 do `architecture.md`. Também `notebooks/02_analise_estatistica.ipynb` e uma etapa no `run_pipeline.py`.
- **Configuração:** `src/config.py` ganha os caminhos das saídas da Gold e da análise, a defasagem máxima (6) e a amostra mínima por combinação.
- **Dependências:** `scipy` fixado no `requirements.txt`.
- **Testes:** `tests/test_gold.py`, `tests/test_analise.py` e o acréscimo em `tests/test_no_duplicates.py`.
- **Documentação:** `docs/architecture.md` (5.3, 5.4 e 9) e `docs/data_dictionary.md` (Gold e tabelas da análise).
- **Dados:** `data/final/`, com alguns MB e fora do Git. As figuras em `docs/figuras/` **vão para o Git**, porque são produto da entrega e pequenas (PNG).
