# Impacto da Selic nos Financiamentos por Estado

Pipeline de dados que cruza o saldo de financiamentos por estado (SCR.data / Banco Central) com a taxa Selic (Ipeadata / Ipea) para responder se — e quanto — variações nos juros estão associadas ao crédito em cada UF e modalidade.

Projeto Integrador — Da Ingestão à Decisão.

**Status:** Sprint 1 (fundação)

---

## Integrantes

| Nome | Responsável por |
|---|---|
| *(preencher)* | ingestão SCR.data |
| *(preencher)* | ingestão Selic |
| *(preencher)* | camadas Silver e Gold |
| *(preencher)* | análise estatística e ML |
| *(preencher)* | documentação e testes |

---

## Como rodar do zero

Testado em Linux, macOS e Windows com Python 3.11.

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd projeto-selic-credito
```

### 2. Criar o ambiente virtual

Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 4. Baixar as amostras e conferir as fontes

```bash
python scripts/baixar_amostras.py
```

Esse script baixa um ano do SCR.data e a série da Selic, e imprime um diagnóstico: encoding do arquivo, nomes das colunas, número de linhas e as primeiras linhas de dados. Ele **não** faz ingestão — serve para confirmar que as fontes ainda existem e estão no formato esperado antes de escrevermos o pipeline.

O ZIP do SCR tem ~168 MiB. Se a amostra já estiver em `data/raw/_amostras/`, o script **reaproveita o arquivo** em vez de rebaixar. Para conferir se a fonte mudou:

```bash
python scripts/baixar_amostras.py --forcar-download
```

### 5. Abrir o notebook de exploração (opcional)

O Jupyter não está no `requirements.txt` — o CI e o Docker instalam só aquele arquivo, e nenhum teste usa notebook. As ferramentas de exploração ficam em `requirements-dev.txt`, que já traz o `requirements.txt` junto:

```bash
pip install -r requirements-dev.txt
jupyter lab notebooks/01_exploracao_amostras.ipynb
```

No VS Code, o `ipykernel` sozinho basta — o `jupyterlab` só é preciso para abrir no navegador.

### 6. Rodar os testes

```bash
pytest
```

### 7. Rodar pelo Docker (alternativa ao venv)

O grupo decidiu manter o Docker (seção 7.3 do `architecture.md`). Ele padroniza o ambiente entre as máquinas, mas **não** é o caminho padrão — os passos 2 a 6 acima continuam sendo a forma normal de rodar.

```bash
docker compose run --rm pipeline
```

A imagem instala apenas o `requirements.txt`; o Jupyter fica de fora dela de propósito.

---

## Estrutura do repositório

```
├── data/                    # dados, fora do Git
│   ├── raw/                  # camada Bronze (dado cru)
│   ├── processed/            # camada Silver (dado limpo)
│   └── final/                # camada Gold (pronto para a pergunta)
├── docs/
│   ├── architecture.md       # especificação do projeto — leia antes de codar
│   └── data_dictionary.md    # dicionário de dados
├── notebooks/               # exploração e análise
│   └── 01_exploracao_amostras.ipynb   # Sprint 1: conferência das fontes
├── scripts/                 # scripts executáveis
├── src/
│   ├── config.py             # caminhos, URLs e constantes
│   ├── ingestion/            # leitura das fontes
│   ├── transformation/       # Bronze → Silver → Gold
│   ├── validation/           # checagens de qualidade
│   └── ml/                   # modelo (Sprint 5)
├── tests/                   # testes automatizados
├── requirements.txt         # dependências do pipeline (CI e Docker instalam esta)
└── requirements-dev.txt     # + ferramentas de exploração (Jupyter)
```

`docs/architecture.md` é a fonte de verdade do projeto. Mudança de escopo entra lá primeiro, no código depois.

---

## Fontes de dados

| Base | Instituição | Acesso | Formato | Licença |
|---|---|---|---|---|
| [SCR.data](https://dadosabertos.bcb.gov.br/dataset/scr_data) | Banco Central do Brasil | arquivo | ZIP → CSV (`;`) | Open Data Commons ODbL |
| [Selic — série BM12_TJOVER12](http://www.ipeadata.gov.br/) | Ipea (Ipeadata) | API REST | JSON (OData v4) | sem termo único publicado; uso educacional com citação obrigatória da fonte ([detalhes](docs/architecture.md)) |

**Data de coleta:** *(a preencher — Sprint 1)*

**Chave de cruzamento:** `ano_mes`.

**Recorte temporal:** julho/2016 em diante. Antes disso o SCR usava outro limite de registro (R$ 1.000 em vez de R$ 200), o que torna as séries não comparáveis.

---

## Sprints

- [ ] **Sprint 1 — Fundação.** Perguntas fechadas, repositório montado, amostras baixadas e conferidas.
- [ ] **Sprint 2 — Ingestão Bronze.** Loaders de arquivo e API, metadados técnicos, quarentena.
- [ ] **Sprint 3 — Idempotência e CI.** Hash, carga incremental, testes, GitHub Actions.
- [ ] **Sprint 4 — Silver e Gold.** Tipagem, join, variações, lags, análise estatística.
- [ ] **Sprint 5 — ML.** Definir o problema, construir a base, baseline, modelo, anti-vazamento.
- [ ] **Sprint 6 — Decisão e entrega.** Limiar, frase final, README completo, ensaio da defesa.

---

## Uso de IA generativa

*(Obrigatório declarar — Requisito 9 do enunciado. Preencher ao longo do projeto: qual ferramenta, para quê e em que partes.)*

| Ferramenta | Usada para | Em quais arquivos |
|---|---|---|
| | | |

Todo integrante do grupo é capaz de explicar qualquer trecho do que foi entregue.

---

## Limitações conhecidas

1. O SCR.data traz o **saldo** da carteira no fim do mês, não os financiamentos novos do mês. A variação mensal é uma aproximação de fluxo.
2. O estado vem do CEP de residência (PF) ou da sede (PJ), não de onde o dinheiro é usado.
3. Valores em reais nominais, sem correção pela inflação.
4. A Selic é nacional — não existe taxa por estado.
5. Associação não é causa: renda, emprego e política de crédito dos bancos não são controlados.

Lista completa em `docs/architecture.md`, seção 11.
