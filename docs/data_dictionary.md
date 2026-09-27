# Dicionário de Dados

> Preenchido ao longo das Sprints 2 a 4. As tabelas Silver e Gold são obrigatórias
> na entrega (Requisito 4 do enunciado): coluna, tipo, domínio de valores válidos,
> origem e significado de negócio.
>
> Versão consolidada da seção 5 de `architecture.md`.

## Fontes

| Base | URL | Licença | Data de coleta |
|---|---|---|---|
| SCR.data | https://dadosabertos.bcb.gov.br/dataset/scr_data | Open Data Commons ODbL | **2026-09-03** (amostra de 2024) |
| Selic (Ipeadata) | http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='BM366_TJOVER366') | sem termo único publicado — uso educacional com citação da fonte (seção 2.2 do `architecture.md`) | **2026-09-03** |

**Nota de proveniência:** o Ipeadata redistribui a série originalmente produzida pelo
Banco Central. Instituição mantenedora distinta, origem primária a mesma. **Ao citar a
Selic deste projeto, a fonte a creditar é o Ipeadata** (é obrigatório nos termos do Ipea),
**mencionando o Banco Central como produtor original.**

### Formato confirmado na Sprint 1

Aferido em `notebooks/01_exploracao_amostras.ipynb` sobre a amostra de 2024.

| Item | SCR.data | Selic (Ipeadata) |
|---|---|---|
| Formato | ZIP → 1 CSV por mês (`scrdata_AAAAMM.csv`) | JSON OData v4 |
| Encoding | `utf-8-sig` (UTF-8 com BOM) | UTF-8 |
| Separador de campo | `;` | — |
| Separador decimal | `,` (vírgula) | `.` (ponto, no JSON) |
| Aspas | campos entre aspas duplas | — |
| Colunas / campos | 24 colunas | `SERCODIGO`, `VALDATA`, `VALVALOR`, `NIVNOME`, `TERCODIGO` |
| Volume | 3.726.515 linhas em 2024 | 11.044 registros diários (jul/1996 a set/2026) — série da meta do Copom, conferida em 2026-09-27 |

**Unidades e armadilhas numéricas — valem para a tipagem da Silver:**

| Campo de origem | Unidade / formato | Cuidado |
|---|---|---|
| `carteira_ativa` | **reais** (não milhares), decimal com vírgula | Ler com `decimal=","`. Sem isso o pandas devolve string ou número errado em silêncio. Referência: SP somou R$ 977,0 bi em financiamentos em dez/2024 |
| `numero_de_operacoes` | inteiro, mas usa **`-1` como máscara** | `-1` **não é contagem negativa**: é a marca do BCB para valor abaixo do limite de divulgação. Ocorre em 27% das linhas (83.511 de 310.432 em dez/2024) |
| `VALVALOR` | **% ao ano** (Selic meta do Copom, diária) | Até 2026-09-27 o projeto usava a série acumulada no mês (`BM12_TJOVER12`, % ao mês), descartada porque varia com os dias úteis do mês (seção 2.2 do `architecture.md`). A Silver usa a meta do **último dia** de cada mês |

---

## Camada Bronze

### `bronze_scr`
**Uma linha por:** linha do CSV original, como veio da fonte.
**Chave primária:** `(_source_object, _record_hash)`

A Bronze guarda **todas as colunas do CSV, como texto** (`string`), exatamente como vieram —
sem converter número, data ou separador decimal, e sem descartar registro nem período.
Validação, recorte (jul/2016 em diante) e tipagem são feitos na Silver (seções 3.3 e 4.1
do `architecture.md`). Um CSV só é rejeitado se não tiver as 5 colunas usadas (rejeição
estrutural, registrada em log).

**Colunas usadas pelo projeto** (as únicas que viram Silver — `SCR_COLUNAS_USADAS`):

