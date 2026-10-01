## 1. Confirmação e documentação da decisão

- [x] 1.1 **Confirmar com o grupo o limiar** "20 maiores notas por trimestre" (proposal). Se o grupo escolher outro tamanho ou uma nota mínima, ajustar `TOP_RECOMENDACAO` e os textos antes de seguir. Verificar: a resposta do grupo está anotada nesta task.
  - **Resposta do grupo (2026-09-27):** confirmadas as **20 maiores notas por trimestre**.
- [x] 1.2 Atualizar a seção 0 do `docs/architecture.md`: o decisor passa a ser "diretoria de crédito de uma instituição financeira de atuação nacional, que decide a cada trimestre em quais estados e modalidades expandir ou reduzir a oferta de financiamento"; o escopo diz que o modelo já existe; "onde os dados vivem" cita a publicação futura (decisão 12). Manter a nota de vocabulário. Verificar: `grep -n "cooperativa" docs/architecture.md` só encontra a nota de vocabulário (segmento).
- [x] 1.3 Completar o checklist 6.3 com as duas perguntas do enunciado (entidades em treino e teste; imputadores), com resposta e evidência. Na seção 2.2 e na tabela da seção 3, registrar que a API do Ipeadata não oferece paginação (`$top`/`$skip` ignorados, conferido em 2026-09-27) e como o Requisito 2 é atendido. Na seção 11, as limitações do modelo. Na seção 13, as decisões 13 (decisor) e 14 (limiar). Verificar: o checklist tem as perguntas do enunciado respondidas.

## 2. Etapa de decisão

- [x] 2.1 Acrescentar ao `src/config.py`: `TOP_RECOMENDACAO = 20`, `LIMIARES_SENSIBILIDADE = [0.5, 0.6, 0.7, 0.8, 0.9]`, `TAMANHOS_LISTA = [10, 20, 40]`, `ARQUIVO_RECOMENDACAO`, `ARQUIVO_SENSIBILIDADE` e `ARQUIVO_FRASE` (em `DIR_GOLD`), com comentários; isolar os caminhos em `tests/conftest.py`. Verificar: `pytest tests/test_config.py`.
- [x] 2.2 Criar `src/ml/decisao.py` com `montar_recomendacao()` (20 expandir + 20 alerta, com posição, grupo e `volume_rs` no t0) e `tabela_sensibilidade()` (limiares e tamanhos de lista, modelo × volta ao normal, com as previsões do teste e a `aceleracao_3m` da `gold_ml_dataset`). Verificar: testes com previsões sintéticas conferem a ordem da lista e a precisão das N maiores notas.
- [x] 2.3 Criar `numeros_da_frase()` e `executar_decisao()`, que gravam os três arquivos de forma atômica, sem rede. Verificar: um teste confere que 82,5% de precisão numa lista de 20 vira 16,5 acertos e 3,5 erros por trimestre; duas execuções dão saídas idênticas.
- [x] 2.4 Acrescentar a etapa "Sprint 6: decisão" ao `scripts/run_pipeline.py`, imprimindo a frase de fechamento com os números e as 20 recomendações. Criar `tests/test_decisao.py`. Verificar: `pytest -v` verde, sem rede e sem tocar em `data/`.

## 3. Números reais na entrega

- [x] 3.1 Rodar a etapa de decisão sobre as previsões reais e anotar nesta task: a tabela de sensibilidade, os números do JSON e as 20 recomendações. Verificar: os números batem com a Sprint 5 (82,5% e 75,0% nas 20 maiores).
  - **Resultado (2026-09-27, previsões reais):** sensibilidade no teste — nota ≥0,5: 106,7/mês, precisão 67,7%, recall 82,7%; ≥0,6: 92,1, 69,3%, 73,2%; ≥0,7: 73,4, 72,2%, 60,7%; ≥0,8: 48,0, 76,2%, 41,9%; ≥0,9: 15,3, 84,8%, 14,9%. Listas: 10 → 79,2% (regra simples 77,5%); **20 → 82,5% (75,0%)**; 40 → 77,5% (67,1%). Frase: ~16,5 acertos e ~3,5 erros por trimestre (acaso ~10,0; regra simples 15,0); AUC 0,778 × 0,688; associação mais forte da Sprint 4: imobiliário, k=4, ρ=+0,42. Lista set–nov/2026: 20 combinações, R$ 557,5 bi de saldo; 9 rurais; topo em mercados pequenos (AP exportação 0,953; PI e RN importação). Bate com a Sprint 5.
