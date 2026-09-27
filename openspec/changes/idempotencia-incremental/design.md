## Context

A motivação está em `proposal.md — Why`, e os requisitos nas specs delta (`ingestao-scr`, `ingestao-selic`, `idempotencia-bronze`).

Estado atual relevante (branch `feat/sprint-3-idempotencia`, a partir do arquivamento da `correcoes-ingestao-bronze`):
- `carregar_scr()` baixa ou reaproveita o ZIP, lê todos os CSVs em blocos e grava tudo. Não há nenhuma consulta ao que já está na Bronze.
- `carregar_selic()` requisita a série e grava tudo com `_ingestion_mode='full'`.
- `anexar_metadados()` calcula `_record_hash = sha256(json(registro) + _source_object)`, e hoje `_source_object` é só o nome do CSV.
- A Bronze é um dataset Parquet particionado por `_ingestion_date`, e precisa ser lida com `ignore_prefixes=["."]`.

Fatos conferidos antes do desenho:
- O servidor do BCB responde `HEAD` com `ETag`, `Last-Modified` e `Content-Length`. Em 2026-09-27, o `scrdata_2024.zip` tinha `Last-Modified` de 15/09/2026, que é a republicação de agosto.
- O índice do ZIP traz, por CSV, o CRC32 e a data do arquivo (`scrdata_202408.csv`: CRC `0xfedecd9f`, data 2026-09-15 02:38:32). Ler esses dados não exige descompactar.
- Nenhuma linha duplicada dentro de um mesmo CSV em 2024: 0 em 3.726.512.
- A API do Ipeadata ignora `$filter`, `$top` e `$orderby`: devolve sempre os 633 registros.

## Goals / Non-Goals

**Goals:**
- Rodar o pipeline duas vezes não muda nenhuma contagem, e a segunda execução termina em segundos.
- Uma republicação do BCB entra como versão nova e completa, sem apagar nada.
- Uma queda no meio da gravação é completada na próxima execução, sem duplicar.
- Tudo demonstrável ao vivo na defesa (seção 3.2).

**Non-Goals:**
- Aplicar "versão mais recente" na leitura. Isso é da Silver (Sprint 4), e aqui só fica registrado como regra.
- Detectar revisão de meses **antigos** da Selic, anteriores ao watermark. A Selic realizada não costuma ser revista, e o custo não se justifica agora.
- Apagar versões antigas ou compactar a Bronze.

## Decisions

### 1. Tabela de controle em JSON, uma por fonte

Ficam em `data/raw/_controle/controle_scr.json` e `data/raw/_controle/controle_selic.json`, com os caminhos no `config.py`:

```json
// controle_scr.json
{"2024": {"etag": "\"5bf84e73d444dd1:0\"",
          "csvs": {"scrdata_202408.csv": {"data": "2026-09-15T02:38:32", "crc32": "fedecd9f", "status": "completo"}}}}
// controle_selic.json
{"watermark": "2026-09-01"}
```

*Por que JSON e não Parquet:* são poucos KB, qualquer integrante abre no editor e entende, e a escrita é atômica com o mesmo truque do ZIP (grava em `.tmp` e renomeia). *Alternativa descartada:* SQLite, que seria mais uma tecnologia para todo mundo saber explicar (seção 7). A pasta começa com `_`, junto de `_quarentena` e `_downloads`, e fica fora do Git como tudo em `data/`.

### 2. SCR — detecção de mudança em dois níveis

```
para cada ano:
  etag = HEAD(url).headers["ETag"]           # alguns bytes, sem baixar o ZIP
  se etag == controle[ano].etag e ZIP em disco → usa o ZIP local
  senão → baixa (gravação atômica .parcial), registra o etag depois
  para cada CSV no índice do ZIP:
      versão = (data do arquivo, CRC32)       # zipfile.ZipInfo — sem descompactar
      se controle tem a mesma versão com status "completo" → pula
      senão → ingere como versão nova
```