| Coluna | Tipo na Bronze | Como vem da fonte | Significado |
|---|---|---|---|
| `data_base` | string | `AAAA-MM-DD` | data de referência do mês |
| `uf` | string | sigla da UF (pode vir suja — validada na Silver) | unidade da federação |
| `modalidade` | string | texto acentuado | modalidade de crédito |
| `numero_de_operacoes` | string | inteiro em texto; `-1` é máscara do BCB | quantidade de operações. Na Silver, as linhas com `-1` não entram na soma de `qtd_operacoes` (que vira limite inferior) e são contadas em `linhas_qtd_nao_divulgada` |
| `carteira_ativa` | string | decimal com **vírgula** (ex.: `1234,56`), em reais | saldo da carteira ativa. A Silver converte com `decimal=","` |

**Demais colunas** (preservadas na Bronze, não usadas pelo projeto — todas `string`, na
ordem em que vêm no CSV; conferido na execução real de 2026-09-26 sobre o ZIP de 2024):

`segmento`, `cliente`, `cnae_ocupacao`, `porte`, `submodalidade`, `origem`, `indexador`,
`a_vencer_ate_90_dias`, `a_vencer_de_91_ate_360_dias`, `a_vencer_de_361_ate_1080_dias`,
`a_vencer_de_1081_ate_1800_dias`, `a_vencer_de_1801_ate_5400_dias`, `a_vencer_acima_de_5400_dias`,
`carteira_a_vencer`, `vencido_de_15_ate_90_dias`, `vencido_acima_de_90_dias`, `carteira_vencida`,
`carteira_inadimplencia`, `ativo_problematico`.

São 24 colunas de origem no total (5 usadas + 19 acima). **Atenção ao vocabulário:** `segmento`
é o tipo da **instituição financeira**, não o tipo do financiamento — o projeto usa
`modalidade` e não usa `segmento`.

### `bronze_selic`
**Uma linha por:** registro devolvido pela API — um por **dia** (a série inteira, desde jul/1996).
**Chave primária:** `(_source_object, _record_hash)`

Todos os campos devolvidos pela API, **como texto**, sem conversão e sem recorte temporal.
A Bronze só rejeita uma resposta que não é JSON OData legível (registrado em log).

| Coluna | Tipo na Bronze | Como vem da fonte | Significado |
|---|---|---|---|
| `SERCODIGO` | string | `BM366_TJOVER366` | código da série no Ipeadata (Selic meta do Copom) |
| `VALDATA` | string | data ISO com fuso (ex.: `2024-01-01T00:00:00-02:00`) | data de referência. A Silver converte para mês |
| `VALVALOR` | string | número com ponto (ex.: `14.25`) | Selic meta fixada pelo Copom naquele dia, **% ao ano** |
| `NIVNOME` | string | texto (geralmente vazio) | nível geográfico |
| `TERCODIGO` | string | texto (geralmente vazio) | código territorial |

### Como ler a Bronze

As tabelas Bronze são pastas Parquet particionadas por `_ingestion_date`
(`data/raw/bronze_scr/_ingestion_date=AAAA-MM-DD/*.parquet`). Para ler:

```python
pd.read_parquet(config.DIR_BRONZE / "bronze_scr", ignore_prefixes=["."])
```

O `ignore_prefixes=["."]` é **obrigatório**: por padrão o pyarrow ignora pastas cujo
nome começa com `_` ou `.`, e a pasta da partição começa com `_`. Sem o parâmetro, a
leitura devolve uma tabela **vazia, sem erro**. A coluna `_ingestion_date` volta como
categoria (texto `AAAA-MM-DD`).

### Metadados técnicos (presentes nas duas tabelas Bronze)

| Coluna | Tipo | Significado |
|---|---|---|
| `_ingestion_timestamp` | timestamp | momento exato da ingestão |
| `_ingestion_date` | date | data da ingestão, usada para particionar |
| `_source_system` | string | `scr_data` ou `ipeadata` |
| `_source_object` | string | SCR: nome do CSV **+ versão** (data do arquivo dentro do ZIP), ex.: `scrdata_202408.csv@2026-09-15T02:38:32`. Selic: URL do endpoint |
| `_load_id` | string | identificador único da execução |
| `_ingestion_mode` | string | SCR: sempre `full` (carga por arquivo). Selic: `full` na primeira carga, `incremental` nas seguintes |
| `_record_hash` | string | SHA-256 do conteúdo do registro + `_source_object` |