- [x] 3.2 Preencher a seção 1 (frase de fechamento) e a seção 10 (decisor, ação, custo de FP e FN, limiar adotado e por quê, ligação métrica → consequência) do `architecture.md` **com os números do JSON**. Atualizar o `data_dictionary.md` com as três saídas da decisão. Verificar: nenhum "PENDENTE" ou "a preencher" sobra nas seções 1 e 10.
  - **Resultado:** frase de fechamento preenchida na seção 1 e seção 10 reescrita (decisor, ação, custos de FP/FN, limiar e por quê, sensibilidade, leitura da lista) com os números do JSON; dicionário com as saídas da decisão. Nenhum "PENDENTE"/"a preencher" nas seções 1 e 10.

## 4. README e CLAUDE.md

- [x] 4.1 Reescrever o `README.md` completo:
  - o que o projeto responde, com a frase de fechamento;
  - como rodar do zero (**Python 3.11**, venv, `pip install -r requirements.txt`, `python scripts/run_pipeline.py` com a primeira carga de ~50 min e as seguintes em segundos, `--anos` para um teste rápido, testes, notebooks 01 a 03, demonstração de idempotência);
  - onde ficam os resultados (tabelas em `data/final/` e figuras em `docs/figuras/`);
  - a estrutura atualizada (`src/analise`, `src/ml`, `notebooks/02` e `03`);
  - as fontes com licença e data;
  - as sprints marcadas;
  - as limitações.

  Verificar: o README não cita mais "Sprint 1" como estado atual e tem os passos na ordem em que se executam.
- [x] 4.2 Atualizar o `CLAUDE.md`: o estado do projeto (Sprints 1 a 6, módulos implementados), os comandos (`run_pipeline.py` completo, `conferir_bronze.py`) e a regra de que não há atribuição em commits e PRs. Verificar: `grep -n "pacotes vazios" CLAUDE.md` vazio.

## 5. Verificação e entrega

- [x] 5.1 **Clone limpo:** clonar o branch numa pasta temporária e seguir **só o README** (venv novo, instalação, `pytest`, `python scripts/run_pipeline.py --anos 2024`). Corrigir no README tudo o que precisar de ajuda externa. Anotar o Python usado (a máquina não tem 3.11; o CI confirma) e o resultado. Apagar a pasta temporária ao final.
  - **Resultado (2026-09-27):** clone do branch numa pasta temporária seguindo só o README (Windows): `py -3.14 -m venv` (**a máquina não tem Python 3.11** — o README pede 3.11; o CI confirma 3.11), `pip install -r requirements.txt` ok, `pytest` **93 passed**, `run_pipeline.py --anos 2024` baixou o ZIP de 2024 e gerou Bronze, Silver (2.450 linhas, 12 meses), Gold e análise.
  - **Falha encontrada e corrigida:** com um ano só nenhuma combinação tem os 120 meses da coorte, a base de ML ficava vazia e o pipeline **quebrava** (`StandardScaler` com 0 amostras). Correção: o ML e a decisão são pulados com aviso (teste `test_ml_pulado_com_poucos_dados`). Reexecução no clone: exit 0 em 63 s.
  - Pasta temporária apagada.
- [x] 5.2 `pytest -v`, CI verde no PR para o `develop` e commits atômicos em pt-BR **sem linha de atribuição**.
  - **Resultado:** 94 testes passando; PR #18 com CI verde em Python 3.11; commits sem linha de atribuição.
