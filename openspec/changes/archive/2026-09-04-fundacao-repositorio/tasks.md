## 1. Ajustar o script de diagnóstico

- [x] 1.1 Fazer `baixar_amostra_scr()` reaproveitar `data/raw/_amostras/scrdata_{ano}.zip` quando o arquivo já existir, com uma opção explícita para forçar o download; verificar rodando `python scripts/baixar_amostras.py` duas vezes seguidas e confirmando que a segunda não baixa os 176 MB de novo
- [x] 1.2 Fazer o diagnóstico do SCR imprimir o último `data_base` encontrado na amostra, para comparar com `config.ANO_FIM`; verificar que a saída mostra a competência mais recente do arquivo
- [x] 1.3 Acrescentar à saída da Selic a frase de que `BM12_TJOVER12` está em **% ao mês**, não ao ano; verificar que a linha aparece na execução
- [x] 1.4 Confirmar que uma falha em uma das fontes não impede o diagnóstico da outra e não levanta exceção — simular apontando temporariamente uma URL inválida e conferir que o script termina imprimindo o motivo e segue para a outra fonte

## 2. Executar o diagnóstico e coletar as respostas

- [x] 2.1 Rodar `python scripts/baixar_amostras.py` da raiz do projeto e salvar a saída completa; anotar a data real de execução (é a data de coleta que vai para os docs)
- [x] 2.2 A partir da saída, registrar em rascunho: encoding do CSV do SCR, contagem total de colunas, presença de cada uma das 5 colunas de `SCR_COLUNAS_USADAS`, contagem de registros da Selic e a última `VALDATA` publicada
- [x] 2.3 Consultar a página de termos de uso do Ipeadata e registrar a licença publicada com a URL e a data da consulta; se não houver termo inequívoco, registrar exatamente isso como resposta

## 3. Notebook de exploração da amostra

- [x] 3.1 Criar `requirements-dev.txt` começando com `-r requirements.txt` e acrescentando `jupyterlab` e `ipykernel` com versões fixadas; preencher os pins com o que o `pip` resolveu de fato (`pip freeze | grep -E "jupyterlab|ipykernel"`), não com número chutado. Verificar rodando `pip install -r requirements-dev.txt` no `.venv` e confirmando que `jupyter lab --version` responde
- [x] 3.2 Criar `notebooks/01_exploracao_amostras.ipynb` importando `src.config` (com `sys.path` ajustado para a raiz) e lendo a amostra de `config.DIR_BRONZE / "_amostras"`; verificar que nenhum caminho está chumbado no notebook
- [x] 3.3 Célula que abre o membro do ZIP e imprime os primeiros bytes crus decodificados, para decidir a olho se o decimal é vírgula ou ponto; verificar que a saída fica visível no notebook salvo
- [x] 3.4 Célula que lê o CSV com `chunksize` e `decimal` correto, contando as linhas do ano; verificar que a execução termina sem estourar a memória e que o total é impresso
- [x] 3.5 Célula que lista as modalidades distintas e conta quantas começam com `config.PREFIXO_MODALIDADE`; verificar que a contagem é comparada com as 8 modalidades esperadas e que a diferença, se houver, fica anotada
- [x] 3.6 Célula que decide a unidade de `carteira_ativa` pela ordem de grandeza dos valores de um estado grande em uma modalidade; verificar que a conclusão (reais ou milhares) está escrita em célula de texto, não só implícita no número
- [x] 3.7 Salvar o notebook com as saídas preenchidas e confirmar com `git status` que nenhum arquivo de `data/` entrou no commit

## 4. Registrar as respostas nos documentos

- [x] 4.1 Preencher em `docs/architecture.md` a data de coleta do SCR (seção 2.1) e a data de coleta e a licença da Selic (seção 2.2); verificar que os três `[PREENCHER]` sumiram dessas seções
- [x] 4.2 Registrar na seção 7.3 a decisão do grupo de **manter o Docker**, com a justificativa; verificar que o quarto `[PREENCHER]` sumiu e que `grep -n "PREENCHER" docs/architecture.md` não retorna mais nada da Sprint 1
- [x] 4.3 Acrescentar em `docs/architecture.md`, seção 2.1, o encoding, o separador de campo e o separador decimal confirmados na amostra
- [x] 4.4 Atualizar `docs/data_dictionary.md` com a unidade e o formato numérico confirmados de `carteira_ativa` e `numero_de_operacoes`, e com a nota de proveniência da Selic (o Ipeadata redistribui série produzida pelo Banco Central)
- [x] 4.5 Acrescentar ao README a instrução de uso do Docker e, na seção 4, o `pip install -r requirements-dev.txt` seguido de `jupyter lab notebooks/01_exploracao_amostras.ipynb` para abrir o notebook; verificar seguindo as instruções do zero num ambiente limpo

## 5. Reconciliar a configuração e fechar a sprint

- [x] 5.1 Comparar o diagnóstico com `src/config.py` e corrigir apenas o que divergir — encoding fora de `SCR_ENCODINGS_CANDIDATOS`, nome de coluna diferente, ou `ANO_FIM` desalinhado da última competência; registrar cada divergência encontrada em `docs/architecture.md`
- [x] 5.2 Rodar `pytest -v` e confirmar que os 7 testes de `tests/test_config.py` continuam passando após qualquer ajuste em `src/config.py`
- [x] 5.3 Conferir a definição de pronto da Sprint 1 (seção 8 do `docs/architecture.md`) item a item: as duas amostras foram abertas e todos os `[PREENCHER]` foram respondidos
- [x] 5.4 Commitar em commits atômicos no padrão do projeto (`✨ feat:`, `📄 docs:`), distribuídos e com mensagem em pt-BR; abrir o Pull Request para a `main` — *feito em 7 commits no branch `sprint-1-fundacao`; o PR #1 foi aberto e mesclado no **`develop`**, não na `main`, porque o grupo adotou `develop` como branch de integração (commit `f027a98` liberou PRs para ela no CI)*