---

## Camada Silver

Reconstruída inteira a partir da Bronze a cada execução (`src/transformation/`). Usa só a
**versão mais recente** de cada CSV do SCR e a **leitura mais recente** de cada mês da Selic,
e só o recorte **jul/2016 a jun/2026**. O que fica fora do escopo é filtrado e contado em
`data/processed/_relatorio_silver.json`; o que é inválido vai para a quarentena.

### `silver_scr` — `data/processed/silver_scr.parquet`
**Uma linha por:** mês × estado × modalidade de financiamento.
**Chave primária:** `(ano_mes, uf, modalidade)`

| Coluna | Tipo | Domínio | Origem | Significado |
|---|---|---|---|---|
| `ano_mes` | date | jul/2016 a jun/2026, primeiro dia do mês | `data_base` | mês de referência |
| `uf` | string(2) | 27 estados | `uf` | estado do tomador (CEP de residência para PF, sede para PJ) |
| `modalidade` | string | 8 modalidades de financiamento | `modalidade` | tipo de financiamento (nome exatamente como na fonte) |
| `qtd_operacoes` | integer | ≥ 0 | `numero_de_operacoes` | soma das quantidades **divulgadas** do grupo — **limite inferior**. Linhas com `-1` (quantidade escondida pelo BCB) não entram na soma, nem como zero |
| `linhas_qtd_nao_divulgada` | integer | ≥ 0 | `numero_de_operacoes` | quantas linhas do grupo tinham `-1`. Se for maior que zero, a quantidade real é maior que `qtd_operacoes` |
| `volume_rs` | decimal | ≥ 0 | `carteira_ativa` | saldo da carteira em R$ nominais (**reais**), soma de todas as linhas do grupo. É **saldo**, não concessão do mês. Completo — é o indicador principal |
| `_load_id` | string | UUID | — | execução da Silver que gerou a linha |

### `silver_selic` — `data/processed/silver_selic.parquet`
**Uma linha por:** mês.
**Chave primária:** `(ano_mes)`

| Coluna | Tipo | Domínio | Origem | Significado |
|---|---|---|---|---|
| `ano_mes` | date | jul/2016 a jun/2026, primeiro dia do mês | `VALDATA` | mês de referência |
| `selic_pct` | decimal | > 0 | `VALVALOR` | **Selic meta do Copom vigente no último dia do mês, % ao ano.** Usa só a série configurada, a leitura mais recente de cada dia e o último dia válido do mês; um mês ainda não fechado nunca entra |
| `_load_id` | string | UUID | — | execução da Silver que gerou a linha |

---

## Camada Gold

### `gold_credito_selic` — `data/final/gold_credito_selic.parquet`
**Uma linha por:** mês × estado × modalidade de financiamento.
**Chave primária:** `(ano_mes, uf, modalidade)`

| Coluna | Tipo | Origem | Significado |
|---|---|---|---|
| `ano_mes` | date | Silver | mês (primeiro dia) |
| `uf` | string(2) | Silver | estado |
| `modalidade` | string | Silver | tipo de financiamento |
| `qtd_operacoes` | integer | Silver | quantidade de operações divulgadas — **limite inferior** (5.1) |
| `linhas_qtd_nao_divulgada` | integer | Silver | linhas do grupo com a quantidade escondida pelo BCB |
| `volume_rs` | decimal | Silver | saldo em R$ — indicador principal |
| `tem_mes_anterior` | boolean | derivada | a combinação tem linha no mês imediatamente anterior? Se não, as variações ficam vazias |
| `var_qtd_pct` | decimal | derivada | variação % da quantidade vs. mês anterior. Vazia sem mês anterior **ou** quando a quantidade anterior é 0 |
| `var_volume_pct` | decimal | derivada | variação % do volume vs. mês anterior. Vazia sem mês anterior |
| `selic_pct` | decimal | Silver | Selic meta do mês (% a.a., último dia do mês) — a mesma para todas as UFs e modalidades do mês |
| `var_selic_pp` | decimal | derivada | **decisão do Copom no mês**: variação da meta vs. mês anterior, em pontos percentuais ao ano (0 se não houve mudança) |
| `selic_lag_1` … `selic_lag_6` | decimal | derivada | Selic meta de 1 a 6 meses antes, **pelo calendário** |

