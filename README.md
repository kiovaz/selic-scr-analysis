# Impacto da Selic nos Financiamentos por Estado

Pipeline de dados que cruza o **saldo de financiamentos por estado e modalidade** (SCR.data / Banco Central) com a **Selic meta do Copom** (Ipeadata / Ipea), mede a associação entre os dois e treina um modelo que recomenda, a cada trimestre, **em quais estados e modalidades vale expandir a oferta de crédito**.

Projeto Integrador — Da Ingestão à Decisão. **Status:** Sprints 1 a 6 concluídas (pipeline, análise, modelo e decisão). A publicação da Gold na nuvem fica para depois.

---

## O que o projeto responde

> "Cruzando o **SCR.data (Banco Central)** e a **Selic meta do Copom (Ipeadata)**, identificamos que **o saldo do crédito imobiliário anda junto com a Selic de 4 meses antes (Spearman +0,42), mas a Selic não antecipa o trimestre seguinte — o que antecipa é o ritmo recente do próprio crédito em cada estado**. Recomendamos que **a diretoria de crédito de uma instituição financeira de atuação nacional** faça **a expansão da oferta de financiamento nas 20 combinações estado × modalidade com maior probabilidade de o crédito ganhar força** nos próximos **3 meses (set–nov/2026)**, priorizando **as de maior saldo dentro da lista**. Se agir, o ganho esperado é **acertar ~16,5 de 20 expansões por trimestre (82,5%), contra ~15,0 da regra simples e ~10,0 ao acaso**; se errarmos, o custo é **~3,5 expansões por trimestre em mercados que estão perdendo força — capital, captação e equipe comercial alocados sem retorno no trimestre**."

Os números acima são gerados pelo pipeline (`data/final/frase_fechamento.json`) e impressos no fim de `python scripts/run_pipeline.py`. Custos do erro, regra de decisão e sensibilidade: seção 10 do [`docs/architecture.md`](docs/architecture.md). Ressalvas: [Limitações](#limitações-conhecidas).

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

Precisa de **Python 3.11** (é a versão do CI) e de ~8 GB livres em disco. Os comandos abaixo rodam **a partir da raiz do projeto**.

### 1. Clonar o repositório

```bash
git clone https://github.com/kiovaz/selic-scr-analysis.git
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

- **A primeira execução leva ~50 minutos**: baixa 11 ZIPs do SCR (~1,5 GB, 2016 a 2026) e grava ~34 milhões de linhas na Bronze. Deixe o computador **na tomada e sem suspender** — se ele dormir, a execução fica parada até acordar.
- **As execuções seguintes levam poucos minutos**: o pipeline consulta a versão de cada ZIP no BCB sem baixar, vê que nada mudou e não regrava a Bronze (idempotência).
- **Teste rápido** com um só ano do SCR (um ZIP de ~170 MB, uns 5 minutos):

  ```bash
  python scripts/run_pipeline.py --anos 2024
  ```

  Com um ano só, a Silver e a Gold ficam curtas, a análise não tem meses suficientes e **o ML e a decisão são pulados** (o pipeline avisa) — serve para conferir que o ambiente funciona, não para ver os resultados. ⚠ Esse teste **sobrescreve os gráficos de `docs/figuras/`** com resultados de um ano só: não os commite; rode o pipeline completo (ou `git checkout -- docs/figuras`) antes.

### 6. Ver os resultados

| O quê | Onde |
|---|---|
| Recomendação do trimestre (20 para expandir, 20 em alerta) | `data/final/recomendacao_trimestre.parquet` |
| Números da frase de fechamento | `data/final/frase_fechamento.json` |
| Modelo (métricas, com e sem Selic, previsões) | `data/final/ml_resultados.json`, `ml_previsao_producao.parquet` |
| Análise estatística (tabelas) | `data/final/analise_*.parquet` |
| Gráficos | `docs/figuras/` (versionados no Git) |
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

### 7. Demonstrar a idempotência (defesa)

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

### 9. Docker (alternativa ao venv)

```bash
docker compose run --rm pipeline
```

A imagem instala só o `requirements.txt` (sem Jupyter). O caminho padrão continua sendo o venv.

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
│   └── ml/                   # base de ML, treino/avaliação e decisão
├── tests/                   # testes automatizados (pytest)
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

As decisões de cada sprint estão na seção 13 do `architecture.md` (Registro de decisões), e as propostas completas em `openspec/changes/archive/`.

**Pendências do grupo antes da entrega:**
1. **Commits distribuídos** (Requisito 4 do enunciado): o histórico precisa ter commits de todos os integrantes.
2. **Ensaio da defesa:** cada integrante explica um trecho sorteado do código.
3. **Revisar a declaração de uso de IA** abaixo e preencher a tabela de integrantes.
4. **Um integrante refaz o "Como rodar do zero"** na própria máquina, com Python 3.11.

---

## Uso de IA generativa

*(Requisito 9 do enunciado. **Rascunho a revisar e completar pelo grupo.**)*

| Ferramenta | Usada para | Em quais partes |
|---|---|---|
| Claude Code (Anthropic) | Revisar a ingestão da Sprint 2 e propor correções; escrever código e testes a partir das especificações OpenSpec decididas pelo grupo; investigar os dados (perfil da Bronze, efeito dos dias úteis na Selic, balanço do rótulo do ML); redigir a documentação | `src/` (ingestion, validation, transformation, analise, ml), `tests/`, `scripts/`, `notebooks/02` e `03`, `docs/`, `openspec/` — Sprints 2 a 6 |

As decisões de escopo (pergunta de pesquisa, recorte, tratamento da quantidade, troca da série da Selic, pergunta do modelo, decisor e limiar) foram tomadas pelo grupo e estão registradas na seção 13 do `architecture.md`.

Todo integrante do grupo é capaz de explicar qualquer trecho do que foi entregue.

---

## Limitações conhecidas

1. O SCR.data traz o **saldo** da carteira no fim do mês, não os financiamentos novos. A variação mensal é uma aproximação de fluxo.
2. O estado vem do CEP de residência (PF) ou da sede (PJ), não de onde o dinheiro é usado.
3. Valores em reais nominais, sem correção pela inflação.
4. A Selic é nacional — não existe taxa por estado.
5. **Associação não é causa:** renda, emprego, safra e política de crédito dos bancos não são controlados.
6. A **quantidade de operações é subestimada** (o BCB esconde 28% das linhas); a análise e o modelo usam o **volume**.
7. **A Selic não antecipa o trimestre seguinte:** o modelo com e sem Selic tem desempenho equivalente.
8. As probabilidades mais extremas do modelo aparecem em **mercados pequenos**; por isso a recomendação prioriza, dentro da lista, as de maior saldo.
9. A avaliação final cobre 12 meses (fev/2025–jan/2026), um só regime de juros altos.

Lista completa e o que seria preciso para afirmar mais: `docs/architecture.md`, seção 11.
