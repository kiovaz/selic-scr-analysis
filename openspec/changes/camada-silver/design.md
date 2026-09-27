## Context

A motivação e a decisão do grupo sobre a quantidade estão em `proposal.md`, e os requisitos nas specs `silver-scr`, `silver-selic` e `validacao-bronze`.

Estado atual:
- `src/transformation/` está vazio (só `__init__.py`). A seção 9 prevê `silver_scr.py`, `silver_selic.py` e `gold_credito_selic.py`.
- **Bronze real:**
  - `bronze_scr` tem 34.121.187 linhas em 127 versões (uma por CSV mensal, jan/2016–jul/2026), 24 colunas de texto, em ~175 arquivos Parquet;
  - `bronze_selic` tem 633 leituras;
  - as duas se leem com `ignore_prefixes=["."]`.
- **`src/validation/quality_checks.py`** tem checagens registro a registro e `enviar_para_quarentena`, que grava um arquivo por registro.

**Perfil da Bronze real** (2026-09-27, 92 s; base das decisões abaixo):

| Medida | Valor |
|---|---|
| Linhas de financiamento (8 modalidades) | 12.299.508 de 34,1 milhões |
| UFs fora da lista | 0 (27 distintas) |
| `carteira_ativa` não numérica ou negativa | 0 |
| `numero_de_operacoes` = −1 | 3.457.520 linhas (28,1%), com 10,8% do saldo |
| Grupos mês × UF × modalidade com algum −1 | 26.007 de 26.037 (99,9%); 8.364 só com −1 |
| Combinações UF × modalidade no recorte | 216; 174 com os 120 meses; 42 com meses faltando (mín. 19) |
| Grupos por mês no recorte | de 198 a 212 (máximo teórico 216) |

## Goals / Non-Goals

**Goals:**
- `silver_scr` e `silver_selic` corretas, com chave única e reproduzíveis a partir da Bronze.
- Rodar sobre os 34 milhões de linhas numa máquina comum, com memória limitada e em poucos minutos.
- Cada número descartado explicado no relatório: nada some sem contagem.

**Non-Goals:**
- Gold, join, órfãos, variações, lags e análise (próxima change).
- Preencher meses faltantes, deflacionar valores ou corrigir a quantidade escondida.
- Uma estimativa da quantidade real. O BCB não informa o limite do sigilo, e inventar um número seria "correção silenciosa que ninguém consegue explicar" (seção 4.1).

## Decisions

### 1. Leitura da Bronze por fragmento, com filtro no pyarrow

A leitura é feita arquivo por arquivo (`dataset.get_fragments()`), só com as 6 colunas necessárias (`_source_object` e as 5 usadas). Em cada fragmento:
1. o filtro `modalidade` começa com `Financiamentos` é aplicado **antes** de converter para pandas (`pyarrow.compute.starts_with`), o que corta ~64% das linhas cedo;
2. as linhas passam por versão vigente, recorte, validação e agregação parcial `groupby(ano_mes, uf, modalidade).sum()`.

As agregações parciais (no máximo alguns milhares de linhas por fragmento) são concatenadas e somadas de novo no fim. A memória fica limitada ao tamanho de um fragmento (~200 mil linhas) e não aos 34 milhões.

*Alternativa descartada:* `pd.read_parquet` da Bronze inteira. Seriam vários GB de texto em memória. O perfil acima, feito por fragmento, levou 92 s.

**Versão vigente:** antes do laço, uma leitura só da coluna `_source_object` (distintos) monta `{arquivo: versão mais recente}`. Um fragmento de versão antiga é pulado inteiro e contado no relatório. Como a versão é `nome@AAAA-MM-DDTHH:MM:SS` (com um eventual `#crc…`), a comparação de texto da parte da data dá a ordem certa.

### 2. Escopo: filtrar e contar, não pôr em quarentena

Modalidade fora do escopo, mês fora do recorte e versão antiga **não são dados inválidos**: são dados que o projeto decidiu não usar. Ir para a quarentena lotaria a tabela com milhões de linhas corretas (só a modalidade daria 21,8 milhões) e esconderia os problemas reais. Por isso essas linhas são filtradas, e o relatório registra quantas saíram por cada motivo.

*Consequência no dicionário:* a frase "o mês corrente incompleto da Selic vai para a quarentena" é corrigida. Com o recorte fixo em jun/2026, esse mês simplesmente fica fora do recorte. A proteção "nunca incluir um mês não fechado" continua valendo como regra independente.

### 3. `ano_mes` é o primeiro dia do mês

O SCR usa o último dia (`2024-08-31`) e a Selic o primeiro (`2024-08-01T00:00:00-03:00`). As duas Silvers normalizam para o **primeiro dia** (`2024-08-01`), tipo data. Assim o join da Gold por `ano_mes` é direto, sem conversão. Para o SCR: `pd.to_datetime(data_base).dt.to_period("M").dt.to_timestamp()`. Para a Selic, os 10 primeiros caracteres de `VALDATA`, e daí o mês.

### 4. Quantidade: limite inferior e coluna de transparência

```python
qtd = pd.to_numeric(bloco["numero_de_operacoes"])      # texto -> inteiro
divulgada = qtd.where(qtd >= 0, 0)                     # -1 não entra na soma
nao_divulgada = (qtd == -1).astype(int)
agregado = bloco.assign(qtd_operacoes=divulgada, linhas_qtd_nao_divulgada=nao_divulgada, volume_rs=saldo) \
                .groupby(["ano_mes", "uf", "modalidade"])[["qtd_operacoes", "linhas_qtd_nao_divulgada", "volume_rs"]].sum()
```

