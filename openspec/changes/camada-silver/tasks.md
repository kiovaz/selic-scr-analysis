## 1. Especificação primeiro

- [x] 1.1 Atualizar `docs/architecture.md`: na seção 5.1, `qtd_operacoes` passa a ser "soma das quantidades divulgadas — limite inferior" e entra a coluna `linhas_qtd_nao_divulgada`, com a decisão do grupo e a data (2026-09-27) e os números do perfil (28,1% das linhas, 99,9% dos grupos, 10,8% do saldo); `ano_mes` = primeiro dia do mês nas duas tabelas (5.1 e 5.2); na seção 3.3, registrar que a quarentena da Silver é refeita a cada execução e que o que está fora do escopo (modalidade, recorte, versão antiga) é filtrado e contado, não posto em quarentena; na seção 11, acrescentar as limitações "quantidade de operações subestimada, com proporção de máscara que pode variar no tempo" e "42 de 216 combinações UF × modalidade não têm todos os meses". Verificar: `grep -n "limite inferior\|linhas_qtd_nao_divulgada" docs/architecture.md` mostra as seções 5.1 e 11.
- [x] 1.2 Atualizar `docs/data_dictionary.md` (seções `silver_scr`, `silver_selic` e `Quarentena`) com as mesmas regras: colunas, tipos, `ano_mes` como primeiro dia, quantidade como limite inferior, e a correção da frase sobre o mês corrente da Selic (fora do recorte, não quarentena). Verificar: o dicionário não diz mais "`-1` vira nulo" na Silver.

## 2. Configuração e validação por coluna

- [x] 2.1 Acrescentar a `src/config.py`: `SCR_DECIMAL = ","`, `ARQUIVO_SILVER_SCR`, `ARQUIVO_SILVER_SELIC` e `ARQUIVO_RELATORIO_SILVER` (em `DIR_SILVER`), com comentários; atualizar `tests/conftest.py` para isolar os novos caminhos. Verificar: `pytest tests/test_config.py`.
- [x] 2.2 Criar em `src/validation/quality_checks.py` as funções `mascara_uf_invalida`, `mascara_tipagem_invalida(serie, tipo, decimal)`, `mascara_valor_negativo(serie_numerica, coluna)` e `mascara_data_futura`, com docstrings em pt-BR. Verificar: um teste de equivalência em `tests/test_validation.py` compara cada máscara com a `checar_*` correspondente numa lista de casos de borda (vazio, `abc`, `-5`, `-1` em `numero_de_operacoes`, `sp`, `XX`, `SP`, `1234,56`, data futura).
- [x] 2.3 Criar `gravar_quarentena_da_tabela(rejeitados, motivos, tabela, load_id, source_system, dir_quarentena)`: um Parquet por tabela, substituindo o anterior de forma atômica, no mesmo formato de linha de `enviar_para_quarentena`, sem nunca levantar exceção. Verificar: um teste grava duas vezes o mesmo lote de 3 rejeitados e confere 3 linhas (não 6); outro, com diretório inválido, confere que só registra em log.

## 3. silver_scr

- [x] 3.1 Criar `src/transformation/silver_scr.py` com a leitura por fragmento (6 colunas, filtro `starts_with` da modalidade no pyarrow antes do pandas) e o mapa de versão vigente por arquivo. Verificar: um teste com duas versões do mesmo CSV na Bronze sintética confere que só a mais recente é usada e que o relatório conta as linhas da antiga.
- [x] 3.2 Aplicar o recorte (`ANO_INICIO/MES_INICIO` a `ANO_FIM/MES_FIM`) e contar no relatório, sem quarentena, as linhas fora do recorte e fora das modalidades. Verificar: um teste com linhas de `Empréstimos`, de jun/2016 e de jul/2026 confere que nenhuma entra na Silver nem na quarentena e que as três contagens aparecem no relatório.
- [x] 3.3 Validar com as máscaras na ordem `uf_invalida` → `tipagem_invalida` → `data_fora_do_intervalo` → `valor_negativo`, mandar os rejeitados para a quarentena da tabela e excluí-los da agregação. Verificar: testes com `XX`, `abc` no saldo e `-5` na quantidade conferem o motivo de cada um; `-1` não é rejeitado.
- [x] 3.4 Tipar e agregar por `(ano_mes, uf, modalidade)`: `ano_mes` no primeiro dia do mês, `volume_rs` = soma do saldo (decimal vírgula), `qtd_operacoes` = soma só das divulgadas, `linhas_qtd_nao_divulgada` = contagem de −1. Verificar: o cenário da spec (`10`, `-1`, `5` / `100,00`, `50,00`, `25,00` → 15, 1, 175.00) e o grupo só com −1 (→ 0, n, soma).
- [x] 3.5 Gravar `silver_scr.parquet` e o relatório (contagens por etapa, combinações incompletas com a quantidade de meses, modalidades distintas) de forma atômica, com `_load_id`. Verificar: rodar duas vezes sobre a mesma Bronze sintética produz Parquet e quarentena idênticos.

