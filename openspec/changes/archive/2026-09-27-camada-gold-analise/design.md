## Context

A motivação e as decisões do grupo estão em `proposal.md`, e os requisitos nas specs `gold-credito-selic` e `analise-estatistica`.

Estado atual:
- **Silver pronta:**
  - `silver_scr.parquet` tem 24.578 linhas, chave `(ano_mes, uf, modalidade)`, `ano_mes` no primeiro dia do mês (tipo `date`) e colunas `qtd_operacoes`, `linhas_qtd_nao_divulgada` e `volume_rs` (float);
  - `silver_selic.parquet` tem 120 linhas.
- **Perfil da Silver** (2026-09-27):
  - 42 combinações UF × modalidade têm buracos no meio da série, somando 3.698 linhas;
  - 7.945 linhas têm `qtd_operacoes = 0`;
  - nenhuma linha tem volume 0.
- **Ferramentas:** `scipy` 1.18.1 está instalado (vem com o `scikit-learn`) e tem `spearmanr`, `pearsonr` e `false_discovery_control` (Benjamini-Hochberg). `matplotlib` e `seaborn` já estão fixados no `requirements.txt`.
- **Estrutura:** a seção 9 prevê `src/transformation/gold_credito_selic.py` e `notebooks/02_analise_estatistica.ipynb`, mas não um lugar para o código da análise.

## Goals / Non-Goals

**Goals:**
- A Gold com as colunas da seção 5.3 e sem nenhuma limpeza (4.1), porque se precisasse limpar, a Silver teria falhado.
- Uma análise que respeite a seção 5.4 (variações, defasagens, por modalidade, associação) e que qualquer integrante consiga explicar.
- Os dois gráficos da entrega, reproduzíveis pelo pipeline.

**Non-Goals:**
- A base de ML (`gold_ml_dataset`, Sprint 5).
- A publicação na nuvem (Neon + Next.js), numa change futura.
- Modelos de regressão, controles regionais e deflação pela inflação (limitações 3 e 5 da seção 11).

## Decisions

### 1. `tem_mes_anterior` e as variações pelo calendário, não pela linha anterior

```python
gold = gold.sort_values(["uf", "modalidade", "ano_mes"])
anterior = gold.groupby(["uf", "modalidade"]).shift(1)          # linha anterior da MESMA combinação
mes_esperado = gold["ano_mes"] - pd.DateOffset(months=1)
gold["tem_mes_anterior"] = anterior["ano_mes"] == mes_esperado  # a linha anterior é mesmo o mês anterior?
gold["var_volume_pct"] = ((gold["volume_rs"] / anterior["volume_rs"] - 1) * 100).where(gold["tem_mes_anterior"])
gold["var_qtd_pct"] = ((gold["qtd_operacoes"] / anterior["qtd_operacoes"] - 1) * 100) \
                          .where(gold["tem_mes_anterior"] & (anterior["qtd_operacoes"] > 0))
```

Usar só `shift(1)` compararia fev/2017 com out/2016 nas combinações com buraco. A comparação da data com o "mês esperado" evita isso, e o `groupby` garante que combinações diferentes nunca se misturam (seção 5.3).

### 2. Selic, variação e defasagens pela série nacional, antes do join

A variação e as defasagens da Selic são calculadas **uma vez**, na série da `silver_selic` indexada pelo mês, e depois entram na Gold pelo join:

```python
selic = silver_selic.set_index("ano_mes").asfreq("MS")          # série mensal contínua
selic["var_selic_pp"] = selic["selic_pct"].diff()
for k in range(1, DEFASAGEM_MAXIMA + 1):
    selic[f"selic_lag_{k}"] = selic["selic_pct"].shift(k)
```

Como a Selic é nacional e não tem buracos, o `shift` na série contínua é exatamente o deslocamento no calendário, e uma combinação com buraco ainda recebe a defasagem certa. Os primeiros meses (jul–dez/2016) ficam vazios, como prevê a seção 5.3.

*Alternativa considerada:* estender a `silver_selic` para jan/2016, para ter as defasagens dos primeiros meses. Descartada: a seção 5.3 já aceita esses vazios, e mudar o recorte da Silver exigiria outra decisão do grupo. Fica registrada como possibilidade.

### 3. Join e órfãos

`silver_scr` e `silver_selic` são juntadas por `ano_mes` com `how="outer", indicator=True`, só para **contar** os dois lados:
- `left_only` são os meses do SCR sem Selic;
- `right_only` são os meses da Selic sem SCR.

A Gold fica com o `both`. Com o recorte fixo, espera-se zero órfãos, e qualquer órfão aparece no relatório como algo a investigar (seção 2.4).

### 4. Correlação de Spearman

**Spearman** (correlação de postos) é a medida principal, com Pearson registrado ao lado para comparação.

*Por que Spearman:* as variações % têm valores extremos. Um exemplo é o AP × títulos, que passou de R$ 9 mil para R$ 20 mil (+120%). Pearson é muito sensível a esses casos: um único mês extremo pode criar ou apagar uma correlação. Spearman compara a **ordem** dos valores ("quando a Selic sobe mais, o crédito cai mais?"), é mais robusto e é igualmente fácil de explicar.

