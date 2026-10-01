## Context

A motivação e as duas decisões do grupo estão em `proposal.md — Why`. Os requisitos estão nas specs delta de `ingestao-scr`, `ingestao-selic` e `validacao-bronze`. Este documento mostra, para cada item, **como está o código hoje, qual é o erro e como vai ficar**.

Estado atual relevante:
- `src/ingestion/scr_file_loader.py` tem três etapas: `baixar_zips()`, depois `ler_csvs_do_zip()` (que devolve o CSV inteiro já cortado em 5 colunas) e por fim `carregar_scr()` (que valida com `iterrows`, manda para a quarentena e grava).
- `src/ingestion/selic_api_loader.py`: `parsear_resposta_selic()` converte os tipos e corta antes de jul/2016, e `carregar_selic()` valida e manda para a quarentena.
- `src/validation/quality_checks.py` tem as checagens de um valor por vez e a quarentena. **Não muda nesta mudança.**
- `src/ingestion/metadata.py` calcula o `_record_hash` com `iterrows`.
- `openspec list` mostra `fundacao-repositorio` com 22/23 tasks, embora a versão arquivada esteja completa.
- A Sprint 1 confirmou que o CSV do SCR usa `utf-8-sig`, `;` como separador e `,` como decimal, e que um ano tem cerca de 3,7 milhões de linhas em 12 CSVs.

## Goals / Non-Goals

**Goals:**
- Deixar a Bronze fiel à seção 4.1: dado como veio, sem regra de negócio e sem descarte.
- Tornar viável processar um ano inteiro do SCR numa máquina comum.
- Fazer o teste de pronto falhar quando o loader real quebrar.
- Tirar do código todo caminho e constante que deveria estar no `config.py`.

**Non-Goals:**
- Construir a Silver e ligar a quarentena a ela (Sprint 4). Nesta mudança, os loaders só **deixam de chamar** a validação.
- Mudar `quality_checks.py`, seja com versões vetorizadas ou com quarentena em lote. Isso será decidido no desenho da Silver, quando se souber como ela lê a Bronze.
- Mudar a fórmula do `_record_hash`. Ela continua sendo `json.dumps(registro, sort_keys=True) + _source_object` e passa a cobrir todos os campos da fonte.
- Deduplicação, idempotência e watermark (Sprint 3).

## Decisions

### Item 1 — Rodar o pipeline de verdade

**Como está:** `data/raw/` só tem `_quarentena/`. Nunca existiu `bronze_scr/` nem `bronze_selic/` nesta máquina.

**Erro:** a definição de pronto da Sprint 2 foi aceita só com testes sintéticos.

**Como vai ficar:** o `run_pipeline.py` ganha o argumento `--anos`, repassado a `carregar_scr(anos=...)`:
```python
parser = argparse.ArgumentParser()
parser.add_argument("--anos", type=int, nargs="*",
                    help="Anos do SCR a processar (padrão: ANO_INICIO a ANO_FIM)")
args = parser.parse_args()
load_id_scr = carregar_scr(anos=args.anos)
```
A primeira execução real é `python scripts/run_pipeline.py --anos 2024`. Como a Bronze não descarta mais nada, a conferência fica simples: **linhas na `bronze_scr` = 3.726.515**, o total medido na Sprint 1. Só depois disso roda o intervalo inteiro.

### Item 2 — Teste de pronto chamando o loader real

**Como está:**
```python
dfs_scr = ler_csvs_do_zip(zip_path)
for idx, row in df_scr.iterrows():          # o teste refaz o trabalho do loader
    motivo = validar_registro(row, config)
    ...
df_scr_v.to_parquet(dir_scr / f"scr_{load_id_scr}.parquet")
```

**Erro:** `carregar_scr()` não é chamado. Se ele quebrar, o teste continua verde.

