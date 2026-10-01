## Context

As decisões e o porquê estão em `proposal.md`, e os requisitos nas specs `gold-ml-dataset` e `modelo-ml`.

Estado atual:
- **Gold pronta:** `gold_credito_selic` com 24.578 linhas, 120 meses (jul/2016–jun/2026), `volume_rs` completo e Selic meta com `var_selic_pp`. As 174 combinações da coorte têm os 120 meses.
- **`src/ml/` vazio.** O `scikit-learn` 1.9.0 está fixado; o `03_modelo.ipynb` está previsto na seção 9.
- **Números medidos na Gold** (2026-09-27, coorte, rótulo "ganha força" de t+2 a t+5):
  - ~19 mil exemplos;
  - **49,9% "perde força" / 50,1% "ganha força"**;
  - o baseline "volta ao normal" acerta **64,7%**;
  - AUC da Selic sozinha, por variação de 6 meses: **0,51** no total e 0,49–0,54 por modalidade.
  - Na pergunta anterior (relativa ao Brasil), a Selic sozinha dava 0,50.

## Goals / Non-Goals

**Goals:**
- Uma base de ML sem nenhum caminho de vazamento, com testes que provam isso.
- Responder com números: (1) o modelo supera a "volta ao normal"? (2) a Selic ajuda a prever? (3) o resultado se repete em anos diferentes?
- A previsão set–nov/2026 pronta para a Sprint 6.

**Non-Goals:**
- A otimização extensa de hiperparâmetros.
- Regressão.
- A Selic futura como variável.
- O limiar de custo (Sprint 6).
- Salvar o modelo.

## Decisions

### 1. Origem, folga e rótulo

Cada linha é "o que se sabia no fim do mês t". O rótulo compara o crescimento do trimestre utilizável com o crescimento recente:

```python
passado = volume[t]   / volume[t-3] - 1      # últimos 3 meses (conhecido em t)
futuro  = volume[t+5] / volume[t+2] - 1      # trimestre que o decisor ainda pode usar
ganha_forca = int(futuro > passado)
```

**A folga de 2 meses** (`FOLGA_PUBLICACAO_MESES = 2`): o mês t só é publicado ~60 dias depois. Sem a folga, o rótulo mediria meses que já passaram quando o decisor recebe o dado, e o modelo pareceria melhor do que é na prática.

### 2. Features (todas com meses ≤ t)

| Feature | Cálculo | Ideia |
|---|---|---|
| `var_1m`, `var_3m`, `var_6m`, `var_12m` | `volume[t]/volume[t−k] − 1` (%) | momento do crédito |
| `aceleracao_3m` | `var_3m[t] − var_3m[t−3]` (p.p.) | ganhou ou perdeu força recentemente (base da volta ao normal) |
| `rel_3m`, `rel_12m` | `var_k(combinação) − var_k(nacional da modalidade)` | ganhando ou perdendo espaço no país |
| `participacao`, `var_participacao_12m` | `volume/nacional_mod` e a sua diferença em 12 meses | tamanho relativo |
| **`selic_pct`, `selic_var_3m`, `selic_var_6m`** | meta em t; `selic[t] − selic[t−k]` | **variáveis da Selic** (as que entram ou saem na comparação) |
| `uf`, `modalidade` | one-hot | diferenças estruturais |

Tudo numa tabela larga por combinação (meses nas linhas), com `shift` **para trás**. O `shift` para frente aparece **só** no rótulo. O teste anti-vazamento altera meses posteriores a uma origem e confere features idênticas. A quantidade de operações fica de fora (limite inferior, 5.1).

### 3. Conjuntos (datas no `config.py`)

| Conjunto | Origens | Linhas (aprox.) | Rótulo usa até |
|---|---|---|---|
| desenvolvimento | jul/2017 – ago/2024 (`FIM_TREINO_FINAL`) | 86 × 174 ≈ 15.000 | jan/2025 |
| embargo | set/2024 – jan/2025 | 5 × 174 (fora do modelo avaliado) | jun/2025 |
| teste | fev/2025 (`INICIO_TESTE`) – jan/2026 | 12 × 174 = 2.088 | jun/2026 = t0 |
| produção | jun/2026 = t0 | 174 (sem rótulo) | nov/2026 |

As origens de fev a mai/2026 ficam fora, porque o rótulo delas passaria do t0.

### 4. Janela móvel por ano (escolha e estabilidade)

Para cada bloco `B` em `BLOCOS_JANELA_MOVEL = [2020, 2021, 2022, 2023]`:
- **treino:** origens de `desenvolvimento` ≤ **jul/(B−1)**, porque o rótulo da última origem de treino termina em dez/(B−1), antes do bloco;
- **avaliação:** as origens de jan a dez/B.

