## 1. Especificação primeiro

- [x] 1.1 Atualizar `docs/architecture.md`: na seção 3, trocar "busca só o que falta" por "baixa a série inteira e grava só o que falta — a API do Ipeadata ignora `$filter`/`$top`/`$orderby` (conferido em 2026-09-27)" e acrescentar a linha "Controle de versão | SCR.data | `ETag` do ZIP via `HEAD` + CRC32/data de cada CSV"; na seção 3.2, registrar o `_source_object` com versão (`nome@data`), a preservação de versões republicadas, a regra da Silver ("para cada arquivo, a versão mais recente; para cada mês da Selic, a leitura mais recente") e a recuperação de execução interrompida. Verificar: as seções 3 e 3.2 citam a tabela de controle e a regra da Silver.
- [x] 1.2 Atualizar `docs/data_dictionary.md`: formato de `_source_object` na `bronze_scr` (com exemplo), `_ingestion_mode` da Selic (`full` na primeira carga, `incremental` depois) e uma seção "Tabelas de controle" descrevendo `controle_scr.json` e `controle_selic.json` campo a campo. Verificar: o dicionário mostra o exemplo `scrdata_202408.csv@2026-09-15T02:38:32`.

## 2. Tabela de controle

- [x] 2.1 Acrescentar a `src/config.py` as constantes `DIR_CONTROLE = DIR_BRONZE / "_controle"`, `ARQUIVO_CONTROLE_SCR` e `ARQUIVO_CONTROLE_SELIC`, com comentário. Verificar: `pytest tests/test_config.py` passa.
- [x] 2.2 Criar `src/ingestion/controle.py` com `ler_controle(caminho) -> dict` (devolve `{}` se o arquivo não existir) e `gravar_controle(caminho, dados)` (grava em `.tmp` e renomeia: escrita atômica), comentados em pt-BR. Verificar: testes cobrem arquivo inexistente, ida e volta de um dicionário e ausência de `.tmp` sobrando.

## 3. SCR — versão por CSV e download condicionado

- [x] 3.1 Em `ler_blocos_do_zip()` / `carregar_scr()`, montar `_source_object` como `f"{nome}@{datetime(*info.date_time).isoformat()}"`, usando o `ZipInfo` de cada CSV. Verificar: o teste de metadados exige o formato `scrdata_202401.csv@AAAA-MM-DDTHH:MM:SS`.
- [x] 3.2 Antes de baixar, fazer `requests.head(url, timeout=config.TIMEOUT_DOWNLOAD_SCR)` e comparar o `ETag` com o controle: igual e ZIP em disco → não baixa; diferente ou sem ZIP → baixa (gravação atômica já existente) e só então registra o novo `ETag`. Se o `HEAD` falhar e o ZIP existir, usar o local com aviso no log. Verificar: testes com `requests.head` simulado cobrem os três casos, e no caso "igual" `requests.get` não é chamado.
- [x] 3.3 Comparar cada CSV com o controle (data + CRC32): pular os que estão `completo` com a mesma versão; marcar `em_andamento` antes do primeiro bloco e `completo` depois do último, gravando o controle a cada mudança de status. Verificar: um teste com ZIP republicado (só um CSV alterado) mostra que apenas esse CSV foi lido e que a versão antiga continua na Bronze.
- [x] 3.4 Recuperação: para uma versão encontrada `em_andamento`, ler da Bronze só os `_record_hash` daquele `_source_object` (`pyarrow.dataset` com filtro, uma coluna, `ignore_prefixes=["."]`) e gravar apenas as linhas ausentes. Verificar: um teste simula exceção na gravação do segundo bloco e, na execução seguinte, a versão fica completa sem duplicata.
- [x] 3.5 Caso teórico de CRC diferente com a mesma data: registrar erro em log e usar `nome@data#crc<hex>`. Verificar: teste unitário da função que monta o `_source_object`.
- [x] 3.6 Reconstrução do controle: se `controle_scr.json` não existir e a `bronze_scr` tiver dados, montar o controle a partir dos `_source_object` distintos da Bronze (versões marcadas `completo`) antes de ingerir. Verificar: teste que apaga o controle depois da primeira carga e confirma que a segunda execução não muda a contagem.

## 4. Selic — watermark