**Como vai ficar:** o teste coloca o ZIP sintético na pasta de downloads com o nome oficial e chama o loader, que reaproveita o arquivo local sem acessar a rede. A expectativa também muda com a decisão da quarentena: o registro `XX` agora **entra** na Bronze.
```python
def test_definicao_de_pronto_sprint2(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DIR_BRONZE", tmp_path / "raw")
    dir_zips = tmp_path / "zips"
    _criar_zip_teste(dir_zips, rows_scr, zip_name=config.SCR_NOME_ZIP.format(ano=2024))

    carregar_scr(dir_download=dir_zips, anos=[2024])        # loader real

    bronze = pd.read_parquet(config.DIR_BRONZE / "bronze_scr")
    assert len(bronze) == len(rows_scr)                     # nada foi descartado
    assert "XX" in set(bronze["uf"])                        # sujo entra intacto
    assert not (config.DIR_BRONZE / "_quarentena").exists() # loader não usa quarentena
```
O ZIP de teste também traz um CSV sem a coluna `uf`, para provar que a rejeição **estrutural** continua funcionando.

*Alternativa descartada:* substituir `baixar_zips` com `monkeypatch`. Funciona, mas pula o caminho de "reaproveitar o ZIP local", que também está na spec.

### Item 3 — Bronze do SCR com todas as colunas, como texto

**Como está:**
```python
temp_df = pd.read_csv(..., decimal=',', low_memory=False)   # pandas infere os tipos
df_filtrado = df[config.SCR_COLUNAS_USADAS].copy()          # joga fora 19 colunas
```

**Erro:** há dois descartes, e a seção 4.1 proíbe os dois. Um é de colunas. O outro é do texto original, quando o pandas converte `"0001"` em `1` ou lê `"NA"` como nulo.

**Como vai ficar:**
```python
pd.read_csv(arquivo, sep=config.SCR_SEPARADOR, encoding=encoding,
            dtype=str,              # tudo como texto: nada é convertido
            keep_default_na=False,  # "NA" e "" continuam sendo o texto que vieram
            chunksize=config.SCR_TAMANHO_BLOCO)
```
O cabeçalho continua sendo conferido contra as 5 colunas usadas. Um CSV sem elas não serve ao projeto e é rejeitado inteiro, com log, o que é uma rejeição estrutural. O `decimal=','` sai do loader, porque na Bronze nada é convertido. Quando a Silver precisar, a constante `SCR_DECIMAL` entra no `config.py` na Sprint 4.

*Por que é o certo:* é a convenção medallion. A camada crua é a fonte de verdade reprocessável. Se a Silver precisar de mais uma coluna (por exemplo `porte`), basta reprocessar a partir do disco, sem baixar cerca de 2 GB de novo do BCB.

### Item 4a — Timeout e gravação atômica no download

**Como está:** `requests.get(url, stream=True)`, gravando direto em `scr_{ano}.zip`.

**Erro:** sem timeout, uma conexão que para de mandar bytes trava o pipeline. E se o download cair no meio, o ZIP incompleto fica no caminho final e é "reaproveitado" na próxima execução.

**Como vai ficar:**
```python
# config.py
# (conectar, ler) em segundos. O "ler" é o tempo máximo SEM receber nenhum byte,
# não o tempo total do download — por isso 300 s é folgado para um ZIP de 170 MB.
TIMEOUT_DOWNLOAD_SCR = (10, 300)

# scr_file_loader.py
caminho_parcial = zip_path.with_suffix(".zip.parcial")
response = requests.get(url, stream=True, timeout=config.TIMEOUT_DOWNLOAD_SCR)
... grava em caminho_parcial ...
caminho_parcial.replace(zip_path)   # só vira .zip quando terminou inteiro
```

### Item 4b — Leitura em blocos, sem arquivo temporário e sem `iterrows`

**Como está:**
```python
temp_dir = tempfile.mkdtemp()                           # nunca é apagado
extracted_path = zip_ref.extract(csv_file, temp_dir)    # ~100 MB por CSV
temp_df = pd.read_csv(extracted_path, ...)              # CSV inteiro em memória
for index, row in df.iterrows():                        # ~3,7 mi de iterações por ano
    ...
```

