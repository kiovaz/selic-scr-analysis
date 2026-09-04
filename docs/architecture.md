# Definição Arquitetural do Projeto — Impacto da Selic nos Financiamentos por Estado

> Documento de especificação do projeto (OpenSpec). Toda decisão de implementação deve ser rastreável a uma seção daqui. Mudança de escopo passa primeiro por este arquivo, depois pelo código.
>
> **Versão 2** — correções de consistência aplicadas, stack enxuta, desenvolvimento em sprints, seção de ML mantida como escopo mas com definição adiada.

---

## 0. Contexto e Objetivo

**Problema:** entender se — e o quanto — variações na taxa Selic estão associadas ao saldo de financiamentos no Brasil, com granularidade por estado (UF) e por **modalidade** de crédito.

**Decisor final:** diretoria de crédito de uma cooperativa de crédito ou financeira regional, que precisa decidir em quais estados e modalidades expandir ou reduzir a oferta de financiamento a cada trimestre.

**Escopo:** pipeline de dados completo (Bronze → Silver → Gold) + análise estatística de associação + modelo preditivo (definição na Sprint 5, ver seção 6).

**Onde os dados vivem:** filesystem local do projeto, pasta `data/` no `.gitignore`. Sem cloud, sem DVC — decisão consciente pelo escopo acadêmico.

### Nota sobre vocabulário

No SCR.data, `segmento` e `modalidade` são coisas diferentes. Este projeto usa **modalidade**.

| Termo | O que significa no SCR.data | Usamos? |
|---|---|---|
| `segmento` | tipo da instituição que emprestou (Banco, Cooperativa, Financeira, Fintech, etc.) | não |
| `modalidade` | tipo da operação de crédito (Empréstimos, Financiamentos, Arrendamento, etc.) | **sim** |

Em nenhum documento, apresentação ou código do projeto a palavra "segmento" deve ser usada para se referir ao tipo de financiamento.

---

## 1. Pergunta de Pesquisa e Hipóteses

**Pergunta de pesquisa:**
> Existe associação estatisticamente significativa entre os ciclos de alta e baixa da taxa Selic e o saldo (e sua variação mensal) da quantidade e do volume de financiamentos, por unidade da federação e por modalidade de crédito?

**Hipótese principal (H1):**
> Variações na taxa Selic têm associação estatisticamente significativa com a quantidade e o volume de financiamentos, com efeito diferenciado por UF e por modalidade.

**Hipótese nula (H0):**
> Não existe associação estatisticamente significativa entre a taxa Selic e a quantidade/volume de financiamentos por UF e por modalidade.

**Pergunta de decisão/ação:**
> Quando a Selic sobe, o saldo de financiamentos recua em estados e modalidades específicos — e esse recuo é grande e previsível o bastante para orientar a estratégia de concessão de crédito no trimestre seguinte?

**Frase de fechamento (template obrigatório da entrega):**
> "Cruzando o SCR.data e a Selic, identificamos que \_\_\_\_. Recomendamos que \_\_\_\_ faça \_\_\_\_ nos próximos \_\_\_\_, priorizando \_\_\_\_. Se agir, o ganho esperado é \_\_\_\_; se errarmos, o custo é \_\_\_\_."

> **Por que "saldo" e não "novos financiamentos concedidos":** o SCR.data publica a carteira ativa, que é o saldo devedor no fim do mês, não o valor contratado no mês. A variação mensal do saldo é usada como aproximação de fluxo, e essa limitação está declarada na seção 11. A pergunta precisa refletir o dado que existe.

---

## 2. Fontes de Dados

### 2.1. Base X — SCR.data (Banco Central do Brasil)

| Campo | Valor |
|---|---|
| Instituição | Banco Central do Brasil — Depto. de Monitoramento do Sistema Financeiro |
| O que é | Dados de crédito por estado e mês |
| Portal | https://dadosabertos.bcb.gov.br/dataset/scr_data |
| Download | `https://www.bcb.gov.br/pda/desig/scrdata_{ANO}.zip` |
| Formato | ZIP → CSV, separador `;`, decimal `,`, campos entre aspas duplas |
| Encoding | `utf-8-sig` (UTF-8 com BOM) — **confirmado na Sprint 1**, ver ressalva abaixo |
| Acesso | Arquivo |
| Granularidade original | UF × mês × segmento × cliente × modalidade × submodalidade × CNAE/ocupação × porte × origem × indexador |
| Período disponível | desde jun/2012, atualização mensal (~30 dias após o fechamento) |
| Licença | Open Data Commons ODbL |
| Metodologia | https://www.bcb.gov.br/pda/desig/metodologia_versao2.pdf |
| Colunas usadas | `data_base`, `uf`, `modalidade`, `numero_de_operacoes`, `carteira_ativa` |
| **Data de coleta** | **2026-09-03** (amostra do ano de 2024) |
| Volume conferido | ZIP de 167,9 MiB → 12 CSVs mensais, ~1,15 GB descompactado, 3.726.515 linhas em 2024 |