- *Por que `ETag` e não só `Last-Modified`:* o `ETag` muda com o conteúdo, e a data pode ficar igual se o arquivo for regravado no mesmo segundo. O `Last-Modified` vai para o log, para ajudar a humanos.
- *Se o `HEAD` falhar* (rede instável), usa-se o ZIP local, com aviso no log, e a comparação por CSV ainda protege contra reingestão.
- *Por que dois níveis:* o `ETag` evita baixar 1,5 GB à toa; o CRC por CSV evita reprocessar 12 meses quando só um mudou.
- *Mesmo sem o `ETag`*, um ZIP de 2026 que ganhou agosto teria os meses de jan a jul com o mesmo CRC, e só agosto seria ingerido.

### 3. `_source_object` com versão

Hoje é `scrdata_202408.csv`; passa a ser `scrdata_202408.csv@2026-09-15T02:38:32`.

```python
source_object = f"{nome_csv}@{datetime(*info.date_time).isoformat()}"
```

- É isso que faz a versão republicada entrar **inteira**. Sem a versão, uma linha que não mudou teria o mesmo hash nas duas publicações e seria tratada como "já ingerida", e agosto ficaria só com as linhas alteradas.
- A fórmula do hash (seção 3.2) **não muda**: continua sendo conteúdo + `_source_object`. Só o `_source_object` ficou mais preciso.
- Na Silver (Sprint 4): `arquivo = _source_object.split("@")[0]`, e para cada arquivo fica a maior versão. Essa regra vai para a seção 3.2 do `architecture.md` e para o dicionário de dados agora, para a Sprint 4 não precisar redescobrir.
- *Caso teórico:* CRC diferente com a mesma data. O loader registra um erro no log e usa `nome@data#crc<hex>`, para não colidir com a versão anterior.

*Alternativa descartada:* uma coluna nova `_source_version`, fora do `_source_object`. Mudaria a lista de metadados da seção 3.1 e a fórmula do hash, e seria mais uma coisa para explicar.

### 4. Execução interrompida

O controle marca a versão como `"em_andamento"` **antes** de gravar o primeiro bloco e como `"completo"` **depois** do último.
- **Caminho normal:** não há versão `em_andamento`, então não há custo extra.
- **Se a próxima execução encontrar uma versão `em_andamento`:** lê da Bronze só os `_record_hash` daquele `_source_object`, com filtro do pyarrow (`ds.field("_source_object") == versão`, lendo uma coluna), e grava apenas os blocos com linhas cujo hash não está nesse conjunto.

*Por que não apagar a gravação parcial e refazer:* a Bronze é imutável (seção 4.1), e apagar arquivos de uma partição é justamente o tipo de operação que perde dado quando dá errado.

A suspensão do notebook que vimos na Sprint 2 **não** conta como interrupção: o processo continua depois. Só conta se o processo morrer.

### 5. Selic — watermark com gravação só do que falta

```
serie = GET(api)                                    # sempre os 633 registros (API ignora filtros)
wm = controle_selic.watermark                       # ex.: "2026-09-01"; ausente na 1ª carga
candidatos = serie if wm is None else serie[VALDATA[:10] >= wm]
novos = candidatos sem hash na bronze_selic          # a bronze_selic é pequena: lê a coluna inteira
grava novos (_ingestion_mode = "full" se wm is None, senão "incremental")
atualiza watermark = max(VALDATA[:10]) depois de gravar
```

- **O mês do watermark é reavaliado de propósito:** setembro vale 0,88 hoje e vai mudar até o mês fechar. Com `>=`, o valor novo gera um hash novo e entra como nova linha; com o mesmo valor, o hash é igual e nada entra. A Silver pega a leitura mais recente de cada mês (`_ingestion_timestamp`), e essa regra também vai para o `architecture.md`.
- **Comparação de datas pelo texto `AAAA-MM-DD`:** o fuso da API alterna entre `-02:00` e `-03:00` (horário de verão antigo), e comparar o texto completo daria resultados errados. Os 10 primeiros caracteres bastam, porque a série é mensal.
- **A seção 3 do `architecture.md`** dizia "busca só o que falta". Ela será corrigida para "baixa a série e grava só o que falta", com a evidência de que a API ignora filtros.