O bloco de 2023 termina em origens de dez/2023, com rótulo até mai/2024, antes do teste final. **Nenhum bloco toca o período de teste.** Os blocos cobrem anos de juros em queda (2020), mínima (2021) e alta (2022–23).

Candidatos, cada um **com** e **sem** Selic:
1. regressão logística (`C=1.0`, `max_iter=1000`);
2. `HistGradientBoostingClassifier` (`max_iter=200`, `learning_rate=0.05`, `random_state=SEMENTE`).

**Escolha:** maior AUC média nos 4 blocos, entre as versões **com** Selic (a pergunta de pesquisa). Se a diferença para a logística for menor que 0,01, vence a logística. A versão "sem Selic" do escolhido é a comparação obrigatória.

*Por que blocos anuais e não `KFold`/`TimeSeriesSplit`:* o `KFold` embaralha meses e vaza o futuro, e o `TimeSeriesSplit` não conhece o horizonte de 5 meses. Os blocos são montados à mão, com o intervalo certo.

### 5. Teste final (uma vez)

O escolhido (com e sem Selic) é treinado com todas as origens de `desenvolvimento` e avaliado no `teste`. Os baselines também são avaliados no `teste`. A diferença "com − sem Selic" em AUC aparece no teste **e** em cada bloco: se ela for consistentemente próxima de 0, a conclusão é "a Selic não agrega à previsão do próximo trimestre".

### 6. Métricas

- **AUC:** a principal. Mede se o modelo ordena bem quem vai ganhar força, independentemente do limiar, e é o que a Sprint 6 usa para escolher o limiar pelo custo.
- **Precisão nas melhores apostas** (`TOP_APOSTAS = 20`): por mês de origem, das 20 combinações com maior probabilidade, a fração que de fato ganhou força, com a média entre os meses. É como o decisor usa: escolhe onde expandir.
- **AUC pesada pelo volume:** `roc_auc_score(..., sample_weight=volume_rs na origem)`. O erro em combinações grandes custa mais.
- **Precisão e recall da classe positiva, F1 e acurácia** no limiar 0,5, no total e por modalidade.
- **Alerta:** qualquer métrica do modelo acima de 0,95 é registrada como "possível vazamento — investigar".

### 7. Por que os números parecem mais firmes do que são

- **Rótulos sobrepostos:** as origens t e t+1 compartilham 2 dos 3 meses do trimestre futuro. As linhas não são independentes.
- **Choques comuns:** as 174 combinações do mesmo mês sofrem os mesmos choques.

Por isso **não** se calcula intervalo de confiança "ingênuo" sobre as ~2 mil linhas do teste. A incerteza é mostrada pela **variação entre os 4 blocos anuais**, e o notebook explica isso em texto simples.

### 8. Explicação

Importância por permutação (`permutation_importance`, `scoring="roc_auc"`, `n_repeats=10`, `random_state=SEMENTE`) no teste, agrupada por variável original. Para a logística, os coeficientes padronizados.

### 9. Produção

O escolhido (com Selic) é treinado com todas as linhas rotuladas (desenvolvimento + embargo + teste) e prevê as 174 linhas de produção. A saída é `ml_previsao_producao.parquet` com `uf, modalidade, prob_ganha_forca`, ordenada.

### 10. Código

- `src/ml/dataset.py`: `construir_gold_ml_dataset()`.
- `src/ml/treino.py`: `baselines()`, `montar_pipeline(modelo, com_selic)`, `janela_movel()`, `teste_final()`, `metricas()`, `prever_producao()` e `executar_ml()`.
- `notebooks/03_modelo.ipynb`: só lê e explica, e contém o checklist 6.3.
- `scripts/run_pipeline.py`: etapa "Sprint 5: ML".

## Risks / Trade-offs

- [O modelo não supera a volta ao normal] → é um resultado legítimo e vai relatado. A Sprint 6 decide o que recomendar ao decisor, podendo usar a própria regra simples se ela for a melhor.
- [A Selic não agrega] → provável, pelos números medidos. Vira uma conclusão da pesquisa, coerente com a Sprint 4: associação contemporânea sem poder de antecipação no curto prazo.
- [Mudança de regime] → os blocos cobrem 2020–2023, e o teste cai no regime de 2025–26.
- [Poucas origens no teste (12)] → os 4 blocos anuais dão a leitura de estabilidade.
- [Métrica alta demais] → alerta automático.

## Migration Plan

Não há base de ML anterior.
1. Preencher a 6.1 no `architecture.md` (a regra da seção 8).
2. Implementar com testes sintéticos, incluindo o teste do futuro alterado e um sinal plantado.
3. Rodar sobre a Gold real.
4. Rodar de novo e conferir resultado idêntico.
5. Responder o checklist 6.3.

Rollback: reverter o PR.