**Erro:** vazam cerca de 1,15 GB em pasta temporária por ano, o consumo de memória é alto e `iterrows` leva horas no volume real.

**Como vai ficar:**
```python
with zipfile.ZipFile(zip_path) as z:
    for nome_csv in csvs:
        encoding = detectar_encoding(z, nome_csv)       # testa os candidatos no início do arquivo
        with z.open(nome_csv) as arquivo:               # lê direto do ZIP, sem extrair
            for bloco in pd.read_csv(arquivo, dtype=str, chunksize=..., ...):
                gravar_bronze(anexar_metadados(bloco, ...))
```
Com a validação fora do loader, o laço linha a linha desaparece por completo. Sobra apenas o cálculo do `_record_hash`, em que `anexar_metadados` troca o `iterrows` por `to_dict("records")`: mesma fórmula, algumas vezes mais rápido.

*Detecção de encoding:* decodificar os primeiros ~1 MB com cada candidato, na ordem de `SCR_ENCODINGS_CANDIDATOS`. *Alternativa descartada:* tentar `read_csv` inteiro com cada encoding, como é hoje, o que no pior caso lê o arquivo três vezes.

*Tamanho do bloco:* `SCR_TAMANHO_BLOCO = 200_000` linhas no `config.py`.

### Item 5 — Caminhos e constantes no `config.py`

**Como está:**
```python
# scr_file_loader.py
dir_download = config.RAIZ / 'data' / 'downloads'
zip_filename = f"scr_{ano}.zip"
# scripts/baixar_amostras.py
PASTA_AMOSTRAS = config.RAIZ / "data" / "raw" / "_amostras"
caminho_zip = PASTA_AMOSTRAS / f"scrdata_{ANO_AMOSTRA}.zip"
```

**Erro:** viola a regra "nenhum outro arquivo pode ter caminho chumbado". Os dois scripts também dão nomes diferentes ao mesmo arquivo.

**Como vai ficar:**
```python
# config.py
DIR_AMOSTRAS = DIR_BRONZE / "_amostras"          # amostras da Sprint 1 (diagnóstico)
DIR_DOWNLOADS_SCR = DIR_BRONZE / "_downloads"    # ZIPs baixados pelo loader
SCR_NOME_ZIP = "scrdata_{ano}.zip"               # mesmo nome publicado pelo BCB
SCR_TAMANHO_BLOCO = 200_000
TIMEOUT_DOWNLOAD_SCR = (10, 300)
```
As duas pastas continuam separadas, porque a spec `diagnostico-fontes` fixa `data/raw/_amostras/`. Com o nome igual, quem já tem a amostra de 2024 pode copiá-la para `_downloads/`.

### Item 6 — Pasta duplicada no OpenSpec

**Como está:** existem `openspec/changes/fundacao-repositorio/` (com a task 5.4 desmarcada) e `openspec/changes/archive/2026-09-04-fundacao-repositorio/` (completa).

**Erro:** o arquivamento deveria ter **movido** a pasta. A cópia antiga provavelmente voltou com os reverts das PRs #3 e #5.

**Como vai ficar:** `git rm -r openspec/changes/fundacao-repositorio`.

### Item 7 — Tirar a regra de negócio dos loaders

**Como está:**
```python
# scr_file_loader.py
motivo = validar_registro(row, config)     # uf, data, tipagem, negativo
if motivo: enviar_para_quarentena(...)

# selic_api_loader.py
valvalor_float = float(valvalor_raw)       # converte
if valdata_dt >= cutoff_date: ...          # corta antes de jul/2016
erro_neg = checar_valor_nao_negativo(...)  # valida
enviar_para_quarentena(...)
```

**Erro:** a seção 4.1 proíbe regra de negócio e descarte na Bronze. Se uma regra tiver bug, o registro some da camada de onde todo reprocessamento parte.

