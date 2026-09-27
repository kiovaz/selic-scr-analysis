## Why

A revisão da Sprint 2, feita antes de abrir a Sprint 3, encontrou problemas na ingestão Bronze que os testes não pegam:
- O pipeline nunca rodou de ponta a ponta com dado real.
- O teste de pronto não chama o loader do SCR.
- O download não tem timeout.
- A leitura do CSV inteiro com `iterrows` torna inviável processar cerca de 3,7 milhões de linhas por ano.

Há também um problema de desenho. A Bronze **aplica regras de negócio**: descarta 19 das 24 colunas do SCR, converte tipos, corta a Selic antes de jul/2016 e desvia registros para a quarentena. A seção 4.1 do `architecture.md` diz o contrário: a Bronze guarda o "dado como veio" e não descarta registro, enquanto "validações com quarentena" são tarefa da Silver.

Isso importa porque o reprocessamento sempre parte da Bronze. Com a quarentena na Bronze, uma regra com bug (por exemplo, rejeitar um mês inteiro por engano) faz o dado sumir da Bronze, e reprocessar depois de corrigir a regra não o traz de volta.

A Sprint 3 (idempotência) protege a Bronze contra duplicação. Não adianta proteger uma Bronze que já nasce errada, por isso as correções vêm antes.

**Decisões do grupo registradas nesta mudança:**
1. A Bronze guarda **todas as colunas da fonte, como vieram**. Só 5 colunas do SCR (`SCR_COLUNAS_USADAS`) viram Silver, e o corte e a tipagem acontecem lá.
2. A **quarentena por regra de negócio passa para a Silver** (Sprint 4). A Bronze só rejeita o que **não consegue ler** e registra isso em log.

## What Changes

Resumo no formato "como está → erro → como vai ficar". O antes e depois com código fica no `design.md`.

| # | Como está | Erro | Como vai ficar |
|---|---|---|---|
| 1 | `run_pipeline.py` nunca foi executado com dado real | A definição de pronto da Sprint 2 não foi comprovada | Execução real registrada, primeiro com `--anos 2024` e depois completa, com contagens anotadas |
| 2 | `test_definicao_de_pronto_sprint2` refaz o trabalho do loader dentro do teste | Se `carregar_scr()` quebrar, o teste continua verde | O teste chama `carregar_scr()` de verdade, sobre um ZIP local, sem rede |
| 3 | O loader do SCR faz `df[SCR_COLUNAS_USADAS]` e o pandas infere os tipos | A Bronze deixa de ser "dado como veio" (seção 4.1) | **BREAKING:** `bronze_scr` guarda **todas as colunas do CSV, como texto** |
| 4a | `requests.get(url, stream=True)` sem timeout | Uma conexão travada congela o pipeline | Timeout vindo de `config.TIMEOUT_DOWNLOAD_SCR` e gravação atômica do ZIP |
| 4b | O CSV é extraído para uma pasta temporária que nunca é apagada, lido inteiro e percorrido com `iterrows` | Lento (horas por ano), usa muita memória e deixa cerca de 1,15 GB de lixo em disco por ano | Leitura em blocos direto do ZIP, sem laço linha a linha e sem arquivo temporário |
| 5 | `config.RAIZ / 'data' / ...` no loader e no script de amostras; `scr_{ano}.zip` num e `scrdata_{ano}.zip` no outro | Caminhos fora do `config.py`, contra a regra do projeto | `DIR_DOWNLOADS_SCR`, `DIR_AMOSTRAS`, `SCR_NOME_ZIP` e outras constantes no `config.py` |
| 6 | `openspec/changes/fundacao-repositorio/` coexiste com a versão arquivada | O OpenSpec trata a Sprint 1 como mudança ativa | A cópia órfã é removida |
| 7 | Os dois loaders validam UF, data, sinal e tipo e mandam para a quarentena; a Selic corta antes de jul/2016 | Regra de negócio na Bronze, contra a seção 4.1 | **BREAKING:** os loaders **não validam regra de negócio nem cortam período**. Registro sujo entra intacto na Bronze e é barrado na Silver (Sprint 4). A Bronze só rejeita, com log, CSV sem as colunas esperadas e resposta da API que não é JSON OData válido |

O módulo `src/validation/quality_checks.py` (checagens e quarentena) **continua existindo**. Ele deixa de ser chamado pelos loaders e passa a ser usado pela Silver na Sprint 4.

Fora do escopo:
- Idempotência, watermark da Selic e `test_idempotencia.py` ficam para a Sprint 3.
- Implementar a Silver e chamar a quarentena a partir dela fica para a Sprint 4.
- Renomear a capability `validacao-bronze`, cujo nome ficou impreciso agora que ela serve à Silver, fica para uma mudança separada, se o grupo quiser.

## Capabilities

### New Capabilities

*(Nenhuma.)*

### Modified Capabilities

- `ingestao-scr`: a Bronze preserva todas as colunas do CSV como texto; o download ganha timeout; a leitura é feita em blocos, sem arquivo temporário; caminhos e nomes vêm do `config.py`; o loader aceita a lista de anos. **Removido:** a integração com validação e quarentena. **Novo:** o registro sujo entra intacto na Bronze.
- `ingestao-selic`: a Bronze preserva os campos da API como vieram, sem converter tipo e sem recorte temporal. **Removido:** a integração com validação e quarentena. **Novo:** a rejeição passa a ser só estrutural (resposta ilegível).
- `validacao-bronze`: as checagens e a quarentena continuam com as mesmas regras, mas passam a ser aplicadas pela Silver e não mais pelos loaders da Bronze.

## Impact

- **Código:** `src/config.py`, `src/ingestion/scr_file_loader.py`, `src/ingestion/selic_api_loader.py`, `src/ingestion/metadata.py`, `scripts/baixar_amostras.py`, `scripts/run_pipeline.py`. `src/validation/quality_checks.py` não muda.
- **Testes:** `tests/test_ingestion.py` é reescrito. Os testes que esperavam quarentena a partir dos loaders passam a esperar o registro sujo intacto na Bronze. `tests/test_validation.py` continua como está.
- **Documentação:**
  - `docs/architecture.md`: registro das duas decisões nas seções 3.3 e 4.1, e ajuste da definição de pronto da Sprint 2 e dos itens da Sprint 4 na seção 8.
  - `docs/data_dictionary.md`: `bronze_scr` e `bronze_selic` como vieram da fonte; mês incompleto e recorte passam a ser descartados na Silver.
  - `README.md`: a linha da Sprint 2 no checklist.
  - Purpose da spec principal `validacao-bronze`.
- **Dados:** a `bronze_scr` ocupa mais espaço (24 colunas em vez de 5) e a `bronze_selic` guarda a série inteira. Os dois são pequenos em Parquet, e nada vai para o Git.
- **Silver (Sprint 4):** passa a ser responsável por selecionar as colunas, tipar, aplicar o recorte jul/2016, validar e mandar para a quarentena. Isso já estava previsto na seção 4.1.
- **Dependências:** nenhuma nova.