**Regra de cálculo:** variações calculadas separadamente por estado e modalidade, só entre
meses consecutivos (`tem_mes_anterior`); buracos não são preenchidos. A Selic, a variação e
as defasagens vêm da série nacional, pelo calendário. Detalhes na seção 5.3 do `architecture.md`.

### `analise_brasil_modalidade` — `data/final/analise_brasil_modalidade.parquet`
**Uma linha por:** modalidade × defasagem (8 × 7 = 56 linhas).

| Coluna | Tipo | Significado |
|---|---|---|
| `modalidade` | string | tipo de financiamento |
| `defasagem_meses` | integer | k: compara a variação do crédito no mês t com a variação da Selic no mês t − k (0 a 6) |
| `n_meses` | integer | meses com as duas variações disponíveis |
| `spearman` | decimal | correlação de Spearman (−1 a 1). Negativa = quando a Selic sobe, o crédito tende a crescer menos |
| `pearson` | decimal | correlação de Pearson, para comparação |
| `p_valor` | decimal | valor-p do Spearman |
| `p_ajustado` | decimal | valor-p ajustado por Benjamini-Hochberg entre as 56 medidas |
| `significativo` | boolean | `p_ajustado < 0,05` |

### `analise_uf_modalidade` — `data/final/analise_uf_modalidade.parquet`
**Uma linha por:** UF × modalidade.

| Coluna | Tipo | Significado |
|---|---|---|
| `uf`, `modalidade` | string | combinação |
| `defasagem_meses` | integer | k* usado: a defasagem de maior associação da modalidade no nível Brasil |
| `n_meses` | integer | meses válidos (com mês anterior e as duas variações) |
| `amostra_insuficiente` | boolean | `n_meses` abaixo do mínimo (24): correlação não calculada |
| `spearman`, `pearson`, `p_valor` | decimal | vazios se a amostra for insuficiente |
| `p_ajustado`, `significativo` | decimal / boolean | Benjamini-Hochberg entre as combinações calculadas |

### Saídas da decisão (`data/final/`, Sprint 6)

| Arquivo | Conteúdo |
|---|---|
| `recomendacao_trimestre.parquet` | `grupo` (`expandir` / `alerta`), `posicao`, `uf`, `modalidade`, `prob_ganha_forca`, `volume_rs` (saldo em jun/2026): as 20 combinações com maior e as 20 com menor probabilidade de ganhar força em set–nov/2026 |
| `sensibilidade_limiar.parquet` | por regra (`nota mínima` 0,5–0,9; `maiores notas do mês` 10/20/40): recomendações por mês, precisão e recall do modelo, precisão da regra simples — calculado no teste |
| `frase_fechamento.json` | todos os números citados na frase de fechamento (seção 1) e na seção 10 do `architecture.md` |

### `gold_ml_dataset` — `data/final/gold_ml_dataset.parquet`
**Uma linha por:** combinação UF × modalidade (coorte de 174) × mês de **origem** (o mês em que a previsão seria feita).
**Chave primária:** `(uf, modalidade, origem)`