### 6. Testes sem rede

- **Isolamento:** `requests.head` e `requests.get` são simulados com `unittest.mock`, e as pastas `DIR_BRONZE` e de controle apontam para `tmp_path`, como nos testes atuais.
- **`test_idempotencia.py`:**
  - duas execuções com o mesmo ZIP e o mesmo `ETag` dão a mesma contagem, e a segunda não chama `requests.get`;
  - um ZIP republicado com um CSV alterado acrescenta só aquele CSV, e a versão antiga continua;
  - uma interrupção simulada (exceção no segundo bloco) é completada na próxima execução sem duplicar;
  - Selic: duas execuções iguais não gravam nada novo, e uma mudança no valor do mês corrente acrescenta 1 linha.
- **`test_no_duplicates.py`:** depois de cada cenário acima, a chave `(_source_object, _record_hash)` não tem duplicata nas duas tabelas.

### 7. Script de conferência para a defesa

`scripts/conferir_bronze.py` lê só as colunas de metadado e imprime:
- as linhas por fonte e por ano;
- as versões guardadas por mês, destacando os meses com mais de uma versão;
- a quantidade de duplicatas na chave.

Roteiro da demonstração: rodar `conferir_bronze.py`, rodar `run_pipeline.py`, rodar `conferir_bronze.py` de novo e mostrar as mesmas contagens. Para ficar leve com 34 milhões de linhas, conta as duplicatas por `_source_object` (uma versão por vez), sem carregar todos os hashes juntos. Foi isso que deixou lenta a conferência da Sprint 2.

## Risks / Trade-offs

- [A Bronze local foi gravada sem versão no `_source_object`] → a primeira execução depois desta mudança não teria controle e reingeriria tudo com `_source_object` novo, duplicando o conteúdo. Mitigação: uma task explícita apaga `data/raw/bronze_*`, `data/raw/_controle` e a quarentena de teste antes de reingerir (~35 minutos). Os ZIPs em `_downloads` são mantidos.
- [O BCB mudar o `ETag` sem mudar o conteúdo, por exemplo ao regravar o arquivo idêntico] → baixa-se o ZIP de novo (~50 s), mas o CRC por CSV não muda e nada é reingerido. O custo é só de download.
- [A tabela de controle for apagada ou corrompida] → a próxima execução trata tudo como novo e reingere, gerando **as mesmas** versões (mesmo `_source_object`, mesmos hashes), o que duplicaria a Bronze. Mitigação: se o controle não existir mas a Bronze tiver dados, o loader reconstrói o controle a partir dos `_source_object` presentes na Bronze antes de começar, e registra isso no log.
- [O CRC32 colidir entre versões] → a probabilidade é desprezível, e a data do arquivo também entra na comparação.
- [A leitura filtrada da Bronze na recuperação varrer 4,9 GB] → só acontece no caminho de exceção (versão `em_andamento`), e lê uma única coluna com filtro.

## Migration Plan

1. Implementar e rodar o `pytest`, que não depende de rede nem de dados locais.
2. Apagar `data/raw/bronze_scr`, `data/raw/bronze_selic` e `data/raw/_quarentena`. Os arquivos atuais da quarentena são restos de testes antigos da Sprint 2, gravados antes de a quarentena passar para a Silver.
3. `python scripts/run_pipeline.py`, a carga inicial completa, reaproveitando os ZIPs.
4. `python scripts/run_pipeline.py` de novo, que deve terminar em segundos. Depois `python scripts/conferir_bronze.py`: contagens iguais e zero duplicatas.

Rollback: é só reverter o PR. Os dados locais podem ser regenerados a partir dos ZIPs.
