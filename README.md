# 📈 Impacto da Selic nos Financiamentos por Estado

<p align="left">
  <img src="https://img.shields.io/badge/Institui%C3%A7%C3%A3o-CESUPA-blue?style=for-the-badge" alt="CESUPA" />
  <img src="https://img.shields.io/badge/Turma-EC6MA-orange?style=for-the-badge" alt="Turma EC6MA" />
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/Status-Conclu%C3%ADdo-brightgreen?style=for-the-badge" alt="Status" />
</p>

Pipeline de dados de **Ciência de Dados** que cruza o **saldo de financiamentos por estado e modalidade** (SCR.data / Banco Central) com a **Selic meta do Copom** (Ipeadata / Ipea), mede a associação entre os dois e treina um modelo de Machine Learning que recomenda, a cada trimestre, **em quais estados e modalidades vale expandir a oferta de crédito**.

---

## 👥 Integrantes e Informações Acadêmicas

- **Instituição:** CESUPA (Centro Universitário do Estado do Pará)
- **Turma:** EC6MA
- **Disciplina:** Ciência de Dados

### Autores
- **Caio Vasconcelos**
- **Yasmin dos Santos**
- **Ana Alice Dias**

---

## 📌 Sumário
- [O que o projeto responde](#-o-que-o-projeto-responde)
- [Como rodar do zero](#-como-rodar-do-zero)
- [Estrutura do repositório](#-estrutura-do-reposit%C3%B3rio)
- [Fontes de dados](#-fontes-de-dados)
- [Sprints e Histórico](#-sprints)

---

## 🎯 O que o projeto responde

> "Cruzando o **SCR.data (Banco Central)** e a **Selic meta do Copom (Ipeadata)**, identificamos que **o saldo do crédito imobiliário anda junto com a Selic de 4 meses antes (Spearman +0,42), mas a Selic não antecipa o trimestre seguinte — o que antecipa é o ritmo recente do próprio crédito em cada estado**. Recomendamos que **a diretoria de crédito de uma instituição financeira de atuação nacional** faça **a expansão da oferta de financiamento nas 20 combinações estado × modalidade com maior probabilidade de o crédito ganhar força** nos próximos **3 meses (set–nov/2026)**, priorizando **as de maior saldo dentro da lista**. Se agir, o ganho esperado é **acertar ~16,5 de 20 expansões por trimestre (82,5%), contra ~15,0 da regra simples e ~10,0 ao acaso**; se errarmos, o custo é **~3,5 expansões por trimestre em mercados que estão perdendo força — capital, captação e equipe comercial alocados sem retorno no trimestre**."

Os números acima são gerados pelo pipeline (`data/final/frase_fechamento.json`) e impressos no fim de `python scripts/run_pipeline.py`. Custos do erro, regra de decisão e sensibilidade: seção 10 do [`docs/architecture.md`](docs/architecture.md). Ressalvas: [Limitações](docs/data_dictionary.md#limitações-conhecidas).

---

## 💻 Como rodar do zero

Precisa de **Python 3.11** (versão do CI) e de ~8 GB livres em disco. Os comandos abaixo rodam **a partir da raiz do projeto**.

### 1. Clonar o repositório

```bash
git clone [https://github.com/kiovaz/selic-scr-analysis.git](https://github.com/kiovaz/selic-scr-analysis.git)
cd selic-scr-analysis
```

### 2. Criar e ativar o ambiente virtual

Linux / macOS:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 4. Rodar os testes (1 a 2 minutos, sem internet)

```bash
pytest
```

Os testes usam dados sintéticos em pastas temporárias e bloqueiam a rede: não baixam nada nem mexem em `data/`.

### 5. Rodar o pipeline completo

```bash
python scripts/run_pipeline.py
```

O pipeline faz, em ordem: ingestão Bronze (SCR e Selic) → Silver → Gold → análise estatística → modelo de ML → decisão. No fim, imprime a frase de fechamento com os números e a lista do trimestre.

- **A primeira execução leva ~50 minutos**: baixa 11 ZIPs do SCR (~1,5 GB, 2016 a 2026) e grava ~34 milhões de linhas na Bronze.
- **As execuções seguintes levam poucos minutos**: o pipeline consulta a versão de cada ZIP no BCB sem baixar, vê que nada mudou e não regrava a Bronze (idempotência).
- **Teste rápido** com um só ano do SCR (um ZIP de ~170 MB, uns 5 minutos):

  ```bash
  python scripts/run_pipeline.py --anos 2024
  ```

  Com um ano só, a Silver e a Gold ficam curtas, a análise não tem meses suficientes e **o ML e a decisão são pulados** (o pipeline avisa) — serve para conferir que o ambiente funciona, não para ver os resultados.

### 6. Ver os resultados

| O quê | Onde |
|---|---|
| Recomendação do trimestre (20 para expandir, 20 em alerta) | `data/final/recomendacao_trimestre.parquet` |
| Números da frase de fechamento | `data/final/frase_fechamento.json` |
| Modelo (métricas, com e sem Selic, previsões) | `data/final/ml_resultados.json`, `ml_previsao_producao.parquet` |
| Análise estatística (tabelas) | `data/final/analise_*.parquet` |
| Gráficos | `docs/figuras/` |
| Relatórios das camadas | `data/processed/_relatorio_silver.json`, `data/final/_relatorio_gold.json` |

Os **notebooks** explicam cada etapa lendo esses arquivos (não recalculam nada). O Jupyter fica em `requirements-dev.txt`, que já inclui o `requirements.txt`:

```bash
pip install -r requirements-dev.txt
jupyter lab
```

| Notebook | Conteúdo |
|---|---|
| `notebooks/01_exploracao_amostras.ipynb` | Sprint 1: conferência das fontes (usa a amostra de `scripts/baixar_amostras.py`) |
| `notebooks/02_analise_estatistica.ipynb` | Sprint 4: Selic × crédito, por modalidade e por estado |
| `notebooks/03_modelo.ipynb` | Sprint 5: o modelo, os baselines, o efeito da Selic e o checklist anti-vazamento |

### 7. Demonstrar a idempotência

Rodar a ingestão de novo não pode mudar a contagem de linhas (seção 3.2 do `architecture.md`):

```bash
python scripts/conferir_bronze.py   # 1. anota as contagens e as duplicatas na chave (tem que ser 0)
python scripts/run_pipeline.py      # 2. roda tudo de novo
python scripts/conferir_bronze.py   # 3. as contagens são as mesmas, ainda com 0 duplicatas
```

As tabelas de controle que tornam isso possível ficam em `data/raw/_controle/`.

### 8. Conferir as fontes (opcional)

```bash
python scripts/baixar_amostras.py
```

Baixa uma amostra de 2024 do SCR e a série da Selic e imprime um diagnóstico (encoding, colunas, contagens). Não faz ingestão. Se a amostra já estiver em `data/raw/_amostras/`, reaproveita; `--forcar-download` baixa de novo.

### 9. Publicar no Neon e no site (opcional)

O pipeline pode enviar as tabelas finais para um banco Postgres no [Neon](https://neon.tech), e o site em `web/` (Next.js) mostra a recomendação, a Selic × crédito e a exploração por estado e modalidade.

1. Crie um arquivo `.env` na raiz (ele está no `.gitignore` e nunca vai para o Git) com a string de conexão do Neon:

   ```
   DATABASE_URL=postgresql://USUARIO:SENHA@HOST/BANCO?sslmode=require
   ```

2. Rode o pipeline: no fim, a etapa **Publicação no Neon** recria as tabelas e mostra quantas linhas enviou. Sem o `.env`, ela é pulada e o resto funciona igual.

3. Site local (precisa do [Node.js](https://nodejs.org) 20 ou mais novo):

   ```bash
   cd web
   cp .env.exemplo .env.local   # e cole a mesma DATABASE_URL
   npm install
   npm run dev                  # abre em http://localhost:3000
   ```

4. Na Vercel: importe o repositório, defina **Root Directory = `web`** e cadastre `DATABASE_URL` em *Settings → Environment Variables*. O site lê o banco só no servidor e se atualiza sozinho a cada hora depois de uma nova publicação.

---

## Estrutura do repositório

```
├── data/                    # dados, FORA do Git
│   ├── raw/                  # Bronze (dado como veio) + _controle, _downloads, _quarentena
│   ├── processed/            # Silver (limpo, tipado)
│   └── final/                # Gold, análise, ML e decisão
├── docs/
│   ├── architecture.md       # especificação e decisões do projeto (fonte de verdade)
│   ├── data_dictionary.md    # dicionário de dados de todas as tabelas
│   └── figuras/              # gráficos da análise
├── notebooks/               # 01 fontes · 02 análise · 03 modelo
├── openspec/                # propostas e specs de cada mudança (histórico por sprint)
├── scripts/
│   ├── run_pipeline.py       # pipeline completo (--anos para um teste rápido)
│   ├── conferir_bronze.py    # conferência da Bronze (demonstração de idempotência)
│   └── baixar_amostras.py    # diagnóstico das fontes (Sprint 1)
├── src/
│   ├── config.py             # todos os caminhos, URLs e constantes
│   ├── ingestion/            # loaders do SCR e da Selic, tabelas de controle, metadados
│   ├── validation/           # checagens de qualidade e quarentena
│   ├── transformation/       # Silver (SCR, Selic) e Gold
│   ├── analise/              # correlações e gráficos
│   ├── ml/                   # base de ML, treino/avaliação e decisão
│   └── publicacao/           # envio opcional das tabelas finais ao Neon
├── tests/                   # testes automatizados (pytest)
├── web/                     # site Next.js (Vercel) que lê o Neon
├── requirements.txt         # dependências do pipeline, versões fixadas
└── requirements-dev.txt     # + Jupyter
```

---

## Fontes de dados

| Base | Instituição | Acesso | Formato | Licença | Coleta |
|---|---|---|---|---|---|
| [SCR.data](https://dadosabertos.bcb.gov.br/dataset/scr_data) | Banco Central do Brasil | arquivo (ZIP anual) | CSV `;`, decimal `,`, UTF-8 com BOM | Open Data Commons ODbL | 2026-09-03 (amostra) e 2026-09-26 (carga completa) |
| [Selic meta do Copom — `BM366_TJOVER366`](http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='BM366_TJOVER366')) | Ipea (Ipeadata) | API REST (OData v4) | JSON | sem termo único publicado; uso educacional permitido, **citação obrigatória** ([detalhes](docs/architecture.md)) | 2026-09-27 |

- **Chave de cruzamento:** `ano_mes` (primeiro dia do mês). A Selic é nacional: o mesmo valor vale para as 27 UFs do mês. Órfãos dos dois lados: 0 (seção 2.4).
- **Recorte:** jul/2016 a jun/2026 (120 meses). Antes de jul/2016 o SCR usava outro limite de registro (R$ 1.000, não R$ 200).
- **Por que a Selic meta, e não a acumulada no mês:** a série acumulada (`BM12_TJOVER12`) varia com o número de dias úteis e chegou a subir quando o Copom cortou (seção 2.2).
- **A API do Ipeadata não pagina:** devolve a série inteira numa resposta (`$top`/`$skip` são ignorados). A ingestão usa timeout, retry com backoff e carga incremental por watermark.

---

## Sprints

- [x] **Sprint 1 — Fundação.** Pergunta, repositório, amostras conferidas.
- [x] **Sprint 2 — Ingestão Bronze.** Loaders de arquivo e API, metadados técnicos; Bronze guarda o dado como veio.
- [x] **Sprint 3 — Idempotência e CI.** Versão de cada ZIP/CSV, watermark da Selic, testes de duplicata, GitHub Actions.
- [x] **Sprint 4 — Silver, Gold e análise.** Quarentena, join, variações, lags, correlações por modalidade e por estado.
- [x] **Sprint 5 — ML.** "O crédito vai ganhar força?", baseline, janela móvel, com e sem Selic, checklist anti-vazamento.
- [x] **Sprint 6 — Decisão e entrega.** Decisor, limiar (20 maiores notas), frase de fechamento, README.
- [x] **Publicação.** Tabelas finais no Neon e site em Next.js na Vercel.

As decisões de cada sprint estão na seção 13 do `architecture.md` (Registro de decisões), e as propostas completas em `openspec/changes/archive/`.