**Como vai ficar:**
- **SCR:** `validar_registro` e as chamadas à quarentena saem do loader. Cada bloco lido vai direto para a Bronze com os metadados.
- **Selic:** o loader grava cada item de `value` com todos os seus campos convertidos para texto (`str()` sobre o valor do JSON), sem corte de data e sem checagem. Ele só rejeita, com log, uma resposta que não é JSON ou que não tem a chave `value`.
- **Os dois:** `quality_checks.py` fica intacto, e seus testes (`tests/test_validation.py`) continuam valendo. A Silver o usará na Sprint 4.

**Por que texto na Selic também:** a API devolve `VALVALOR` como número, mas um registro nulo ou com texto misturaria tipos na mesma coluna e faria a escrita do Parquet falhar, derrubando o job. Tudo como texto é o mesmo contrato do SCR, e a conversão fica toda na Silver. `str()` de um `float` em Python é reversível, então nenhuma casa decimal se perde.

*Alternativa descartada:* uma "Bronze que valida mas não descarta", gravando o motivo numa coluna `_motivo`. Isso mistura regra de negócio com a camada crua, e o motivo ficaria desatualizado toda vez que a regra mudasse.

### Achado na implementação — leitura da Bronze voltava vazia

Ao escrever os testes que leem a Bronze de volta, apareceu um problema que existia desde a Sprint 2. `pd.read_parquet("data/raw/bronze_scr")` devolvia uma tabela **vazia, sem erro**. O motivo é que o pyarrow ignora, por padrão, pastas cujo nome começa com `_` ou `.`, e a partição se chama `_ingestion_date=AAAA-MM-DD`. Os testes antigos não pegavam o problema porque só contavam arquivos com `glob` e nunca liam o conteúdo.

**Decisão:** ler com `pd.read_parquet(caminho, ignore_prefixes=["."])`, o que continua cumprindo a spec ("lido com `pd.read_parquet()`"). A forma de leitura ficou documentada em `docs/data_dictionary.md` ("Como ler a Bronze").

*Alternativa descartada:* renomear a partição para `ingestion_date`, sem o `_`. Isso quebraria a convenção da seção 3.1 (metadados com prefixo `_`). A Silver, na Sprint 4, deve centralizar essa leitura numa função.

## Risks / Trade-offs

- [Um CSV com encoding diferente depois do primeiro 1 MB] → o `read_csv` levanta erro de decodificação no meio. Mitigação: o erro é capturado por CSV, registrado em log e o CSV é rejeitado sem derrubar o job, como já acontece com coluna ausente.
- [Bronze maior em disco, com 24 colunas e a série da Selic inteira] → Parquet comprime bem texto repetitivo. É o preço de reprocessar sem ir à fonte.
- [Entre esta mudança e a Sprint 4, nada barra o dado sujo] → não há consumidor da Bronze até a Silver existir, então nada é afetado. O dado sujo fica guardado e será barrado quando a Silver for construída.
- [Mudança de schema da `bronze_scr` e da `bronze_selic`] → não há dado real gravado que dependa do formato antigo. Se alguém tiver, basta apagar `data/raw/bronze_*` e rodar de novo.
- [A definição de pronto da Sprint 2 muda de texto] → a nova versão fica registrada no `architecture.md`, com a data e o motivo, para ninguém achar que a sprint foi "desfeita".
- [A primeira execução real encontrar surpresas em anos antigos] → é o objetivo do item 1. O que aparecer vira nota no `architecture.md` antes de fechar esta mudança.

## Migration Plan

1. Registrar as decisões no `architecture.md` e no dicionário de dados. A especificação vem antes do código.
2. Implementar os itens 5, 7, 3, 4 e 2, nessa ordem, rodando `pytest` a cada etapa.
3. Remover a pasta duplicada (item 6).
4. Rodar `python scripts/run_pipeline.py --anos 2024` e conferir as contagens (item 1). Depois rodar o intervalo completo.

Rollback: é só reverter o PR. Nenhum dado versionado é afetado.
