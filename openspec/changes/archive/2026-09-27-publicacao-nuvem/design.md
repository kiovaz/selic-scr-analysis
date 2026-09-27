## Context

- A decisão 12 (2026-09-27) aprovou NeonDB + Next.js na Vercel, com a etapa de envio opcional. O grupo tem conta nas duas plataformas.
- As saídas finais estão em `data/final/` e são pequenas: a Gold tem 24.578 linhas; as demais, de 8 a 216.
- Os testes bloqueiam a rede (`tests/conftest.py`), então a publicação precisa ser testável sem banco.

## Goals / Non-Goals

**Goals:** publicar as tabelas finais sem mudar nenhuma camada; site só de leitura, simples de explicar; pipeline continua rodando sem a nuvem.

**Non-Goals:** login, edição pelo site, agendamento do pipeline, publicar Bronze ou Silver.

## Decisions

### 1. Substituir as tabelas, não acrescentar

Cada publicação apaga e recria as tabelas, numa só transação. É o jeito mais simples de ser idempotente: a Gold já é reconstruída inteira a cada execução, então o banco espelha o arquivo. Alternativa descartada: `UPSERT` por chave — mais código e nenhum ganho, já que as tabelas são pequenas.

### 2. `psycopg` com `COPY`

`psycopg` (versão 3) é o driver padrão do Postgres em Python. O `COPY` envia as 24 mil linhas da Gold de uma vez, em segundos. Alternativa descartada: `pandas.to_sql`, que exige SQLAlchemy (mais uma dependência) e envia linha a linha.

Os tipos das colunas saem do tipo do pandas: inteiro → `bigint`, decimal → `double precision`, booleano → `boolean`, data → `date`, texto → `text`. A frase de fechamento vai numa tabela de uma linha com uma coluna `jsonb`.

### 3. Credencial no `.env`

A string de conexão fica em `DATABASE_URL`, lida do ambiente ou do `.env` da raiz com `python-dotenv`. O `.env` está no `.gitignore`. No site, a mesma variável é configurada no painel da Vercel. O `config.py` guarda só o **nome** da variável, nunca o valor.

### 4. Site em Next.js dentro de `web/`

Mesmo repositório, pasta `web/`, para o código da entrega ficar num lugar só. Na Vercel, o projeto aponta para a pasta `web/` (Root Directory). As páginas são componentes de servidor que consultam o Neon com `@neondatabase/serverless`; a página é regerada a cada hora (`revalidate`), então uma nova publicação aparece sem novo deploy. Gráficos com `recharts`, com tooltip; um eixo por gráfico (Selic e saldo em gráficos separados, nunca dois eixos no mesmo gráfico).

## Risks / Trade-offs

- [A senha vazar] → só no `.env` local e na Vercel; o site só lê no servidor. Recomendação: criar no Neon um usuário só de leitura para o site.
- [Publicação parcial] → uma transação para tudo.
- [Neon fora do ar] → o pipeline não depende dele; a publicação falha com aviso e as saídas locais continuam válidas.

## Migration Plan

1. Documentação (seções 0, 7, 9 e 13).
2. `src/publicacao/neon.py`, a etapa no pipeline e os testes.
3. Publicar os dados reais no Neon.
4. Site em `web/`, conferido com `npm run build` apontando para o banco.
