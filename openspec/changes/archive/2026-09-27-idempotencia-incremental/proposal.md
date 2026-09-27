## Why

Hoje, rodar o pipeline duas vezes **duplica a Bronze**. Cada execução baixa e grava tudo de novo, e o `_record_hash` é calculado mas nunca consultado. A seção 3.2 do `architecture.md` exige o contrário: "rodar a ingestão duas vezes seguidas não pode alterar a contagem final de linhas", e isso será demonstrado ao vivo na defesa. É a definição de pronto da Sprint 3.

A primeira execução real (2026-09-26) trouxe um fato novo que muda o desenho: **o BCB republica meses já publicados**. O `scrdata_202408.csv` foi regravado em 2026-09-15 com 3 linhas a menos. Uma idempotência ingênua ("pular o que já tem o mesmo hash") trataria a versão nova como repetida, porque a maior parte das linhas não muda e o nome do arquivo é o mesmo. O resultado seria um agosto incompleto. Esta mudança resolve os dois problemas juntos.

## What Changes

- **Controle de ingestão do SCR em dois níveis** (tabela de controle em `data/raw/_controle/`):
  - **ZIP:** antes de baixar, uma requisição `HEAD` lê o `ETag` do ZIP. Se for igual ao registrado, o ano é pulado sem download. Conferido: o servidor do BCB devolve `ETag` e `Last-Modified`.
  - **CSV:** se o ZIP mudou, o índice do ZIP informa o CRC32 e a data de cada CSV. Só os CSVs novos ou alterados são ingeridos. Numa republicação, só o mês alterado é reprocessado.
- **BREAKING — `_source_object` do SCR passa a identificar a versão do arquivo:** `scrdata_202408.csv@2026-09-15T02:38:32`, com o nome mais a data interna do arquivo no ZIP. A versão nova de um mês republicado entra **completa** na Bronze, e a versão anterior **continua guardada** (a Bronze é imutável, seção 4.1). A Silver usará a versão mais recente de cada mês (regra registrada agora, implementada na Sprint 4).
- **Recuperação de execução interrompida:** se um CSV foi gravado pela metade (queda, suspensão da máquina), a próxima execução completa o que falta sem duplicar, comparando o `_record_hash` só dentro daquela versão.
- **Selic incremental por watermark:** uma tabela de controle guarda o último mês ingerido. **A API do Ipeadata ignora `$filter`, `$top` e `$orderby`** (conferido em 2026-09-27: sempre devolve os 633 registros). Por isso a carga incremental baixa a série inteira (~60 KB) e **grava só o que falta**: os registros a partir do watermark, inclusive, cujo hash ainda não está na Bronze. O mês corrente, que muda até fechar, entra como uma nova linha quando o valor muda, e a Silver usa a mais recente. `_ingestion_mode` passa a ser `incremental` depois da primeira carga.
- **Testes:** `tests/test_idempotencia.py` (duas execuções = mesma contagem; republicação acrescenta só a versão nova; execução interrompida é completada) e `tests/test_no_duplicates.py` (chave `(_source_object, _record_hash)` da Bronze sem duplicata).
- **`scripts/conferir_bronze.py`:** conferência para a demonstração na defesa. Mostra as contagens por fonte e por ano, as versões guardadas e as duplicatas na chave (deve ser zero).
- **CI:** já existe e está verde. A única mudança é manter os testes novos sem acesso à rede, para rodarem no GitHub Actions.

Fora do escopo: a Silver (Sprint 4), que vai **aplicar** a regra "versão mais recente".

## Capabilities

### New Capabilities
- `idempotencia-bronze`: garantias que valem para as duas fontes. Reexecução não muda a contagem, a chave da Bronze não tem duplicata, versões republicadas são preservadas e uma execução interrompida é completada sem duplicar.

### Modified Capabilities
- `ingestao-scr`: o download passa a ser condicionado ao `ETag`; a ingestão passa a ser por versão de CSV (CRC e data); `_source_object` inclui a versão; entra a tabela de controle.
- `ingestao-selic`: a ingestão passa a ser incremental por watermark, com gravação só do que falta; `_ingestion_mode` passa a variar entre `full` e `incremental`.

## Impact

- **Código:** `src/config.py` (pasta e arquivos de controle), `src/ingestion/scr_file_loader.py`, `src/ingestion/selic_api_loader.py`, e um novo `src/ingestion/controle.py` (leitura e gravação da tabela de controle). `scripts/run_pipeline.py` não muda de interface.
- **Testes:** dois arquivos novos e ajustes em `tests/test_ingestion.py`.
- **Documentação:** `docs/architecture.md` (seções 3, 3.2 e 3.3: tabela de controle, versões, API sem filtro), `docs/data_dictionary.md` (formato do `_source_object` e tabelas de controle) e o README (como demonstrar a idempotência).
- **Dados locais:** a Bronze atual desta máquina foi gravada com `_source_object` sem versão. Ela precisa ser apagada e reingerida **uma vez** depois da mudança (cerca de 35 minutos). Nada disso vai para o Git.
- **Dependências:** nenhuma nova.
