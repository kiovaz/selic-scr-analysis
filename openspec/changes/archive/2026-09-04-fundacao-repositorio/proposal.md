## Why

O projeto está na Sprint 1, cujo objetivo (seção 8 do `docs/architecture.md`) é **garantir que o tema é viável antes de investir em código**. A estrutura do repositório já existe, mas as duas fontes públicas ainda não foram conferidas de verdade: `docs/architecture.md` carrega quatro campos `[PREENCHER]` (licença do Ipeadata, as duas datas de coleta e a decisão sobre Docker) e nenhum registro sobre encoding real, separador decimal ou unidade de `carteira_ativa`. Sem essas respostas, a Sprint 2 escreveria os loaders da Bronze em cima de suposições — que é exatamente o modo como um projeto morre no segundo encontro, com a base "que existia" atrás de login, com 40 GB ou parada de ser atualizada.

## What Changes

- **Diagnóstico das duas fontes**: `scripts/baixar_amostras.py` passa a ser executado de verdade contra o SCR.data e o Ipeadata, e o resultado é registrado. Hoje o ZIP de 2024 já está em `data/raw/_amostras/` (176 MB), o que prova o download, mas nada disso está documentado.
- **`notebooks/01_exploracao_amostras.ipynb`** (pasta existe, está vazia): abre a amostra já baixada e responde, com célula executada e saída visível, as perguntas da definição de pronto da Sprint 1 — encoding, separador, decimal vírgula ou ponto, `carteira_ativa` em reais ou milhares, contagem de linhas de um ano, presença das 5 colunas de `SCR_COLUNAS_USADAS`, presença das 8 modalidades `Financiamentos%`, e os campos `SERCODIGO`/`VALDATA`/`VALVALOR` da Selic com a última competência publicada.
- **`docs/architecture.md`**: os quatro `[PREENCHER]` respondidos — licença/termos do Ipeadata (2.2), data de coleta do SCR (2.1), data de coleta da Selic (2.2) e a decisão sobre Docker em 7.3, que o grupo fecha como **manter**.
- **`docs/data_dictionary.md`**: registra a unidade e o formato numérico confirmados de `carteira_ativa` e `numero_de_operacoes`, e a nota de proveniência da Selic (Ipeadata redistribui série do BCB).
- **`src/config.py`**: se e somente se o diagnóstico contradisser uma constante — encoding fora de `SCR_ENCODINGS_CANDIDATOS`, nome de coluna diferente do esperado ou `ANO_FIM` desalinhado da última competência — a constante é corrigida. Nenhuma constante nova.
- **Não muda**: nenhum código novo em `src/ingestion/`, `src/transformation/` ou `src/validation/`; nenhum teste novo. O grupo decidiu que a validação das fontes nesta sprint é manual (script + notebook + registro nos docs), não um módulo reutilizável — isso fica para a Sprint 2, quando os loaders existirem.

## Capabilities

### New Capabilities
- `diagnostico-fontes`: o repositório precisa conseguir verificar, sob demanda e sem autenticação, que o SCR.data e a Selic do Ipeadata estão acessíveis e no formato que o pipeline assume, e reportar cada divergência como resultado legível em vez de quebrar. Cobre o contrato observável de `scripts/baixar_amostras.py` e o registro obrigatório das respostas nos documentos do projeto.

### Modified Capabilities
Nenhuma. `openspec/specs/` está vazio — este é o primeiro spec do projeto.

## Impact

- **Arquivos tocados**: `notebooks/01_exploracao_amostras.ipynb` (novo), `requirements-dev.txt` (novo), `scripts/baixar_amostras.py` (ajustes de diagnóstico), `docs/architecture.md` (seções 2.1, 2.2, 7.3), `docs/data_dictionary.md`, `README.md` (instrução do Docker), e `src/config.py` apenas se o diagnóstico contradisser uma constante.
- **Dados**: `data/raw/_amostras/` já tem `scrdata_2024.zip`. A pasta está sob `.gitignore` — nada de dado vai para o Git; o notebook lê o ZIP local em vez de rebaixar 176 MB.
- **CI**: sem alteração. O `pytest -v` do `.github/workflows/ci.yml` continua offline; nenhum teste desta sprint acessa a rede.
- **Dependências**: `jupyterlab` e `ipykernel` entram em `requirements-dev.txt` com versões fixadas, que começa com `-r requirements.txt`. Não entram no `requirements.txt`: o CI o instala a cada push e o `Dockerfile` o copia na camada de dependências, e nenhum teste usa Jupyter. Nenhuma dependência nova do pipeline.
- **Bloqueia**: a Sprint 2 (ingestão Bronze) não começa antes que os `[PREENCHER]` estejam respondidos, porque os loaders dependem de encoding, separador decimal e unidade confirmados.
- **Risco**: se o download do SCR falhar ou o layout tiver mudado, isso é resultado da sprint, não erro — dispara reavaliação do tema antes de escrever o pipeline.
