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
| Selic (Ipeadata) | http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='BM12_TJOVER12') | sem termo único publicado — uso educacional com citação da fonte (seção 2.2 do `architecture.md`) | **2026-09-03** |

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
| Volume | 3.726.515 linhas em 2024 | 633 registros (jan/1974 a set/2026) |

**Unidades e armadilhas numéricas — valem para a tipagem da Silver:**

| Campo de origem | Unidade / formato | Cuidado |
|---|---|---|
| `carteira_ativa` | **reais** (não milhares), decimal com vírgula | Ler com `decimal=","`. Sem isso o pandas devolve string ou número errado em silêncio. Referência: SP somou R$ 977,0 bi em financiamentos em dez/2024 |
| `numero_de_operacoes` | inteiro, mas usa **`-1` como máscara** | `-1` **não é contagem negativa**: é a marca do BCB para valor abaixo do limite de divulgação. Ocorre em 27% das linhas (83.511 de 310.432 em dez/2024) |
| `VALVALOR` | **% ao mês** | Não é % ao ano. O último registro pode ser do **mês corrente incompleto** (em 2026-09-03 vinha 0,1 contra ~1,1 dos vizinhos) e precisa ser descartado |

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
| `numero_de_operacoes` | string | inteiro em texto; `-1` é máscara do BCB | quantidade de operações. A Silver converte `-1` em nulo |
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
**Uma linha por:** registro devolvido pela API (a série inteira, desde jan/1974).
**Chave primária:** `(_source_object, _record_hash)`

Todos os campos devolvidos pela API, **como texto**, sem conversão e sem recorte temporal.
A Bronze só rejeita uma resposta que não é JSON OData legível (registrado em log).

| Coluna | Tipo na Bronze | Como vem da fonte | Significado |
|---|---|---|---|
| `SERCODIGO` | string | `BM12_TJOVER12` | código da série no Ipeadata |
| `VALDATA` | string | data ISO com fuso (ex.: `2024-01-01T00:00:00-02:00`) | data de referência. A Silver converte para mês |
| `VALVALOR` | string | número com ponto (ex.: `0.97`) | taxa Selic acumulada no mês, **% ao mês** |
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
| `_source_object` | string | nome do arquivo CSV ou URL do endpoint |
| `_load_id` | string | identificador único da execução |
| `_ingestion_mode` | string | `full` ou `incremental` |
| `_record_hash` | string | SHA-256 do conteúdo do registro + `_source_object` |

---

## Camada Silver

### `silver_scr`
**Uma linha por:** mês × estado × modalidade de financiamento.
**Chave primária:** `(ano_mes, uf, modalidade)`

| Coluna | Tipo | Domínio | Origem | Significado |
|---|---|---|---|---|
| `ano_mes` | date | jul/2016 a jun/2026 | `data_base` | mês de referência |
| `uf` | string(2) | 27 estados | `uf` | estado do tomador (CEP de residência para PF, sede para PJ) |
| `modalidade` | string | 8 modalidades de financiamento | `modalidade` | tipo de financiamento |
| `qtd_operacoes` | integer | ≥ 0 **ou nulo** | `numero_de_operacoes` | quantidade de operações. A origem traz `-1` como máscara de valor não divulgado — a Silver converte `-1` em **nulo**, nunca em zero: zero afirmaria que não houve operação, o que não é o que a fonte diz |
| `volume_rs` | decimal | ≥ 0 | `carteira_ativa` | saldo da carteira em R$ nominais (**reais**, confirmado na Sprint 1). É **saldo**, não concessão do mês |

### `silver_selic`
**Uma linha por:** mês.
**Chave primária:** `(ano_mes)`

| Coluna | Tipo | Domínio | Origem | Significado |
|---|---|---|---|---|
| `ano_mes` | date | mensal | `VALDATA` | mês de referência |
| `selic_pct` | decimal | > 0 | `VALVALOR` | Selic acumulada no mês, **% ao mês**. O mês corrente incompleto é descartado **na Silver** (vai para a quarentena) |

---

## Camada Gold

### `gold_credito_selic`
**Uma linha por:** mês × estado × modalidade de financiamento.
**Chave primária:** `(ano_mes, uf, modalidade)`

| Coluna | Tipo | Origem | Significado |
|---|---|---|---|
| `ano_mes` | date | Silver | mês |
| `uf` | string(2) | Silver | estado |
| `modalidade` | string | Silver | tipo de financiamento |
| `qtd_operacoes` | integer | Silver | quantidade de operações |
| `volume_rs` | decimal | Silver | saldo em R$ |
| `var_qtd_pct` | decimal | derivada | variação % da quantidade vs. mês anterior |
| `var_volume_pct` | decimal | derivada | variação % do volume vs. mês anterior |
| `selic_pct` | decimal | Silver | Selic do mês |
| `var_selic_pp` | decimal | derivada | variação da Selic em pontos percentuais |
| `selic_lag_1` … `selic_lag_6` | decimal | derivada | Selic de 1 a 6 meses atrás |

**Regra de cálculo:** variações e lags calculados separadamente por estado e modalidade,
ordenados por mês. Os primeiros meses de cada combinação ficam nulos por definição e não
são preenchidos.

### `gold_ml_dataset`
*(A definir na Sprint 5 — ver seção 6 de `architecture.md`.)*

---

## Quarentena

**Uma linha por:** registro rejeitado.

| Coluna | Tipo | Significado |
|---|---|---|
| `_load_id` | string | execução que rejeitou o registro |
| `_source_system` | string | `scr_data` ou `ipeadata` |
| `_source_object` | string | arquivo ou endpoint de origem |
| `motivo` | string | `uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`, `duplicata_na_chave` |
| `payload` | json | registro original preservado |
| `quarantined_at` | timestamp | momento da rejeição |
