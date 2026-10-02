# Guia de comandos

Todos os comandos do projeto em um lugar só. Rode sempre **a partir da raiz do projeto**
(a pasta `selic-scr-analysis/`), com o ambiente virtual ativado. O passo a passo explicado,
na ordem de uso, está no [README](../README.md#como-rodar-do-zero).

---

## Ambiente

```bash
# Criar o ambiente virtual (uma vez só) — Python 3.11, a versão do CI
python3.11 -m venv .venv          # Linux / macOS
py -3.11 -m venv .venv            # Windows

# Ativar (a cada terminal novo)
source .venv/bin/activate         # Linux / macOS
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
source .venv/Scripts/activate     # Windows (Git Bash)

# Instalar as dependências (versões fixadas)
pip install -r requirements.txt       # só o pipeline
pip install -r requirements-dev.txt   # pipeline + Jupyter (para os notebooks)
```

---

## Testes

Usam dados sintéticos em pastas temporárias, sem internet e sem banco — não mexem em `data/`.

```bash
pytest                                              # todos (1 a 2 minutos)
pytest -v                                           # mostrando o nome de cada teste
pytest tests/test_gold.py                           # um arquivo
pytest tests/test_config.py::test_existem_27_ufs -v # um teste
```

| Arquivo | O que testa |
|---|---|
| `test_config.py` | constantes do `config.py` (UFs, recorte, URLs) |
| `test_ingestion.py`, `test_metadata.py`, `test_controle.py` | ingestão Bronze, metadados e tabelas de controle |
| `test_idempotencia.py`, `test_no_duplicates.py` | rodar duas vezes não duplica; chave sem duplicata |
| `test_validation.py`, `test_transformation.py` | quarentena e Silver |
| `test_gold.py`, `test_analise.py` | Gold e correlações |
| `test_ml.py`, `test_decisao.py` | modelo e recomendação do trimestre |
| `test_publicacao.py` | envio ao Neon (com banco falso) |

---

## Pipeline

```bash
python scripts/run_pipeline.py              # completo: Bronze → Silver → Gold → análise → ML → decisão → publicação
python scripts/run_pipeline.py --anos 2024  # teste rápido com um só ano do SCR (ML e decisão são pulados)
python scripts/run_pipeline.py --anos 2024 2025   # escolhendo mais de um ano
```

- **1ª execução:** ~50 minutos (baixa ~1,5 GB do SCR).
- **Execuções seguintes:** poucos minutos — o que não mudou na fonte não é baixado nem regravado.
- **Publicação no Neon:** só acontece se existir o `.env` com `DATABASE_URL`; sem ele, é pulada.

---

## Conferências

```bash
python scripts/conferir_bronze.py                     # contagens da Bronze e duplicatas na chave (tem que ser 0)
python scripts/baixar_amostras.py                     # diagnóstico das fontes (encoding, colunas); não faz ingestão
python scripts/baixar_amostras.py --forcar-download   # idem, baixando a amostra de novo
```

**Demonstrar a idempotência** (as contagens têm que ser iguais antes e depois):

```bash
python scripts/conferir_bronze.py
python scripts/run_pipeline.py
python scripts/conferir_bronze.py
```

---

## Notebooks

```bash
pip install -r requirements-dev.txt   # uma vez só
jupyter lab                           # abre no navegador
```

| Notebook | Conteúdo |
|---|---|
| `notebooks/01_exploracao_amostras.ipynb` | conferência das fontes (precisa do `baixar_amostras.py` antes) |
| `notebooks/02_analise_estatistica.ipynb` | Selic × crédito, por modalidade e por estado |
| `notebooks/03_modelo.ipynb` | modelo, baselines, efeito da Selic e checklist anti-vazamento |

Os notebooks leem os arquivos de `data/final/`: rode o pipeline completo antes.

---

## Publicação e site (`web/`)

```bash
# Publicar só as tabelas finais no Neon, sem rodar o pipeline de novo
# (precisa do .env com DATABASE_URL na raiz)
python -c "from src.publicacao.neon import executar_publicacao; print(executar_publicacao())"
```

Site local (precisa do Node.js 20 ou mais novo):

```bash
cd web
cp .env.exemplo .env.local   # e cole a mesma DATABASE_URL do .env da raiz
npm install                  # uma vez só
npm run dev                  # modo desenvolvimento: http://localhost:3000
npm run build                # gera a versão de produção (confere se compila)
npm run start                # roda a versão gerada pelo build
```

Vercel pela linha de comando (opcional; precisa de `npx vercel login` antes):

```bash
cd web
npx vercel ls        # lista os deploys e o status de cada um
npx vercel env ls    # lista as variáveis cadastradas (sem mostrar os valores)
```

---

## Git (fluxo do projeto)

```bash
git switch develop && git pull                 # começar sempre do develop atualizado
git switch -c feat/minha-mudanca               # um branch por mudança
git add <arquivos> && git commit -m "✨ feat: descrição curta"
git push -u origin feat/minha-mudanca          # depois, abrir o PR para o develop no GitHub
```

Prefixos dos commits: `✨ feat:` (funcionalidade), `🐛 fix:` (correção), `📄 docs:` (documentação),
`✅ test:` (testes), `🔧 chore:` (manutenção).