**Conferido na Sprint 1 (amostra de 2024, coletada em 2026-09-03):**

- O ZIP de um ano traz **um CSV por mês** (`scrdata_AAAAMM.csv`), cada um com um único `data_base`. A amostra tem 24 colunas e as 5 que o projeto usa estão todas presentes.
- **Encoding: `utf-8-sig`.** A lista `SCR_ENCODINGS_CANDIDATOS` do `config.py` estava como `["latin-1", "utf-8"]` e precisou ser corrigida para `["utf-8-sig", "utf-8", "latin-1"]`. Motivo: quem lê adota o primeiro candidato que decodificar sem erro, e `latin-1` aceita qualquer byte — nunca falha. Vindo primeiro, ele vencia sempre e devolvia `ComÃ©rcio` no lugar de `Comércio`. Como `modalidade` é texto acentuado e o recorte é `LIKE 'Financiamentos%'`, o encoding errado quebraria o filtro central do projeto. **A ordem da lista não pode ser trocada.**
- **`carteira_ativa` está em REAIS**, não em milhares. Aferido pela ordem de grandeza: SP somou R$ 977,0 bilhões em financiamentos em dez/2024.
- **`numero_de_operacoes` usa `-1` como máscara** para valores abaixo do limite de divulgação do BCB. Não é contagem negativa. Ocorre em 83.511 das 310.432 linhas de dez/2024 (27%) — precisa de tratamento explícito na Silver.
- O nome exato de uma modalidade é `Financiamentos rurais  (ex-financiamentos rurais e agroindustriais)`, **com dois espaços** antes do parêntese. O filtro por prefixo não se incomoda, mas comparação por igualdade precisa do nome exato.
- **`ANO_FIM` estava em 2025 e foi corrigido para 2026.** Conferido por requisição ao próprio endpoint: os ZIPs de 2024, 2025 e 2026 respondem 200; o de 2027 dá 404. O arquivo de 2026 é parcial (100,8 MiB contra 167,9 MiB de um ano cheio), coerente com a defasagem de publicação de ~30 dias.
- Evidência completa em `notebooks/01_exploracao_amostras.ipynb`, com as saídas gravadas.

**Filtro aplicado:** o SCR.data tem 13 modalidades de crédito; usamos as 8 que começam com "Financiamentos" (`modalidade LIKE 'Financiamentos%'`): financiamentos, à exportação, à importação, com interveniência, rurais e agroindustriais, imobiliários, de títulos e valores mobiliários, e de infraestrutura e desenvolvimento.

### 2.2. Base Y — Selic (Ipeadata / Ipea)

| Campo | Valor |
|---|---|
| Instituição | Instituto de Pesquisa Econômica Aplicada — Ipea |
| O que é | Taxa básica de juros, acumulada no mês |
| Endpoint | `http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='BM12_TJOVER12')` |
| Formato | JSON (OData v4) |
| Acesso | API REST, sem autenticação |
| Unidade | **% ao mês** (não % ao ano) |
| Campos | `SERCODIGO`, `VALDATA`, `VALVALOR` — a API devolve também `NIVNOME` e `TERCODIGO`, ambos vazios nesta série |
| Período | mensal — 633 registros, de jan/1974 a set/2026; **123 dentro do recorte** (jul/2016 em diante) |
| Licença | Sem termo único publicado no Ipeadata — ver ressalva abaixo. Uso educacional permitido e **citação da fonte obrigatória** nas três declarações do Ipea |
| **Data de coleta** | **2026-09-03** |

**Licença — consultado em 2026-09-03.** Nem o `ipeadata.gov.br` nem a página da sua API publicam termos de uso. O que existe são três declarações diferentes, em propriedades distintas do Ipea:

