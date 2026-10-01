## Context

O motivo está em `proposal.md — Why`: a série acumulada no mês varia com os dias úteis (correlação de 0,79), e em mar/2026 subiu enquanto o Copom cortava.

Fatos conferidos em 2026-09-27:
- **A série nova:** `BM366_TJOVER366` ("Taxa de juros - Selic - fixada pelo Copom", diária, % a.a.) tem 11.044 registros de 1996-07-01 a 2026-09-25, **com todos os dias corridos**, inclusive fins de semana (2026-01-31 é sábado e está na série). O último dia de cada mês sempre existe.
- **Corte pelo último dia**, jun/2025 a jun/2026: 15,00 até fev/2026; 14,75 em mar; 14,50 em abr e mai; 14,25 em jun. São as decisões do Copom do período.
- **Alternativa:** `GM366_TJOVER366` (Selic over efetiva, diária, % a.a.) também existe.
- **Loader:** `carregar_selic()` já é agnóstico à série. Grava todos os campos como texto, o watermark compara `VALDATA[:10]` (funciona com dia) e o hash inclui `_source_object`, a URL.
- **Silver:** `construir_silver_selic()` hoje agrupa por `VALDATA[:10]` e trata cada data como um mês. Com dados diários, isso daria ~30 "leituras" por mês.

## Goals / Non-Goals

**Goals:**
- `var_selic_pp` na Gold deve refletir as **decisões do Copom**, não o calendário.
- Mudar o mínimo de código: config, Silver da Selic e uma linha no diagnóstico.
- Registrar a decisão de forma rastreável (seção 2.2 e a nova seção 13).

**Non-Goals:**
- Mudar a Gold ou a análise: o código delas não muda, só roda de novo.
- Manter as duas séries lado a lado na análise.
- Mexer no SCR.

## Decisions

### 1. Meta do Copom (`BM366`), não a Selic over efetiva (`GM366`)

A pergunta de decisão é "quando a Selic sobe…", e o decisor reage ao anúncio do Copom. A meta é o sinal de política e muda **só** nas reuniões, então cada variação mensal diferente de zero é uma decisão identificável. A over efetiva acompanha a meta (tipicamente 0,10 p.p. abaixo), mas tem pequenas oscilações diárias de mercado que não interessam aqui.

*Alternativa descartada:* corrigir a série antiga pelos dias úteis. Exige um calendário de feriados nacionais (uma dependência nova) e continua sendo uma aproximação.

### 2. Corte mensal: a meta vigente no último dia do mês

`selic_pct` do mês = o valor do **último dia com valor válido** no mês.

*Alternativa considerada:* a média da meta no mês. É mais suave, mas mistura o antes e o depois de uma decisão no meio do mês, e a variação deixa de ser "a decisão". Com o último dia, `var_selic_pp` de março/2026 é exatamente −0,25. Fica registrada como opção de sensibilidade para o futuro.

### 3. Filtro pela série configurada na Silver

A Silver só lê as linhas com `_source_object == config.SELIC_URL`. Isso protege contra Bronze antiga ou misturada: se alguém esquecer de apagar a Bronze da série anterior, a Silver não mistura % a.m. com % a.a. As linhas descartadas aparecem no relatório como `descartadas_outra_serie`.

### 4. Ordem das etapas na Silver

```
filtra série → leitura vigente por DIA (maior _ingestion_timestamp; empate ambíguo → quarentena)
→ tipagem/negativo por dia (inválido → quarentena) → corte mensal: último dia válido de cada mês
→ recorte (filtrado e contado) → mês não fechado (filtrado e contado)
```

A validação vem **antes** do corte, para um último dia inválido não virar o valor do mês. O mês usa o último dia válido anterior, e o dia inválido fica na quarentena com o motivo, então nada é corrigido em silêncio: a regra está escrita na spec e o registro fica visível.

### 5. Unidade como constante

`SELIC_UNIDADE = "% ao ano"` no `config.py` é usada pelo diagnóstico da Sprint 1. Hoje a frase "em % AO MÊS" está fixa no script e passaria a mentir. A regra do `CLAUDE.md` ("Unidade da Selic: BM12_TJOVER12 é % ao mês") é reescrita para a série nova, com a advertência de que o número é **% ao ano** e mensal só na granularidade.

### 6. Registro de decisões: seção 13 do `architecture.md`

É uma tabela com número, data, decisão, motivo e seção onde está detalhada. Entram as decisões já tomadas:
1. Bronze como veio;
2. quarentena na Silver;
3. recorte jul/2016–jun/2026 fixo;
4. quantidade como limite inferior;
5. variação só entre meses consecutivos;
6. análise em dois níveis;
7. troca da série da Selic;
8. versões republicadas preservadas;
9. defasagem do SCR de ~60 dias;
10. publicação Neon + Next.js adiada.

A tabela aponta para as seções, não repete o texto: o detalhe continua onde já está.

## Risks / Trade-offs

- [Muitos meses com `var_selic_pp = 0`, sem reunião ou sem mudança] → muitos empates no Spearman. O `scipy` trata empates corretamente, e é o retrato fiel da política: a Selic muda poucas vezes por ano. O efeito aparece mais nas defasagens (`selic_lag_k`) e em janelas de ciclo. Fica registrado na leitura dos resultados.
- [A meta pode ser anunciada no dia, com vigência no dia seguinte] → no último dia do mês isso só desloca uma decisão tomada no próprio último dia. É raro e desprezível.
- [Bronze local antiga] → o filtro de série protege a Silver, e a migração apaga e reingere a Selic (segundos).
- [A Silver passa a processar ~11 mil linhas em vez de 633] → irrelevante (milissegundos).

## Migration Plan

1. Mesclar esta change **antes** de concluir `camada-gold-analise`.
2. Localmente: apagar `data/raw/bronze_selic` e `data/raw/_controle/controle_selic.json`. Rodar a ingestão (só a Selic muda, porque o SCR vê que nada mudou), depois a Silver, a Gold e a análise.
3. Conferir: `silver_selic` com 120 meses, jun/2026 = 14,25, mar/2026 = 14,75, e `var_selic_pp` de mar/2026 = −0,25 na Gold.

Rollback: voltar `SELIC_SERIE` e reingerir a Selic.