- `qtd_operacoes` **nunca é nulo**: é a soma do que foi divulgado. O dicionário muda de "`-1` vira nulo" para "limite inferior". Nulo só fazia sentido linha a linha; agregado, apagaria 99,9% dos grupos.
- `linhas_qtd_nao_divulgada` deixa visível, grupo a grupo, o quanto a quantidade está subestimada. A Gold e a análise podem, por exemplo, excluir da análise de quantidade os grupos com muita máscara, ou só reportar.
- **Por que isso importa para a análise (vai para a seção 11):** se a proporção de linhas mascaradas muda de um mês para o outro, `var_qtd_pct` mistura variação real com variação da máscara. Por isso o **volume** é o indicador principal.

### 5. Validação por coluna e ordem dos motivos

As funções novas em `quality_checks.py` devolvem uma máscara booleana por linha:
- `mascara_uf_invalida(serie, config)`;
- `mascara_tipagem_invalida(serie, tipo, decimal=",")`, com `tipo` em `"float"`, `"int"` ou `"data"`;
- `mascara_valor_negativo(serie_numerica, coluna)`, que respeita a exceção do −1;
- `mascara_data_futura(serie_datas)`.

A Silver aplica as máscaras na ordem da spec, e cada linha fica com o **primeiro** motivo:

```python
motivo = pd.Series(None, index=bloco.index, dtype="object")
for nome, mascara in [("uf_invalida", ...), ("tipagem_invalida", ...),
                      ("data_fora_do_intervalo", ...), ("valor_negativo", ...)]:
    motivo = motivo.mask(motivo.isna() & mascara, nome)
```

Um teste de equivalência compara cada máscara com a checagem `checar_*` correspondente, numa lista de casos de borda.

### 6. Quarentena da Silver reconstruída a cada execução

`gravar_quarentena_da_tabela(df_rejeitados, motivos, tabela, load_id, ...)` grava **um** Parquet por tabela, `data/raw/_quarentena/silver_scr.parquet` e `…/silver_selic.parquet`, **substituindo** o anterior (grava em `.tmp` e renomeia). O formato de linha é o mesmo de `enviar_para_quarentena`; o `payload` é o JSON da linha original da Bronze e o `_source_object` é a versão de origem.

*Por quê:* a Silver é refeita inteira a cada execução (4.1). Uma quarentena só acrescentada ganharia as mesmas linhas a cada execução. *Alternativa descartada:* deduplicar a quarentena pelo hash. É mais código para o mesmo resultado.

`enviar_para_quarentena` (um arquivo por registro) continua existindo para uso pontual e para os testes atuais.

### 7. Saídas e relatório

| Arquivo | Conteúdo |
|---|---|
| `data/processed/silver_scr.parquet` | colunas `ano_mes, uf, modalidade, qtd_operacoes, linhas_qtd_nao_divulgada, volume_rs, _load_id` |
| `data/processed/silver_selic.parquet` | colunas `ano_mes, selic_pct, _load_id` |
| `data/processed/_relatorio_silver.json` | contagens por etapa das duas tabelas e as combinações incompletas |

As saídas ficam num Parquet único por tabela: são pequenas, até 25.920 e 120 linhas, e a Gold lê cada uma de uma vez. A gravação é atômica, o mesmo padrão `.tmp` + renomear. O `_load_id` é da execução da Silver e serve à linhagem por execução (seção 12). Os caminhos vão para o `config.py`.

### 8. Silver da Selic

1. Lê a `bronze_selic` inteira (633 linhas).
2. Leitura vigente: para cada `VALDATA[:10]`, fica a de maior `_ingestion_timestamp`. Empate com valores diferentes vai para a quarentena como `duplicata_na_chave`, com o mês fora da Silver.
3. Aplica o recorte.
4. Descarta, e conta, o mês da execução e os posteriores.
5. Valida `VALVALOR` (tipagem e negativo).
6. Converte para número.

## Risks / Trade-offs

- [Proporção de máscara variar no tempo] → `var_qtd_pct` fica enviesada. Mitigação: a coluna `linhas_qtd_nao_divulgada`, o volume como indicador principal e o registro na seção 11. A Gold decide como filtrar.
- [Grupos com meses faltando] → variações calculadas sobre meses não consecutivos seriam erradas. Mitigação: não preencher, listar no relatório e registrar para a Gold, que só pode calcular variação entre meses consecutivos.
- [Diferenças de acento e espaço no nome da modalidade entre anos] → o filtro é por prefixo e o agrupamento usa o nome exato. Mitigação: o relatório lista as modalidades distintas da Silver, e um teste sobre a Silver real confere que são **8**. Se aparecerem mais, a regra de padronização entra antes do merge.
- [Tempo de execução] → estimado em 2 a 4 minutos (o perfil levou 92 s com lógica parecida). Aceitável, porque a Silver só roda depois da ingestão.
- [Data futura como motivo] → na prática não deve ocorrer. É uma proteção barata contra um arquivo corrompido.

## Migration Plan

Não há dados anteriores na Silver (`data/processed/` está vazio).
1. Implementar com testes sintéticos.
2. Rodar a construção sobre a Bronze real e conferir o relatório. Espera-se: 120 meses; de 198 a 212 grupos por mês; 8 modalidades; soma de `volume_rs` igual à soma do saldo de financiamento no recorte, lida da Bronze por outro caminho; quarentena provavelmente vazia.
3. Rodar de novo e confirmar que as saídas saem idênticas.

Rollback: reverter o PR. A Silver é descartável e se reconstrói da Bronze.