| Coluna | Tipo | Significado |
|---|---|---|
| `uf`, `modalidade` | string | combinação |
| `origem` | date | mês de origem t (jul/2017 em diante — precisa de 12 meses de histórico) |
| `var_1m`, `var_3m`, `var_6m`, `var_12m` | decimal | crescimento % do saldo da combinação nos últimos 1, 3, 6 e 12 meses (até t) |
| `aceleracao_3m` | decimal | `var_3m` em t menos `var_3m` em t−3 (p.p.): ganhou (>0) ou perdeu (<0) força recentemente |
| `rel_3m`, `rel_12m` | decimal | crescimento da combinação menos o da modalidade no Brasil (p.p.) |
| `participacao` | decimal | saldo da combinação ÷ saldo nacional da modalidade, em t |
| `var_participacao_12m` | decimal | variação da participação em 12 meses |
| `selic_pct` | decimal | Selic meta em t (% a.a.) — **variável da Selic** |
| `selic_var_3m`, `selic_var_6m` | decimal | variação da meta nos 3 e 6 meses anteriores (p.p.) — **variáveis da Selic** |
| `volume_origem` | decimal | saldo da combinação em t — só para pesar a AUC; **não** é feature |
| `ganha_forca` | 0/1 | **rótulo**: 1 se o saldo cresce mais de t+2 a t+5 do que cresceu de t−3 a t. Vazio na produção |
| `conjunto` | string | `desenvolvimento` (até ago/2024), `embargo` (set/2024–jan/2025, fora do modelo avaliado), `teste` (fev/2025–jan/2026), `producao` (jun/2026) |

### Saídas do ML (`data/final/`)

| Arquivo | Conteúdo |
|---|---|
| `ml_resultados.json` | janela móvel (AUC por ano de cada candidato, com e sem Selic, e dos baselines), modelo escolhido, métricas do teste final, importância das variáveis, efeito da Selic, alertas |
| `ml_previsoes_teste.parquet` | por linha do teste: `uf, modalidade, origem, ganha_forca, prob_ganha_forca, prob_sem_selic` |
| `ml_previsao_producao.parquet` | por combinação: `uf, modalidade, origem (jun/2026), prob_ganha_forca` para set–nov/2026, ordenado |

---

## Tabelas de controle (`data/raw/_controle/`)

Arquivos JSON pequenos que dizem o que já foi ingerido. São o que torna a ingestão idempotente
(seção 3.2 do `architecture.md`). Fora do Git.

### `controle_scr.json`
Um item por ano do SCR:

| Campo | Significado |
|---|---|
| `etag` | versão do ZIP publicada pelo BCB (cabeçalho `ETag`) na última vez que o ZIP foi baixado |
| `csvs.<nome>.data` | data do arquivo CSV dentro do ZIP (ISO 8601) — é a versão que vai no `_source_object` |
| `csvs.<nome>.crc32` | CRC32 do CSV informado pelo índice do ZIP (hexadecimal) |
| `csvs.<nome>.source_object` | `_source_object` com que essa versão foi gravada na Bronze |
| `csvs.<nome>.status` | `em_andamento` (gravação começou) ou `completo` (todas as linhas gravadas) |

### `controle_selic.json`

| Campo | Significado |
|---|---|
| `watermark` | maior `VALDATA` já gravada na `bronze_selic`, no formato `AAAA-MM-DD` |

---

## Quarentena

Arquivos da Silver em `data/raw/_quarentena/`: `silver_scr.parquet` e `silver_selic.parquet`,
**refeitos a cada execução** (a Silver é reconstruída inteira; reprocessar não duplica
registros rejeitados). Só entra dado inválido — o que está fora do escopo é filtrado e contado
no relatório da Silver.

**Uma linha por:** registro rejeitado.

| Coluna | Tipo | Significado |
|---|---|---|
| `_load_id` | string | execução que rejeitou o registro |
| `_source_system` | string | `scr_data` ou `ipeadata` |
| `_source_object` | string | arquivo ou endpoint de origem |
| `motivo` | string | `uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`, `duplicata_na_chave` |
| `payload` | json | registro original preservado |
| `quarantined_at` | timestamp | momento da rejeição |
