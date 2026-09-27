## Why

A decisão 12 do `architecture.md` aprovou publicar a Gold num banco **NeonDB** (Postgres na nuvem) com um **site em Next.js na Vercel**, para mostrar os resultados na entrega sem que a banca precise rodar o pipeline. Hoje tudo termina em `data/final/`, visível só em quem rodou o projeto.

## What Changes

- **Nova etapa opcional no pipeline — publicação:** depois da decisão, envia para o Neon as tabelas prontas da Gold, da análise e da decisão. Só roda se a string de conexão `DATABASE_URL` estiver configurada (arquivo `.env` na raiz, fora do Git); sem ela, o pipeline avisa e segue.
- **Tabelas publicadas** (substituídas por inteiro a cada execução, numa única transação): `gold_credito_selic`, `recomendacao_trimestre`, `ml_previsao_producao`, `sensibilidade_limiar`, `analise_brasil_modalidade`, `analise_uf_modalidade`, `frase_fechamento` e `publicacao_controle` (quando e quanto foi publicado).
- **Site em `web/`** (Next.js), só leitura, com três páginas:
  - **Recomendação:** a frase de fechamento, os números do modelo e as listas "expandir" e "alerta" do trimestre;
  - **Selic × crédito:** a Selic ao longo do tempo, o saldo por modalidade e a associação medida na análise;
  - **Explorar:** escolher estado e modalidade e ver o saldo mês a mês e a probabilidade prevista para o trimestre.
- **Dependências novas:** `psycopg[binary]` (conexão com o Postgres) e `python-dotenv` (ler o `.env`). O `python-dotenv` saía na seção 7.2 porque nenhuma fonte exigia credencial; agora o banco exige.
- **`.gitignore`:** `.env` e as pastas geradas do front.

## Capabilities

### New Capabilities
- `publicacao-gold`: envio opcional e idempotente das tabelas finais para o Neon e o site de leitura em `web/`.

### Modified Capabilities

*(Nenhuma — as camadas, o modelo e a decisão não mudam.)*

## Impact

- **Código:** `src/publicacao/neon.py` (novo), uma etapa no `run_pipeline.py`, constantes no `config.py`; `web/` (novo).
- **Testes:** `tests/test_publicacao.py` — sem rede e sem banco (a conexão é substituída por uma falsa).
- **Documentação:** `docs/architecture.md` (seções 0, 7, 9 e 13 — decisão 12 implementada e decisão 16), `docs/data_dictionary.md` (tabelas no Neon), `README.md` e `CLAUDE.md`.
- **Segurança:** a senha fica só no `.env` local e nas variáveis de ambiente da Vercel; o site lê o banco apenas no servidor, nunca no navegador.
- **Fora do escopo:** login, edição de dados pelo site e agendamento automático do pipeline.
