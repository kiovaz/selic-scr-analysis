# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Idioma

Código, comentários, docstrings, documentação e mensagens de commit são em **português (pt-BR)**. Nomes de variáveis, funções e colunas também (`criar_pastas`, `volume_rs`, `ano_mes`). Mantenha esse padrão em qualquer coisa nova.

## Comandos

```bash
source .venv/bin/activate          # ambiente já criado em .venv/ (Python 3.11)
pip install -r requirements.txt    # versões fixadas — não usar range

pytest                             # todos os testes (testpaths = tests)
pytest tests/test_config.py        # um arquivo
pytest tests/test_config.py::test_existem_27_ufs -v   # um teste

python scripts/baixar_amostras.py  # baixa amostra real das duas fontes e imprime diagnóstico (NÃO faz ingestão; o ZIP do SCR tem ~176 MB)
python scripts/run_pipeline.py     # pipeline ponta a ponta; cada sprint acrescenta uma etapa aqui

docker compose run --rm pipeline   # opcional (ver ressalva 7.3 do architecture.md)
```

CI (`.github/workflows/ci.yml`) roda `pytest -v` em todo push e PR para `main`, com Python 3.11.

Scripts em `scripts/` fazem `sys.path.insert(0, raiz)` antes de `from src import config` — é assim que eles enxergam o pacote. Rode-os sempre a partir da raiz do projeto.

## A especificação manda no código

`docs/architecture.md` é a fonte de verdade. **Toda decisão de implementação precisa ser rastreável a uma seção dele**, e mudança de escopo entra lá primeiro, no código depois. Antes de implementar qualquer coisa não trivial, leia a seção correspondente. `docs/data_dictionary.md` é a versão consolidada da seção 5 e precisa ser atualizado junto com as camadas Silver/Gold.

O projeto usa OpenSpec (`openspec/`, skills `openspec-*` / `opsx:*`) para propor e aplicar mudanças. Os workflows de proposta criam **apenas artefatos de planejamento** — não editam código.

## Arquitetura

Pipeline medallion sobre filesystem local (sem cloud, sem DVC — decisão consciente; `data/` está no `.gitignore`).

```
SCR.data (BCB, ZIP→CSV ';')  ─┐
                              ├─→ Bronze data/raw/ → Silver data/processed/ → Gold data/final/
Selic (Ipeadata, API OData)  ─┘        (cru)            (limpo, tipado)         (pronto p/ pergunta)
```

Módulos de `src/` (`ingestion/`, `transformation/`, `validation/`, `ml/`, `utils/`) hoje são pacotes vazios — o projeto está na **Sprint 1** e é construído sprint a sprint (plano na seção 8 do architecture.md). Os nomes de arquivo esperados em cada um estão na seção 9.

### `src/config.py` é o único lugar com caminho, URL e constante

Nenhum outro arquivo pode ter caminho ou URL chumbado. Constantes que importam: `DIR_BRONZE/SILVER/GOLD/QUARENTENA`, `SCR_URL_TEMPLATE`, `SELIC_URL`, `SCR_COLUNAS_USADAS` (só 5 colunas viram Silver), `UFS_VALIDAS` (27), `ANO_INICIO/MES_INICIO` e `PREFIXO_MODALIDADE`.

### Regras de domínio que não podem ser violadas

- **Vocabulário:** o projeto usa `modalidade` (tipo da operação de crédito). `segmento` no SCR.data é o tipo da instituição e **não** é usado — nunca escreva "segmento" para se referir a tipo de financiamento.
- **Recorte:** julho/2016 em diante. Antes disso o limite de registro do SCR era R$ 1.000 em vez de R$ 200 — quebra de série, dados não comparáveis.
- **Filtro:** só as 8 modalidades `LIKE 'Financiamentos%'`.
- **Chave de cruzamento:** `ano_mes`. A Selic é nacional, então o mesmo valor se repete para as 27 UFs no mês — isso é esperado, não é erro de join. Órfãos dos dois lados devem ser contados e reportados.
- **Unidade da Selic:** `BM12_TJOVER12` é **% ao mês**, não ao ano.
- **Granularidade:** Silver e Gold são uma linha por `(ano_mes, uf, modalidade)`; a ausência de duplicata na chave é provada por teste.

### Camadas

- **Bronze:** dado como veio, imutável, **nunca descarta registro**. Toda linha carrega os metadados técnicos com prefixo `_` (`_ingestion_timestamp`, `_ingestion_date`, `_source_system`, `_source_object`, `_load_id`, `_ingestion_mode`, `_record_hash`).
- **Silver:** tipagem forte, deduplicação, validações. Registro inválido vai para a **quarentena** (`data/raw/_quarentena`) com motivo padronizado (`uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`, `duplicata_na_chave`) — o job nunca quebra por dado sujo.
- **Gold:** só agregação e indicadores. Se precisou limpar na Gold, a Silver falhou.
- Reprocessamento sempre parte da Bronze; Silver e Gold são reconstruídas sem consultar a fonte de novo.

### Idempotência

`_record_hash` = SHA-256 do conteúdo do registro **concatenado com `_source_object`**. Incluir o arquivo de origem é intencional: preserva linhas idênticas vindas de arquivos diferentes e faz com que só o reprocessamento do *mesmo* arquivo seja descartado. Rodar a ingestão duas vezes seguidas não pode mudar a contagem de linhas.

A Selic usa **carga incremental por watermark** (última data ingerida em tabela de controle); o SCR é carga por arquivo.

### Derivadas e ML

Variações e lags (`var_qtd_pct`, `var_volume_pct`, `var_selic_pp`, `selic_lag_1..6`) são calculados **separadamente por UF × modalidade**, ordenados por mês; os primeiros meses ficam nulos e não são preenchidos artificialmente. A análise compara **variações, nunca níveis** (correlação espúria).

Para ML (Sprint 5): `t0` é o último mês **publicado** do SCR (há ~30 dias de defasagem), split **temporal**, e o checklist anti-vazamento da seção 6.3 vale item a item. A definição do problema ainda está aberta — preencher a tabela 6.1 do architecture.md **antes** de escrever código de treino.

## Convenções de contribuição

- `main` estável; branch de feature por membro; merge via Pull Request.
- Commits atômicos no formato `tipo: descrição breve` (`feat:`, `fix:`, `docs:`, `test:`); o histórico atual usa emoji antes do tipo (`✨ feat:`, `📄 docs:`, `🔧 chore:`).
- Validações de qualidade são funções simples em `src/validation/` cobertas por pytest — Great Expectations/Pandera foram deliberadamente descartados (seção 7.2).

## Regras deste projeto

- Todo integrante do grupo precisa saber explicar qualquer trecho entregue.
  Código simples, comentado em português, explicando a regra de negócio.
- Siga o fluxo do OpenSpec: proposal → specs → design → tasks. Não pule.
- Nenhum dado vai para o Git. A pasta data/ está no .gitignore.
- O SCR.data traz saldo de carteira, não concessão. Nunca escreva
  "financiamentos concedidos" como se fosse fluxo.
- Sempre rode o pytest depois de mexer em código.