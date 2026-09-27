## 1. Documentação

- [x] 1.1 `docs/architecture.md`: seção 0 (onde os dados vivem: local + publicação no Neon), 7.1 (Neon, psycopg, python-dotenv, Next.js), 7.2 (tirar o `python-dotenv` do que sai), 9 (`src/publicacao/` e `web/`), 13 (decisão 12 implementada; decisão 16 com os detalhes).
- [x] 1.2 `docs/data_dictionary.md`: tabelas publicadas no Neon.

## 2. Publicação no pipeline

- [x] 2.1 `requirements.txt`: `psycopg[binary]` e `python-dotenv` com versão fixada; `.gitignore` com `.env` e as pastas geradas do front.
- [x] 2.2 `config.py`: nome da variável `DATABASE_URL`, caminho do `.env`, lista das tabelas publicadas e arquivos de origem.
- [x] 2.3 `src/publicacao/neon.py`: `executar_publicacao()` — pula sem `DATABASE_URL`; confere as saídas; recria as tabelas e grava `publicacao_controle` numa transação.
- [x] 2.4 Etapa no `run_pipeline.py`.
- [x] 2.5 `tests/test_publicacao.py`: pula sem conexão; saída faltando; tipos das colunas; `NaN` vira `NULL`; tudo numa transação (conexão falsa).
- [x] 2.6 Publicar os dados reais no Neon e conferir as contagens.

## 3. Site (`web/`)

- [x] 3.1 Projeto Next.js em `web/` com `@neondatabase/serverless` e `recharts`; `.env.exemplo`.
- [x] 3.2 Página Recomendação.
- [x] 3.3 Página Selic × crédito.
- [x] 3.4 Página Explorar (estado e modalidade).
- [x] 3.5 `npm run build` conectado ao Neon.

## 4. Entrega

- [x] 4.1 README (publicação: `.env`, deploy na Vercel com Root Directory `web`) e `CLAUDE.md`.
- [x] 4.2 `pytest`, `openspec validate --strict`, commits atômicos em pt-BR sem linha de atribuição, PR para o `develop`.