- [x] 4.1 Em `carregar_selic()`: ler o watermark; na primeira carga (sem watermark) gravar tudo com `_ingestion_mode="full"`; nas seguintes, filtrar `VALDATA[:10] >= watermark`, descartar os registros cujo `_record_hash` já está na `bronze_selic` e gravar o resto com `_ingestion_mode="incremental"`; atualizar o watermark para `max(VALDATA[:10])` só depois de gravar. Verificar: testes cobrem "nada mudou → 0 linhas novas", "mês corrente mudou de valor → 1 linha nova, a antiga continua", "mês novo → 1 linha e watermark avança" e "registros antigos não são regravados".

## 5. Testes de idempotência e de chave

- [x] 5.1 Criar `tests/test_idempotencia.py` com os cenários da spec `idempotencia-bronze` (pipeline rodado duas vezes, republicação, execução interrompida, controle apagado), sem rede (`requests.head`/`requests.get` simulados) e com pastas em `tmp_path`. Verificar: `pytest tests/test_idempotencia.py -v` verde.
- [x] 5.2 Criar `tests/test_no_duplicates.py`, que roda sequências de execuções (repetida, republicada, interrompida) e afirma `duplicated(["_source_object", "_record_hash"]).sum() == 0` nas duas tabelas. Verificar: verde; e, removendo de propósito a checagem de versão já ingerida, o teste **falha**. Desfazer em seguida.
- [x] 5.3 Ajustar os testes existentes de `tests/test_ingestion.py` que dependem do formato antigo de `_source_object` e do download incondicional. Verificar: `pytest -v` totalmente verde.

## 6. Conferência e demonstração

- [x] 6.1 Criar `scripts/conferir_bronze.py`: linhas por fonte e por ano, versões por mês (destacando meses com mais de uma versão) e duplicatas na chave, contando versão por versão para não carregar 34 milhões de hashes de uma vez. Verificar: roda sobre a Bronze real em poucos minutos e imprime zero duplicatas.
  - **Resultado (2026-09-27):** sobre a Bronze real, 26 s (a conferência ad hoc da Sprint 2 levava mais de 15 min). 34.121.187 linhas em 127 versões, 633 na Selic, 0 duplicatas nas duas tabelas.
- [x] 6.2 Acrescentar ao README a seção "Como demonstrar a idempotência" (conferir → rodar → rodar → conferir). Verificar: seguindo o README, as contagens antes e depois da segunda execução são iguais.

## 7. Migração dos dados locais e execução real

- [x] 7.1 Apagar `data/raw/bronze_scr`, `data/raw/bronze_selic`, `data/raw/_controle` (se existir) e `data/raw/_quarentena` (restos de testes antigos), mantendo `data/raw/_downloads`. Rodar `python scripts/run_pipeline.py` (carga completa). Verificar e anotar nesta task: tempo, contagens por ano (devem bater com as da Sprint 2: 34.121.187 no SCR, 633 na Selic) e o conteúdo dos dois arquivos de controle.
  - **Resultado (2026-09-27):** carga completa em 2.842 s (~47 min, incluindo baixar de novo os 11 ZIPs, porque os locais ainda não tinham versão registrada), sem nenhum erro. Contagens por ano idênticas às da Sprint 2 (total 34.121.187, 127 versões de CSV, todas `completo`); Selic 633 linhas em modo `full`. Controle: 11 anos com `ETag` registrado; watermark da Selic `2026-09-01`.
- [x] 7.2 Rodar `python scripts/run_pipeline.py` de novo e depois `python scripts/conferir_bronze.py`. Verificar e anotar: a segunda execução não baixa nenhum ZIP, termina em segundos e as contagens são idênticas às da 7.1, com zero duplicatas na chave. É a definição de pronto da Sprint 3.
  - **Resultado (2026-09-27): definição de pronto da Sprint 3 atingida.** Segunda execução em **13 s**, nenhum download (os 11 ZIPs com `ETag` igual), 0 versões novas e 0 linhas gravadas no SCR, 0 linhas na Selic. A saída de `conferir_bronze.py` antes e depois é idêntica, com 0 duplicatas na chave.
- [x] 7.3 Rodar `pytest -v` e conferir o CI verde no PR para o `develop`. Commits atômicos em pt-BR no padrão do projeto, **sem linha de atribuição**.
  - **Resultado:** 45 testes passando localmente; CI verde em Python 3.11 no PR #10. Commits sem linha de atribuição.