## 4. silver_selic

- [x] 4.1 Criar `src/transformation/silver_selic.py`: leitura vigente por mês (maior `_ingestion_timestamp`; empate com valores diferentes → `duplicata_na_chave`), recorte, exclusão do mês da execução e dos posteriores, validação (`tipagem_invalida`, `valor_negativo`), `ano_mes` no primeiro dia e `selic_pct` decimal; gravar a saída, a quarentena da tabela e a parte da Selic no relatório. Verificar: testes cobrem as duas leituras de setembro (fica a mais recente), o empate ambíguo, o nulo em `VALVALOR`, o recorte e o mês corrente.

## 5. Pipeline e testes de chave

- [x] 5.1 Acrescentar a etapa Silver ao `scripts/run_pipeline.py`, depois da ingestão, imprimindo o resumo do relatório (linhas finais, quarentena por motivo, combinações incompletas). Verificar: `python scripts/run_pipeline.py --help` segue funcionando e o resumo aparece na execução real (task 6.1).
- [x] 5.2 Acrescentar a `tests/test_no_duplicates.py` a prova da chave: `silver_scr.duplicated(["ano_mes","uf","modalidade"]).sum() == 0` e `silver_selic.duplicated(["ano_mes"]).sum() == 0`, sobre uma Bronze sintética com versões repetidas e leituras repetidas. Verificar: verde; e, trocando de propósito a versão vigente por "todas as versões", o teste da `silver_scr` **falha**. Desfazer em seguida.
- [x] 5.3 Rodar `pytest -v`. Verificar: todos verdes, sem rede e sem tocar em `data/`.

## 6. Execução real

- [x] 6.1 Rodar a construção da Silver sobre a Bronze real (etapa Silver do `run_pipeline.py`) e anotar nesta task: tempo; linhas finais; meses (esperado 120); grupos por mês (esperado 198–212); modalidades distintas (esperado 8); quarentena por motivo; e as contagens de filtro. Conferir por outro caminho (leitura direta da Bronze vigente no recorte) que a soma de `volume_rs` e a de `qtd_operacoes` batem com a Silver. Se as modalidades distintas não forem 8, parar e registrar a regra de padronização antes de seguir.
  - **Resultado (2026-09-27):** pipeline completo em 154 s (ingestão ~13 s, nada novo; Silver ~140 s). `silver_scr`: **24.578 linhas, 120 meses, 8 modalidades**, quarentena **vazia**, 42 combinações UF × modalidade com meses faltando. Relatório: 34.121.187 lidas − 21.821.679 de outras modalidades − 629.991 fora do recorte = 11.669.517 agregadas; 0 versões antigas (nenhuma republicação na Bronze atual). `silver_selic`: 120 meses (jul/2016 1,11 … jun/2026 1,12), 513 leituras fora do recorte, quarentena vazia.
  - **Conferência por outro caminho:** comparada com a agregação independente do perfil (código diferente, lido direto da Bronze): mesmas 24.578 chaves, volume total R$ 318.747.788.199.816,40 com diferença **zero em todos os grupos**, `qtd_operacoes` total 3.513.233.694 idêntica grupo a grupo, 3.282.731 linhas com `-1` nos dois.
  - Ajuste feito aqui: `converter_numero` passou a devolver `float64` comum (antes saía `Float64` anulável do pandas), para a Gold não lidar com dois tipos de número.
- [x] 6.2 Rodar de novo e confirmar que `silver_scr.parquet`, `silver_selic.parquet` e as quarentenas são idênticos aos da 6.1 (mesmo conteúdo, ignorando `_load_id`). Verificar e anotar.
  - **Resultado:** duas construções seguidas em 288 s no total; `silver_scr` e `silver_selic` idênticas (ignorando `_load_id`), quarentenas com 0 linhas nas duas, e valores iguais aos da execução pelo pipeline.
- [ ] 6.3 `pytest -v`, CI verde no PR para o `develop`, commits atômicos em pt-BR **sem linha de atribuição**.