### 5. Nível Brasil: soma das UFs, depois a variação

Para cada modalidade:
1. soma `volume_rs` das UFs em cada mês. Uma UF ausente no mês soma zero, porque não havia operação (limitação 10);
2. calcula `var_volume_pct` nacional mês a mês (as 8 modalidades têm os 120 meses no nível nacional, e isso é conferido em teste);
3. para cada k de 0 a 6, calcula `spearmanr(var_volume(t), var_selic_pp(t − k))` nos meses em que os dois existem.

O resultado são 56 linhas (8 × 7), com as colunas `modalidade, defasagem_meses, n_meses, spearman, p_valor, p_ajustado, significativo, pearson`.

Somar antes de calcular a variação é deliberado: a média das variações das UFs daria o mesmo peso ao AP e a SP. A soma dá o comportamento do crédito nacional daquela modalidade.

### 6. Nível UF × modalidade: a defasagem do nível Brasil e uma amostra mínima

Testar as 7 defasagens em cada uma das 216 combinações e escolher a "melhor" de cada uma seria **escolher o resultado a dedo**: com 1.512 testes, dezenas sairiam significativos por acaso. Por isso cada combinação é medida numa só defasagem, k*, a de maior |Spearman| **da modalidade no nível Brasil**. A escolha é feita num nível que não depende da combinação.

**Amostra mínima:** `MESES_MINIMOS_CORRELACAO = 24` meses válidos (2 anos). Abaixo disso, a correlação é instável e fica vazia, marcada como `amostra_insuficiente`. O valor fica no `config.py`, então é fácil de ajustar e de justificar.

### 7. Ajuste para muitos testes

`scipy.stats.false_discovery_control(p, method="bh")` é aplicado separadamente em cada nível (56 testes no Brasil, até 216 no UF × modalidade). A coluna `significativo` usa `p_ajustado < 0,05`.

*Alternativa descartada:* Bonferroni. É conservador demais com 216 testes e esconderia associações reais. O Benjamini-Hochberg controla a proporção de falsos positivos e é o padrão quando há muitos testes exploratórios.

### 8. Onde o código mora

- `src/transformation/gold_credito_selic.py`: só a construção da Gold (camada).
- `src/analise/correlacao.py` (pacote novo): as funções dos dois níveis e dos gráficos. Não é transformação de camada, é análise, e separar ajuda cada integrante a achar e explicar a sua parte. A seção 9 do `architecture.md` ganha a pasta.
- `notebooks/02_analise_estatistica.ipynb`: **lê** os resultados de `data/final/` e as figuras, e explica como ler cada gráfico. Não recalcula nada, então não há duas versões da mesma conta.
- `scripts/run_pipeline.py`: novas etapas "Gold" e "Análise".

### 9. Saídas

| Arquivo | Conteúdo |
|---|---|
| `data/final/gold_credito_selic.parquet` | a Gold (~24,6 mil linhas) |
| `data/final/analise_brasil_modalidade.parquet` | 56 linhas (modalidade × defasagem) |
| `data/final/analise_uf_modalidade.parquet` | até 216 linhas (UF × modalidade, na defasagem k*) |
| `data/final/_relatorio_gold.json` | linhas, órfãos e linhas sem mês anterior |
| `docs/figuras/correlacao_por_modalidade.png` | primeiro gráfico: uma linha por modalidade, eixo x = defasagem, eixo y = Spearman, com marcador nos pontos significativos |
| `docs/figuras/mapa_calor_uf_modalidade.png` | UFs × modalidades, cor = Spearman (escala divergente centrada em 0), células com amostra insuficiente em cinza hachurado |

Os gráficos seguem o skill `dataviz` do ambiente, carregado na implementação antes de escrever o código dos gráficos: paleta acessível e escala divergente para correlação. As figuras vão para o Git em `docs/figuras/`, porque são entregáveis pequenos.

## Risks / Trade-offs

- [Correlação espúria por tendência comum] → mitigado por usar só variações (seção 5.4). Mesmo assim, só se afirma associação.
- [Sazonalidade] → o crédito tem padrão sazonal (por exemplo, o rural na safra), e a Selic não. Isso pode diluir a correlação. Fica registrado como limitação da análise, e um ajuste sazonal é uma possível evolução para depois.
- [Poucos pontos por combinação] → mitigado pela amostra mínima e pelo ajuste de Benjamini-Hochberg.
- [Escolha de k* no nível Brasil influencia o mapa de calor] → é deliberada (seção 6 acima). O notebook explica e mostra a tabela completa do nível Brasil.
- [Mês extremo numa combinação pequena] → Spearman reduz o efeito, e o Pearson ao lado mostra quando os dois divergem.

## Migration Plan

Não há Gold anterior (`data/final/` vazio).
1. Implementar com testes sintéticos, incluindo uma relação conhecida (variação do volume = −variação da Selic 2 meses antes) que a análise precisa recuperar.
2. Rodar sobre a Silver real, conferir o relatório (órfãos esperados: 0) e revisar os gráficos.
3. Rodar de novo e conferir que as saídas são idênticas.

Rollback: reverter o PR. A Gold e a análise se reconstroem da Silver.