| Onde | O que diz |
|---|---|
| [ipea.gov.br/portal/dados-abertos](https://www.ipea.gov.br/portal/dados-abertos) | "Todo o conteúdo deste site está publicado sob a licença **Creative Commons Atribuição 2.5 Brasil**." |
| [repositorio.ipea.gov.br](https://repositorio.ipea.gov.br/handle/11058/2206) (registro IPEADATA) | **Licença Padrão Ipea**: reprodução e exibição para uso educacional ou informativo, com crédito e citação da fonte; proíbe uso comercial e obras derivadas. |
| [ipea.gov.br/extrator/termos_condicoes.html](https://www.ipea.gov.br/extrator/termos_condicoes.html) (outra ferramenta) | Apache 2.0 para o software; obrigatória a citação da fonte do dado. |

O denominador comum das três é o que vale para este projeto: **uso educacional é permitido e a citação da fonte é obrigatória**. Sendo um trabalho acadêmico, sem fim lucrativo e sem redistribuição do dado bruto, o uso está coberto mesmo pela leitura mais restritiva. A divergência entre as três está registrada na seção 11 (Limitações Conhecidas).

**Atenção ao último mês da série.** Na coleta de 2026-09-03 o último registro era `2026-09-01` com valor **0,1**, contra ~1,1 nos meses vizinhos: é o **mês corrente ainda incompleto**. Incluí-lo produziria uma queda falsa de mais de 90% na variação da Selic. O mês em curso precisa ser descartado na Silver.

**Nota de proveniência:** o Ipeadata redistribui a série originalmente produzida pelo Banco Central. Instituição mantenedora distinta, origem primária a mesma. Isso deve constar explicitamente no dicionário de dados.

### 2.3. Recorte temporal

**Definido: julho/2016 até a última competência publicada do SCR.data.**

Justificativa: o SCR.data tem uma quebra de série em junho/2016, quando o limite de identificação das operações caiu de R$ 1.000 para R$ 200. Começar em julho/2016 evita comparar períodos com réguas diferentes. O recorte ainda cobre um ciclo completo de juros (Selic alta em 2016, mínima histórica em 2020-21, alta de novo em 2022-23), que é exatamente o que a pergunta precisa.

### 2.4. Cruzamento

- **Chave:** `ano_mes`.
- A Selic é nacional: o mesmo valor se repete para as 27 UFs em cada mês. Isso é esperado e deve estar documentado — não é erro de join.
- **Órfãos a tratar e reportar:**
  - meses da Selic sem SCR (defasagem de publicação do SCR, ~30 dias);
  - meses do SCR sem Selic (fora do recorte temporal).
  - A contagem exata dos dois lados entra na entrega final.

---

## 3. Arquitetura de Ingestão

| Forma | Fonte | Detalhes obrigatórios |
|---|---|---|
| **Arquivo** | SCR.data | Baixa o ZIP, descompacta, lê o CSV tratando encoding, separador `;` e tipagem explícita |
| **API REST** | Ipeadata (Selic) | Requisição com timeout, tratamento de erro e retry com backoff |
| **Carga incremental** | Ipeadata (Selic) | Guarda a última data já ingerida numa tabela de controle (watermark) e busca só o que falta na execução seguinte |

### 3.1. Metadados técnicos da Bronze

Obrigatórios em toda linha, sempre com prefixo `_`:

`_ingestion_timestamp`, `_ingestion_date`, `_source_system`, `_source_object`, `_load_id`, `_ingestion_mode` (`full` | `incremental`), `_record_hash`.

### 3.2. Idempotência

`_record_hash` é o hash SHA-256 do **conteúdo do registro concatenado com `_source_object`**.

Incluir o arquivo de origem no hash é intencional: garante que duas linhas de conteúdo idêntico vindas de arquivos diferentes sejam preservadas, e que só o reprocessamento do **mesmo arquivo** seja descartado. Sem isso, linhas legítimas duplicadas dentro da fonte sumiriam, o que violaria a regra de que a Bronze não descarta registro.

Rodar a ingestão duas vezes seguidas não pode alterar a contagem final de linhas. Isso será demonstrado ao vivo na defesa e coberto por teste automatizado (`test_idempotencia.py`).

### 3.3. Quarentena

Registro com estado inválido, data fora do intervalo, valor negativo ou tipo errado vai para uma tabela separada, com o motivo e o registro original preservados. O job nunca quebra por causa de dado sujo.

Motivos padronizados: `uf_invalida`, `data_fora_do_intervalo`, `valor_negativo`, `tipagem_invalida`, `duplicata_na_chave`.

---

## 4. Arquitetura Medallion

### 4.1. Regras por camada

| Camada | O que precisa estar lá | O que não pode estar |
|---|---|---|
| **Bronze** | Dado como veio da fonte, imutável, com metadados técnicos e particionamento por data | Regra de negócio, deduplicação semântica, agregação, descarte de registro |
| **Silver** | Tipagem forte, padronização, chave e granularidade declaradas, deduplicação, validações com quarentena, integridade referencial do join | Dado sem contrato definido; correção silenciosa que ninguém consegue explicar |
| **Gold** | Tabelas orientadas à pergunta de decisão: agregações e indicadores | Qualquer limpeza — se precisou limpar aqui, a Silver falhou |

Regra geral: reprocessamento sempre parte da Bronze. Se Silver ou Gold quebram, são reconstruídas — a fonte não é consultada de novo.

### 4.2. Tabelas do projeto

| Camada | Tabela | Uma linha por… | Chave primária |
|---|---|---|---|
| Bronze | `bronze_scr` | linha do CSV original | `(_source_object, _record_hash)` |
| Bronze | `bronze_selic` | data da série | `(_source_object, _record_hash)` |
| Silver | `silver_scr` | mês × estado × modalidade | `(ano_mes, uf, modalidade)` |
| Silver | `silver_selic` | mês | `(ano_mes)` |
| Gold | `gold_credito_selic` | mês × estado × modalidade | `(ano_mes, uf, modalidade)` |
| Gold | `gold_ml_dataset` | *(a definir na Sprint 5 — ver seção 6)* | *(a definir)* |

**Prova obrigatória de ausência de duplicata na chave:**
```python
assert df.duplicated(["ano_mes", "uf", "modalidade"]).sum() == 0
```

---

## 5. Modelagem de Dados

### 5.1. Dicionário — `silver_scr`

| Coluna | Tipo | Domínio | Origem | Significado |
|---|---|---|---|---|
| `ano_mes` | date | ≥ jul/2016 | `data_base` | mês de referência |
| `uf` | string(2) | 27 estados | `uf` | estado do tomador (CEP de residência para PF, sede para PJ) |
| `modalidade` | string | 8 modalidades de financiamento | `modalidade` | tipo de financiamento |
| `qtd_operacoes` | integer | ≥ 0 | `numero_de_operacoes` | quantidade de operações |
| `volume_rs` | decimal | ≥ 0 | `carteira_ativa` | saldo em R$ nominais |

### 5.2. Dicionário — `silver_selic`

| Coluna | Tipo | Domínio | Origem | Significado |
|---|---|---|---|---|
| `ano_mes` | date | mensal | `VALDATA` | mês de referência |
| `selic_pct` | decimal | > 0 | `VALVALOR` | Selic acumulada no mês, % a.m. |

### 5.3. Dicionário — `gold_credito_selic`

| Coluna | Tipo | Origem | Significado |
|---|---|---|---|
| `ano_mes` | date | Silver | mês |
| `uf` | string(2) | Silver | estado |
| `modalidade` | string | Silver | tipo de financiamento |
| `qtd_operacoes` | integer | Silver | quantidade de operações |
| `volume_rs` | decimal | Silver | saldo em R$ |
| `var_qtd_pct` | decimal | derivada | variação % da quantidade vs. mês anterior |
| `var_volume_pct` | decimal | derivada | variação % do volume vs. mês anterior |
| `selic_pct` | decimal | Silver | Selic do mês |
| `var_selic_pp` | decimal | derivada | variação da Selic em pontos percentuais |
| `selic_lag_1` … `selic_lag_6` | decimal | derivada | Selic de 1 a 6 meses atrás |

**Regra de cálculo:** variações e lags são calculados separadamente por estado e modalidade, ordenados por mês — nunca misturando combinações diferentes. Os primeiros meses de cada combinação ficam nulos por definição; isso não é preenchido artificialmente.

### 5.4. Regras de análise estatística

- Comparar **variações**, não níveis absolutos. Selic e crédito têm tendência de crescimento própria; comparar níveis gera correlação alta que não significa nada (correlação espúria).
- Testar a Selic defasada em 1 a 6 meses — o crédito reage com atraso a mudanças de juros.
- Rodar a análise separadamente por modalidade. Financiamento imobiliário e rural têm juros subsidiados e indexadores próprios, e reagem menos à Selic por construção.
- Reportar como **associação**, nunca como causa.

---

## 6. Base ML-Ready e Anti-Vazamento

> **Status: escopo confirmado, definição adiada para a Sprint 5.**
>
> O grupo vai fazer a parte de ML, mas ainda não decidiu o que exatamente vai prever. A definição acontece na Sprint 5, **antes** de qualquer linha de código de treino, e este documento é atualizado com as respostas antes de a Sprint começar.

### 6.1. Decisões pendentes

| Elemento | Pergunta a responder na Sprint 5 |
|---|---|
| **Tipo de problema** | Classificação (a direção da variação) ou regressão (o tamanho da variação)? |
| **Label** | O que exatamente é o positivo, e em que momento se sabe que aconteceu |
| **Regra de rotulagem** | A condição formal do evento, em código |
| **Coorte** | Quais combinações UF × modalidade são elegíveis, e o que foi excluído e por quê |
| **Janela de observação** | De onde vêm as features (sempre antes do t0) |
| **Janela de predição** | Onde o label é observado (sempre depois do t0) |
| **Baseline** | O modelo trivial contra o qual o nosso será comparado |
| **Métrica** | Qual, por que ela cabe no desbalanceamento, e **qual é a classe positiva** |

### 6.2. Decisões já fechadas (valem para qualquer opção)

**Ponto de corte (t0):** o último mês **publicado** do SCR.data, não o mês corrente.

Isso é deliberado. O SCR.data sai com cerca de 30 dias de atraso, então no momento real da decisão o dado do mês corrente ainda não existe. Usar o mês corrente como t0 seria dar ao modelo uma informação que na prática ele não teria — vazamento operacional.

**Split: temporal.** Treino nos meses mais antigos, teste nos mais recentes.

Justificativa: o objetivo é prever os **mesmos estados e modalidades** em meses futuros, não generalizar para estados novos. Como não existe risco de uma entidade nova aparecer no teste, separar por tempo basta. Split por grupo não se aplica.

### 6.3. Checklist Anti-Vazamento

A responder item a item na entrega final, independentemente do modelo escolhido:

- [ ] Toda feature existia antes do t0?
- [ ] As agregações (lags, médias móveis) foram calculadas apenas com dados anteriores ao t0 de cada observação?
- [ ] O split respeita a ordem temporal? Nenhum mês de teste aparece antes de um mês de treino?
- [ ] Scalers e encoders foram ajustados (`fit`) **somente** no treino, com apenas `transform` em teste?
- [ ] A coluna que dá origem ao label foi removida das features?

### 6.4. Armadilhas específicas deste projeto

- **Selic de meses futuros entrando como feature.** Usar apenas `selic_pct` e `selic_lag_*` até o t0.
- **A mesma coluna virando feature e label.** Se o label vier de `volume_rs`, a feature tem que ser sempre de mês anterior ou igual ao t0, nunca posterior.
- **Combinações com pouco histórico.** Aplicar o filtro de coorte antes do split, não depois.
- **Métrica alta demais.** Acima de 0,95 é motivo de investigação, não de comemoração.

---

## 7. Stack e Ambiente

Stack enxuta de propósito. Cada ferramenta aqui ou é exigida pelo enunciado, ou paga o próprio custo de aprendizado. O critério: **todo integrante precisa saber explicar qualquer trecho entregue** — ferramenta que ninguém do grupo sabe justificar vira passivo, não diferencial.

### 7.1. O que fica

| Item | Por quê |
|---|---|
| **Python 3.11+**, pandas, requests | núcleo do pipeline |
| **scikit-learn** | Sprint 5 (ML) |
| **matplotlib / seaborn** | gráficos da análise e da entrega de decisão |
| **venv + `requirements.txt` com versões fixadas** | exigido pelo enunciado |
| **pytest** | é como se prova a unicidade da chave e a idempotência. Sem isso, o Requisito 2 vira promessa |
| **GitHub Actions** | roda os testes a cada push. Custo de setup baixo (um YAML), e mostra na prática que o pipeline não quebrou |
| **Docker + `docker-compose.yml`** | padroniza o ambiente entre os membros. **Ver ressalva em 7.3** |
| **Git** | exigido |

### 7.2. O que sai

| Item | Por que foi cortado |
|---|---|
| **DVC** | O enunciado exige apenas que os dados não vão para o Git. `data/` no `.gitignore` já resolve, de graça. DVC sem um remote configurado é overhead sem benefício |
| **Great Expectations / Pandera** | As validações deste projeto (domínio de UF, tipos, faixas, duplicata) cabem em funções simples em `src/validation/`, cobertas por pytest. Uma biblioteca declarativa a mais é uma coisa a mais para todo mundo saber explicar |
| **Black / Flake8 como obrigatórios** | Podem entrar no CI se o grupo quiser, mas não valem ponto e não são bloqueantes |
| **`.env` / python-dotenv** | Nenhuma das duas fontes exige token ou autenticação. Caminhos de dados ficam num `config.py` simples |

### 7.3. Ressalva sobre o Docker

O Docker resolve "na minha máquina funciona", mas o enunciado já é satisfeito por `venv` + `requirements.txt` com versões fixadas + README.

**Regra de decisão:** se pelo menos um integrante já tem alguma familiaridade com Docker, mantemos. Se ninguém tem, cortamos e ficamos com `venv`. Debugar Dockerfile é tempo que não vira nota.

Decisão do grupo (Sprint 1, 2026-09-03): **MANTER o Docker.**

O critério da própria regra acima foi atendido — há integrante do grupo com familiaridade suficiente para explicar o `Dockerfile` na apresentação. `Dockerfile` e `docker-compose.yml` seguem versionados, e o README traz a instrução de uso.

Vale registrar o que o Docker **não** faz aqui: ele não é o caminho padrão de execução, que continua sendo `venv` + `requirements.txt`. Ele padroniza o ambiente entre as máquinas do grupo. Se em alguma sprint futura ninguém conseguir mais explicar o Dockerfile, a decisão é revista — o critério é esse, não o esforço já investido.

Uma consequência prática desta decisão: o `Dockerfile` copia **apenas** o `requirements.txt` na camada de dependências. As ferramentas de exploração (Jupyter) ficam em `requirements-dev.txt` justamente para não entrarem na imagem nem na instalação do CI.

---

## 8. Plano de Sprints

Desenvolvimento incremental. Cada sprint tem uma **definição de pronto** objetiva, e nenhuma sprint começa antes de a anterior estar fechada.

### Sprint 1 — Fundação

**Objetivo:** garantir que o tema é viável antes de investir em código.

- Fechar a pergunta de pesquisa, as hipóteses e o decisor (seções 0, 1 e 10 revisadas com o grupo)
- Criar o repositório com a estrutura de pastas da seção 9
- `requirements.txt`, `.gitignore`, `README.md` inicial
- **Baixar à mão uma amostra real de cada base** e abrir para conferir
- Preencher: licença do Ipeadata, datas de coleta, decisão sobre Docker
- Confirmar na amostra: tamanho do arquivo, encoding, separador, se o decimal é vírgula ou ponto, e se `carteira_ativa` está em reais ou milhares

**Pronto quando:** as duas amostras estão abertas no computador de alguém do grupo e os campos `[PREENCHER]` deste documento foram respondidos.

> Esta sprint existe porque projeto morre no segundo encontro quando a base "que existia" está atrás de login, tem 40 GB ou parou de ser atualizada.

### Sprint 2 — Ingestão Bronze

- `src/ingestion/scr_file_loader.py`: download do ZIP, descompactação, leitura do CSV com encoding, separador e tipagem explícitos
- `src/ingestion/selic_api_loader.py`: requisição com timeout, tratamento de erro e retry com backoff
- Metadados técnicos da seção 3.1 em toda linha
- Quarentena funcionando com os motivos padronizados
- Escrita em `data/raw/`, particionada por data

**Pronto quando:** os dois loaders rodam do zero e produzem `bronze_scr` e `bronze_selic` em disco, e um registro sujo injetado de propósito cai na quarentena sem derrubar o job.

### Sprint 3 — Idempotência, incremental e CI

- `_record_hash` implementado conforme a seção 3.2
- Carga incremental por watermark na Selic, com tabela de controle
- `tests/test_idempotencia.py` e `tests/test_no_duplicates.py`
- GitHub Actions rodando `pytest` a cada push

**Pronto quando:** rodar o pipeline duas vezes seguidas não muda a contagem de linhas, e o CI está verde no repositório.

### Sprint 4 — Silver e Gold

- `silver_scr` e `silver_selic` com tipagem, deduplicação e validações
- Join e contagem de órfãos dos dois lados, registrada
- `gold_credito_selic` com as variações e os lags da seção 5.3
- Análise estatística conforme a seção 5.4
- Dicionário de dados consolidado em `docs/data_dictionary.md`

**Pronto quando:** o `assert` de duplicata passa nas três tabelas e existe um primeiro gráfico da relação Selic × variação do crédito.

### Sprint 5 — Definição e treino do ML

- **Preencher a tabela 6.1 e atualizar este documento — antes de escrever código de treino**
- Construir `gold_ml_dataset`
- Baseline primeiro, modelo depois
- Responder o checklist 6.3 item a item

**Pronto quando:** o modelo supera o baseline e o checklist anti-vazamento está respondido por escrito.

### Sprint 6 — Decisão e entrega

- Definir o limiar de decisão ligando a métrica ao custo do erro (seção 10)
- Preencher a frase de fechamento com os números reais
- README completo, permitindo rodar do zero
- Declaração de uso de IA
- Ensaio da defesa: cada integrante explica um trecho sorteado do código

**Pronto quando:** alguém de fora do grupo consegue rodar o pipeline seguindo só o README.

---

## 9. Organização do Repositório

```
projeto-selic-credito/
├── README.md
├── requirements.txt
├── Dockerfile                   # se a decisão de 7.3 for manter
├── docker-compose.yml           # idem
├── .gitignore
│
├── data/                        # fora do Git
│   ├── raw/                      # Bronze
│   ├── processed/                # Silver
│   └── final/                    # Gold
│
├── notebooks/
│   ├── 01_exploracao_amostras.ipynb
│   ├── 02_analise_estatistica.ipynb
│   └── 03_modelo.ipynb
│
├── src/
│   ├── __init__.py
│   ├── config.py                 # caminhos e constantes
│   ├── ingestion/
│   │   ├── scr_file_loader.py
│   │   └── selic_api_loader.py
│   ├── transformation/
│   │   ├── silver_scr.py
│   │   ├── silver_selic.py
│   │   └── gold_credito_selic.py
│   ├── validation/
│   │   └── quality_checks.py
│   ├── ml/                       # Sprint 5
│   └── utils/
│
├── tests/
│   ├── test_ingestion.py
│   ├── test_transformation.py
│   ├── test_no_duplicates.py
│   └── test_idempotencia.py
│
├── scripts/
│   └── run_pipeline.py
│
└── docs/
    ├── architecture.md           # este arquivo
    └── data_dictionary.md        # seção 5 consolidada
```

**Estratégia Git:** `main` estável, branches de feature por membro, merge via Pull Request. Commits atômicos no formato `tipo: descrição breve` (`feat:`, `fix:`, `docs:`, `test:`).

**Commits distribuídos entre os integrantes ao longo do tempo.** Um repositório com tudo no último dia e um autor só é tratado como trabalho de uma pessoa.

**`.gitignore`** cobrindo `data/`, `*.csv`, `*.zip`, `*.parquet`, `__pycache__/`, `.venv/`.

---

## 10. Decisão de Negócio

- **Decisor:** diretoria de crédito de uma cooperativa de crédito ou financeira regional.
- **Ação possível:** aumentar ou reduzir a oferta de financiamento por estado e modalidade no próximo trimestre.
- **Custo de falso positivo** (expandir onde o crédito vai encolher): capital parado, equipe comercial alocada, meta não batida, risco de afrouxar o padrão de concessão para preencher volume.
- **Custo de falso negativo** (não expandir onde o crédito vai crescer): receita perdida, espaço cedido ao concorrente, custo de reentrar depois.
- **Limiar de decisão:** [PENDENTE — Sprint 6, definir após o treino, com base no trade-off precisão/recall que faça sentido para os custos acima. O limiar tende a ser assimétrico, porque o custo do falso positivo é imediato e o do falso negativo é de oportunidade.]
- **Frase de decisão final:** template na seção 1, a preencher com os números reais do pipeline.

---

## 11. Limitações Conhecidas

1. O SCR.data mostra o **saldo** da carteira no fim do mês, não os financiamentos novos do mês. A variação mensal é uma aproximação — ela é o resultado líquido de novas operações menos pagamentos e baixas.
2. O estado vem do CEP de residência (pessoa física) ou da sede (pessoa jurídica), não de onde o dinheiro é efetivamente usado.
3. Valores em reais nominais, sem correção pela inflação.
4. A Selic é nacional — não existe taxa por estado. O efeito diferente por UF é inferido pela resposta ao mesmo estímulo, não por variação do estímulo.
5. Associação não é causa: renda, emprego, safra e política de crédito dos bancos não são controlados.
6. Operações abaixo de R$ 200 não entram na base. O limite era R$ 1.000 até maio/2016 — por isso o recorte começa em julho/2016.

7. O Ipeadata **não publica termos de uso** no seu próprio site. As três declarações de licença encontradas em propriedades do Ipea (CC BY 2.5 BR no portal de dados abertos, Licença Padrão Ipea no repositório, Apache 2.0 no Extrator) divergem entre si quanto a uso comercial e obras derivadas. Uso educacional com citação da fonte é permitido nas três, que é o caso deste projeto — mas uma eventual reutilização comercial deste trabalho exigiria consultar o Ipea antes. Consultado em 2026-09-03; detalhes na seção 2.2.
8. A amostra conferida na Sprint 1 é do ano de **2024**. Os anos anteriores do SCR.data podem ter cabeçalho ou layout diferente — a Sprint 2 confere ano a ano em vez de assumir o layout de 2024.

**O que seria preciso para afirmar mais:** série de concessões com abertura por UF (não disponível publicamente), variáveis de controle regionais mensais como renda e emprego, e informação sobre a política de crédito das instituições.

---

## 12. Governança e Uso de IA

- **Linhagem:** cada execução do pipeline gera um `_load_id` único, registrado em log. Como a Gold é agregada (uma linha dela vem de milhares de linhas da Bronze), a rastreabilidade é feita **por execução**, não por registro individual — não é possível carregar um `_record_hash` único até a Gold.
- **Owner:** um integrante responsável por cada etapa (ingestão SCR, ingestão Selic, Silver, Gold, ML, documentação).
- **LGPD:** os dados usados são agregados por UF e modalidade, sem identificação de pessoa física. Nenhum dado pessoal entra em nenhuma camada.
- **Uso de IA generativa:** declarado no README — para quê foi usada e em que partes. Todo integrante precisa ser capaz de explicar qualquer trecho entregue. Código que ninguém do grupo consegue justificar conta como não entregue.
- **Fontes:** URL, data de coleta e licença de cada base citadas na seção 2 e no dicionário de dados.

---

## Anexo — Mudanças da v1 para a v2

| # | Mudança |
|---|---|
| 1 | Pergunta de pesquisa corrigida: "novos financiamentos concedidos" → "saldo e variação mensal", eliminando a contradição com a seção 11 |
| 2 | "Segmento" substituído por "modalidade" em todo o documento, com nota de vocabulário na seção 0 |
| 3 | t0 redefinido como o último mês **publicado**, não o mês corrente, por causa da defasagem de 30 dias do SCR |
| 4 | Referência quebrada à "seção 4.5" removida |
| 5 | `gold_ml_dataset` incluída na lista de tabelas |
| 6 | `_record_hash` passa a incluir `_source_object`, resolvendo o conflito entre "descartar duplicata" e "a Bronze não descarta registro" |
| 7 | Campos de licença e data de coleta marcados como pendência da Sprint 1 |
| 8 | Recorte temporal definido: julho/2016 em diante, evitando a quebra de série |
| 9 | Linhagem da Gold corrigida: por execução (`_load_id`), não por registro |
| 10 | Justificativa do split reescrita de forma direta |
| 11 | Prefixo `_` padronizado em todos os metadados |
| 12 | `.env` e menção a token do Ipeadata removidos — a API é aberta |
| 13 | Classe positiva da métrica incluída entre as decisões pendentes |
| 14 | Stack enxuta: DVC, Pandera e dotenv removidos; Docker condicionado à familiaridade do grupo |
| 15 | Seção 6 (ML) mantida no escopo, com definição adiada para a Sprint 5 |
| 16 | Plano de 6 sprints adicionado, com definição de pronto por sprint |