## Context

Motivação em `proposal.md — Why`; requisitos em `specs/diagnostico-fontes/spec.md`.

Estado atual verificado no repositório:

- A estrutura da seção 9 do `docs/architecture.md` já existe: `src/` com os cinco subpacotes, `tests/`, `scripts/`, `docs/`, `notebooks/` (vazia), `data/` com `raw/`, `processed/`, `final/`, `raw/_quarentena/` e `.gitkeep` nas três camadas.
- `requirements.txt` com versões fixadas, `.gitignore` cobrindo `data/`, `*.csv`, `*.zip`, `*.parquet`, `README.md`, `Dockerfile`, `docker-compose.yml` e `.github/workflows/ci.yml` (pytest 3.11 em push e PR) já estão no lugar.
- `src/config.py` concentra caminhos, URLs e constantes; `tests/test_config.py` tem 7 testes que cobrem as constantes.
- `scripts/baixar_amostras.py` já existe e faz o diagnóstico das duas fontes, mas **sempre rebaixa o ZIP**.
- `data/raw/_amostras/scrdata_2024.zip` já está em disco com 176 MB — o download do SCR funciona; falta registrar isso.
- `openspec/specs/` está vazio: `diagnostico-fontes` é o primeiro spec do projeto.

Restrições que moldam o desenho: o ZIP tem ~176 MB e o CSV descompactado é bem maior que isso; o CI roda offline; nenhum dado pode ir para o Git; e todo integrante precisa saber explicar qualquer trecho entregue.

## Goals / Non-Goals

**Goals:**

- Responder as perguntas da definição de pronto da Sprint 1 com evidência de arquivo real, não com suposição.
- Deixar o diagnóstico repetível por qualquer integrante em um comando, reaproveitando a amostra já baixada.
- Ler a amostra sem carregar o CSV inteiro em memória.

**Non-Goals:**

- Ingestão. Nada é escrito em `data/raw/` como camada Bronze nesta sprint — `_amostras/` é área de inspeção, não Bronze.
- Módulo de validação reutilizável em `src/validation/`. Decisão do grupo: nesta sprint a validação é manual. `quality_checks.py` entra na Sprint 2, junto com os loaders que vão consumi-lo.
- Testes que acessam a rede. O CI continua offline.

## Decisions

**1. Validação manual (script + notebook) em vez de módulo em `src/validation/` — decisão do grupo.**
A alternativa era `src/validation/fontes.py` com funções de contrato cobertas por pytest sobre amostras locais. Foi descartada por antecipação: o contrato que essas funções checariam só fica conhecido *depois* deste diagnóstico, e o consumidor real (os loaders da Bronze) ainda não existe. Escrever o validador agora significaria escrevê-lo duas vezes. A consequência aceita é que o resultado desta sprint é um registro em documento, não um teste automatizado — e que uma mudança futura no layout da fonte só aparece quando alguém rodar o script de novo. A Sprint 2 fecha essa lacuna.

**2. O script reaproveita a amostra em disco antes de baixar.**
Hoje `baixar_amostras.py` chama `requests.get` incondicionalmente e depois grava por cima do ZIP existente — 176 MB de download a cada execução. A mudança é uma checagem de existência do caminho antes da requisição, com uma opção explícita para forçar o download quando se quer conferir se a fonte mudou. Alternativa considerada: comparar `Content-Length` via `HEAD`. Descartada — resolve menos e adiciona um caminho de código a mais para o grupo explicar.

**3. O notebook lê o CSV por *chunks*, nunca inteiro.**
`pandas.read_csv` direto no membro do ZIP estouraria a memória de máquina de estudante. O notebook usa `zipfile.ZipFile.open` sobre o arquivo local e `read_csv(..., chunksize=...)`, acumulando só o que a pergunta exige: contagem de linhas, conjunto de modalidades distintas, e as primeiras linhas para inspeção visual do decimal. Alternativa: `nrows` pequeno. Insuficiente — a contagem de linhas do ano e o conjunto completo de modalidades exigem varrer o arquivo todo.

**4. Jupyter fica em `requirements-dev.txt`, não no `requirements.txt`.**
O `requirements.txt` é o contrato do que o *pipeline* precisa para rodar. Dois lugares o instalam sozinhos, sem ninguém pedir: o CI, a cada push e a cada PR, e o `Dockerfile`, que o copia na camada de dependências. Jupyter ali significa dezenas de pacotes (tornado, nbformat, nbconvert, jsonschema, pyzmq) baixados a cada push para rodar testes que não abrem notebook nenhum, e uma imagem maior pelo mesmo motivo. Instalar avulso, sem pin, foi descartado por juntar o pior dos dois lados: ninguém sabe qual versão está rodando, e isso contraria o Requisito 4 do enunciado, que é a razão de o `requirements.txt` ter versões fixadas. A saída é um segundo arquivo, também fixado, que começa com `-r requirements.txt` e acrescenta `jupyterlab` e `ipykernel` — quem vai mexer no notebook continua rodando **um** comando (`pip install -r requirements-dev.txt`), que traz o pipeline junto. CI e `Dockerfile` não mudam: seguem apontando só para o `requirements.txt`. Quem usa o notebook dentro do VS Code precisa apenas do `ipykernel`; o `jupyterlab` serve para abrir no navegador. Alternativa considerada: extra do `pyproject.toml` (`pip install .[dev]`). Descartada — o projeto não tem `pyproject.toml`, e introduzir empacotamento só para isso é mais uma coisa para todo mundo saber explicar.

