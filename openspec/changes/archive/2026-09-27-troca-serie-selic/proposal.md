## Why

A primeira execução da análise (change `camada-gold-analise`, pausada em 12/16) mostrou que a série da Selic escolhida na Sprint 1, a `BM12_TJOVER12` (Selic **acumulada no mês, % a.m.**), **não mede a política de juros mês a mês**. Ela mede, em boa parte, o calendário:

- A Selic acumulada no mês soma os juros de cada dia útil. Com a taxa parada, um mês de 22 dias úteis "rende" mais que um de 20.
- Nos 120 meses do recorte, a variação mensal dessa série tem **correlação de Spearman de 0,79 com a variação do número de dias úteis**.
- **Exemplo real:** em mar/2026 a série **subiu** de 1,00% para 1,21% a.m., enquanto o **Copom cortou** a meta de 15,00% para 14,75% a.a. A série indicou o sentido **oposto** ao da decisão, só porque março teve 22 dias úteis e fevereiro, 20.

Com essa série, `var_selic_pp` compara o crédito com o calendário, e o resultado da análise ("nenhuma associação significativa") não responde à pergunta do trabalho. A pergunta fala em "ciclos de alta e baixa da taxa Selic", e isso é a **meta fixada pelo Copom**.

**Decisão do grupo (2026-09-27):** trocar a fonte Y para a **Selic meta do Copom**, `BM366_TJOVER366` no Ipeadata. É diária, em % a.a., com 11.044 registros de jul/1996 a set/2026. O corte mensal pega a meta vigente no último dia de cada mês. A decisão fica registrada no `architecture.md` e numa nova seção "Registro de decisões", que reúne todas as decisões do grupo até agora.

## What Changes

- **BREAKING — fonte Y:** `SELIC_SERIE` passa de `BM12_TJOVER12` para `BM366_TJOVER366` no `config.py`, com uma constante nova `SELIC_UNIDADE = "% ao ano"`. O loader da Selic não muda de código. A série diária entra na Bronze como veio, e o watermark passa a ser um dia (a lógica já compara `AAAA-MM-DD`).
- **`silver_selic` — corte mensal:**
  - usa só as linhas da série atual na Bronze (`_source_object` igual à URL configurada), ignorando e contando as de outra série;
  - para cada dia, fica a leitura mais recente;
  - valida;
  - para cada mês, fica a **meta vigente no último dia com valor válido do mês**;
  - `selic_pct` passa a ser **% a.a.**
- **Consequência na Gold, sem mudar o código:** `var_selic_pp` passa a ser **a decisão do Copom acumulada no mês, em pontos percentuais ao ano** (por exemplo, −0,25), e é 0 nos meses sem mudança. `selic_lag_k` passa a ser a meta de k meses antes. A Gold e a análise são refeitas.
- **Diagnóstico da Sprint 1** (`scripts/baixar_amostras.py`): a frase fixa "em % AO MÊS" passa a usar `config.SELIC_UNIDADE`, para não mentir sobre a unidade.
- **Documentação:**
  - `architecture.md` seção 2.2: a nova série, a justificativa, a evidência e a série antiga registrada como descartada, com o motivo;
  - `architecture.md` seções 5.2 e 5.3: a unidade e o significado de `var_selic_pp`;
  - **nova seção 13, "Registro de decisões"**: uma tabela com todas as decisões do grupo, com data, onde está detalhada e o motivo;
  - `data_dictionary.md`, `CLAUDE.md` (regra "Unidade da Selic") e `README.md` (tabela de fontes).
- **Migração local:** a `bronze_selic` e o `controle_selic.json` atuais são da série antiga. O watermark 2026-09-01 faria a série nova começar só em setembro/2026. Os dois são apagados e a Selic é reingerida (segundos). O SCR não é tocado.

## Capabilities

### New Capabilities

*(Nenhuma.)*

### Modified Capabilities
- `ingestao-selic`: a série requisitada passa a ser a definida em `SELIC_SERIE` (hoje a meta do Copom, diária, % a.a.), não mais `BM12_TJOVER12` fixa na spec.
- `silver-selic`: a leitura vigente passa a ser por **dia**, com corte mensal pelo último dia válido do mês; a unidade passa a % a.a.; entra o filtro pela série configurada.
- `diagnostico-fontes`: a unidade declarada na saída passa a vir da configuração.

## Impact

- **Código:** `src/config.py` (`SELIC_SERIE`, `SELIC_UNIDADE`), `src/transformation/silver_selic.py` (corte mensal e filtro de série), `scripts/baixar_amostras.py` (uma linha). `selic_api_loader.py`, `gold_credito_selic.py` e `correlacao.py` **não mudam**.
- **Testes:** `tests/test_transformation.py`, testes da Selic: série diária simulada, corte pelo último dia e filtro de série. Os demais seguem.
- **Documentação:** `docs/architecture.md` (2.2, 5.2, 5.3, nova seção 13), `docs/data_dictionary.md`, `CLAUDE.md`, `README.md`.
- **Dados:** `bronze_selic` passa de 633 para ~11 mil linhas (poucos KB em Parquet). A `silver_selic` continua com 120 linhas.
- **Ordem:** esta change é aplicada e mesclada **antes** de concluir a `camada-gold-analise`. Depois, as tarefas 5.3 a 6.3 daquela change rodam com a série nova.