**5. Unidade e decimal são conferidos por leitura direta do texto bruto, antes de qualquer `read_csv`.**
Se `carteira_ativa` usa vírgula decimal e o `read_csv` for feito sem `decimal=','`, o pandas devolve string ou número errado silenciosamente — e a conclusão sobre a unidade sairia errada. Por isso a inspeção das primeiras linhas cruas (`f.read(4000)`, como o script já faz) vem antes, e a leitura tipada usa o que ela revelou. A magnitude decide reais versus milhares: valor de carteira de um estado grande em uma modalidade fica na casa dos bilhões se estiver em reais.

**6. Docker mantido — decisão do grupo, fecha a ressalva 7.3.**
`Dockerfile` e `docker-compose.yml` permanecem versionados. A seção 7.3 passa de `[PREENCHER]` para a decisão registrada, e o README ganha a instrução de uso. Isso mantém o critério da própria seção 7.3: alguém do grupo precisa saber explicar o Dockerfile — se isso deixar de valer, a decisão é revisitada em sprint futura, não agora.

**7. A lista de encodings é ordenada do mais restritivo para o mais permissivo.**
Descoberto ao abrir a amostra: os CSVs vêm em UTF-8 com BOM, mas `SCR_ENCODINGS_CANDIDATOS` estava como `["latin-1", "utf-8"]` e a leitura adota o primeiro candidato que não levanta erro. `latin-1` mapeia todos os 256 bytes possíveis e portanto **nunca** levanta erro — vencia sempre, em qualquer arquivo, e devolvia `ComÃ©rcio` no lugar de `Comércio`. Não é cosmético: `modalidade` é texto acentuado e o recorte do projeto é `LIKE 'Financiamentos%'`, então o encoding errado quebraria o filtro central na Sprint 2. A correção é a ordem — `["utf-8-sig", "utf-8", "latin-1"]` — porque UTF-8 falha de verdade em arquivo latin-1 legítimo, o que torna a ordem significativa e devolve ao `latin-1` o papel de fallback de último recurso. Alternativas consideradas: detectar o BOM explicitamente antes dos candidatos (mais preciso, mas ainda precisaria da reordenação para o caso sem BOM, e acrescenta um caminho de código); e chumbar `utf-8-sig`, descartada porque os anos anteriores a 2024 podem vir diferentes e a lista é o que permite perceber isso.

## Risks / Trade-offs

- **A URL do SCR mudou ou o portal saiu do ar** → O ZIP de 2024 já está em disco, então o diagnóstico do layout acontece mesmo sem rede. Uma falha de download vira registro em `docs/architecture.md`, e o grupo reavalia o tema antes da Sprint 2 — que é exatamente o propósito desta sprint.
- **A licença do Ipeadata não está publicada de forma inequívoca** → Registrar o que está publicado, com a URL e a data em que foi consultada, em vez de afirmar uma licença que não se confirmou. Se não houver termo explícito, isso mesmo é a resposta e entra nas Limitações Conhecidas (seção 11).
- **A amostra é de 2024, e o recorte do projeto começa em jul/2016** → Os anos antigos podem ter layout diferente. O risco é assumido nesta sprint: 2024 confirma o formato corrente, e a Sprint 2, ao baixar a série toda, precisa conferir o cabeçalho de cada ano em vez de assumir o de 2024.
- **`ANO_FIM = 2025` pode estar desalinhado da última competência publicada** → O diagnóstico da Selic já imprime a última `VALDATA`; a do SCR sai do último `data_base` da amostra. Divergência corrige a constante e fica registrada.
- **A saída do notebook fica commitada e envelhece** → Aceito de propósito: a saída é a evidência da sprint. Ela carrega a data de coleta na própria célula, então quem ler depois sabe de quando é.

## Migration Plan

Não se aplica. Nenhum dado em produção, nenhum contrato consumido por terceiros, nenhum artefato a migrar. Reverter é `git revert` — os únicos efeitos fora do Git ficam em `data/raw/_amostras/`, que está no `.gitignore`.

## Open Questions

- O ano da amostra continua sendo 2024 ou passa a ser o ano corrente? Não muda specs, abordagem nem tarefas — é uma constante no script, ajustável quando a Sprint 2 baixar a série completa.
