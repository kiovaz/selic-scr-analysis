# Definição Arquitetural do Projeto — Impacto da Selic nos Financiamentos por Estado

## 0. Contexto e Objetivo

**Problema:** entender se — e o quanto — variações na taxa Selic estão associadas ao saldo de financiamentos no Brasil, com granularidade por estado (UF) e por **modalidade** de crédito.

**Decisor final:** diretoria de crédito de uma **instituição financeira de atuação nacional**, que decide a cada trimestre em quais estados e modalidades expandir ou reduzir a oferta de financiamento. *(Decisão do grupo, 2026-09-27 — antes: "cooperativa de crédito ou financeira regional", que não combinava com um estudo dos 27 estados. O enunciado exige um decisor concreto; ver seção 10.)*

**Escopo:** pipeline de dados completo (Bronze → Silver → Gold) + análise estatística de associação (seção 5.4) + modelo preditivo (seção 6) + recomendação de decisão para o trimestre (seção 10).

**Onde os dados vivem:** filesystem local do projeto, pasta `data/` no `.gitignore`. Sem DVC. O pipeline roda inteiro localmente. Como etapa **opcional**, as tabelas finais (Gold, análise e decisão) são publicadas num banco Postgres no **Neon**, de onde um site em Next.js na **Vercel** (pasta `web/`) as mostra — decisões 12 e 16 da seção 13. Sem a string de conexão, a publicação é pulada e nada muda no resto.

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

**Frase preenchida** (Sprint 6, 2026-09-27 — números gerados pelo pipeline em `data/final/frase_fechamento.json`, impressos por `scripts/run_pipeline.py`):

> "Cruzando o **SCR.data (Banco Central)** e a **Selic meta do Copom (Ipeadata)**, identificamos que **o saldo do crédito imobiliário anda junto com a Selic de 4 meses antes (Spearman +0,42), mas a Selic não antecipa o trimestre seguinte — o que antecipa é o ritmo recente do próprio crédito em cada estado**. Recomendamos que **a diretoria de crédito de uma instituição financeira de atuação nacional** faça **a expansão da oferta de financiamento nas 20 combinações estado × modalidade com maior probabilidade de o crédito ganhar força** nos próximos **3 meses (set–nov/2026)**, priorizando **as de maior saldo dentro da lista**. Se agir, o ganho esperado é **acertar ~16,5 de 20 expansões por trimestre (82,5%), contra ~15,0 da regra simples e ~10,0 ao acaso**; se errarmos, o custo é **~3,5 expansões por trimestre em mercados que estão perdendo força — capital, captação e equipe comercial alocados sem retorno no trimestre**."

Detalhes, custos e regra de decisão na seção 10; ressalvas na seção 11.

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
| Período disponível | desde jun/2012, atualização mensal (~60 dias após o fechamento do mês — ver nota abaixo) |
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
- **`ANO_FIM` estava em 2025 e foi corrigido para 2026.** Conferido por requisição ao próprio endpoint: os ZIPs de 2024, 2025 e 2026 respondem 200; o de 2027 dá 404. O arquivo de 2026 é parcial (100,8 MiB contra 167,9 MiB de um ano cheio), porque o ano corrente só traz os meses já publicados.
- Evidência completa em `notebooks/01_exploracao_amostras.ipynb`, com as saídas gravadas.

**Conferido na primeira execução real da Bronze (2026-09-26, ZIP de 2024 baixado no mesmo dia):**

- A `bronze_scr` de 2024 ficou com **3.726.512 linhas**, e cada um dos 12 CSVs bate linha a linha com a Bronze — nenhum registro foi descartado. A diferença de 3 linhas para a contagem da Sprint 1 (3.726.515) está toda em `scrdata_202408.csv` (310.266 → 310.263): dentro do ZIP, esse arquivo tem data de **2026-09-15**, posterior à coleta de 2026-09-03, enquanto os demais meses são de 2026-03-25. Ou seja, **o BCB republica meses já publicados**. Consequência para o projeto: uma nova ingestão do mesmo ano pode trazer dados diferentes do mesmo mês, o que a Sprint 3 (idempotência) e a Silver (deduplicação na chave) precisam considerar.
- Tempo da ingestão de um ano completo: ~3 min 45 s (download de ~170 MB em ~50 s + leitura, hash e gravação).
- **A defasagem de publicação é de ~60 dias, não ~30.** Em 2026-09-26 o mês mais recente publicado era julho/2026 (`data_base` 2026-07-31); agosto ainda não havia saído. As versões anteriores deste documento falavam em ~30 dias.

**Filtro aplicado:** o SCR.data tem 13 modalidades de crédito; usamos as 8 que começam com "Financiamentos" (`modalidade LIKE 'Financiamentos%'`): financiamentos, à exportação, à importação, com interveniência, rurais e agroindustriais, imobiliários, de títulos e valores mobiliários, e de infraestrutura e desenvolvimento.

### 2.2. Base Y — Selic (Ipeadata / Ipea)

| Campo | Valor |
|---|---|
| Instituição | Instituto de Pesquisa Econômica Aplicada — Ipea |
| O que é | **Taxa Selic meta, fixada pelo Copom** |
| Série | `BM366_TJOVER366` — "Taxa de juros - Selic - fixada pelo Copom" |
| Endpoint | `http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='BM366_TJOVER366')` |
| Formato | JSON (OData v4) |
| Acesso | API REST, sem autenticação. **A API ignora `$filter`, `$top` e `$orderby`** — devolve sempre a série inteira (seção 3) |
| Unidade | **% ao ano** |
| Periodicidade | **diária, em dias corridos** (inclui fins de semana) — 11.044 registros, de jul/1996 a set/2026 (conferido em 2026-09-27) |
| Uso no projeto | **corte mensal:** a meta vigente no **último dia** de cada mês (feito na Silver) |
| Campos | `SERCODIGO`, `VALDATA`, `VALVALOR` — a API devolve também `NIVNOME` e `TERCODIGO`, vazios |
| Licença | Sem termo único publicado no Ipeadata — ver ressalva abaixo. Uso educacional permitido e **citação da fonte obrigatória** nas três declarações do Ipea |
| **Data de coleta** | **2026-09-03** (série antiga) e **2026-09-27** (série atual) |

**Por que não a série acumulada no mês (`BM12_TJOVER12`)** *(decisão do grupo, 2026-09-27 — change `troca-serie-selic`)*. Até a Sprint 4 o projeto usou a `BM12_TJOVER12`, a Selic **acumulada no mês, em % ao mês**. Ela foi descartada porque **varia com o número de dias úteis do mês**, não só com a decisão do Copom: com a taxa parada, um mês de 22 dias úteis acumula mais juros que um de 20. Evidência medida nos 120 meses do recorte:

- a variação mensal da série tem **correlação de Spearman de 0,79 com a variação do número de dias úteis**;
- exemplo real — a série antiga **subiu** quando o Copom **cortou**:

| Mês | Série antiga (acumulada, % a.m.) | Dias úteis | Meta do Copom no fim do mês (% a.a.) |
|---|---|---|---|
| fev/2026 | 1,00 | 20 | 15,00 |
| mar/2026 | **1,21 ↑** | 22 | **14,75 ↓** |

Com a série antiga, a variação da Selic media sobretudo o calendário, e a análise comparava o crédito com os dias úteis. A meta do Copom é o que a pergunta de pesquisa chama de "ciclos de alta e baixa": ela só muda nas reuniões, então cada variação mensal diferente de zero é uma decisão identificável (ex.: −0,25 p.p. em mar/2026). A Selic over efetiva diária (`GM366_TJOVER366`) também existe, mas oscila com o mercado; a meta é o sinal de política.

**Só meses fechados.** A meta vigente no último dia de um mês só é conhecida depois que o mês termina; o mês em curso nunca entra na Silver.

**Licença — consultado em 2026-09-03.** Nem o `ipeadata.gov.br` nem a página da sua API publicam termos de uso. O que existe são três declarações diferentes, em propriedades distintas do Ipea:

| Onde | O que diz |
|---|---|
| [ipea.gov.br/portal/dados-abertos](https://www.ipea.gov.br/portal/dados-abertos) | "Todo o conteúdo deste site está publicado sob a licença **Creative Commons Atribuição 2.5 Brasil**." |
| [repositorio.ipea.gov.br](https://repositorio.ipea.gov.br/handle/11058/2206) (registro IPEADATA) | **Licença Padrão Ipea**: reprodução e exibição para uso educacional ou informativo, com crédito e citação da fonte; proíbe uso comercial e obras derivadas. |
| [ipea.gov.br/extrator/termos_condicoes.html](https://www.ipea.gov.br/extrator/termos_condicoes.html) (outra ferramenta) | Apache 2.0 para o software; obrigatória a citação da fonte do dado. |

O denominador comum das três é o que vale para este projeto: **uso educacional é permitido e a citação da fonte é obrigatória**. Sendo um trabalho acadêmico, sem fim lucrativo e sem redistribuição do dado bruto, o uso está coberto mesmo pela leitura mais restritiva. A divergência entre as três está registrada na seção 11 (Limitações Conhecidas).

**Nota de proveniência:** o Ipeadata redistribui a série originalmente produzida pelo Banco Central. Instituição mantenedora distinta, origem primária a mesma. Isso deve constar explicitamente no dicionário de dados.

### 2.3. Recorte temporal

**Definido: julho/2016 a junho/2026 — 120 meses, exatamente 10 anos, nas duas bases.** *(Decisão do grupo registrada em 2026-09-27; antes o fim era "a última competência publicada do SCR".)*

Justificativa do início: o SCR.data tem uma quebra de série em junho/2016, quando o limite de identificação das operações caiu de R$ 1.000 para R$ 200. Começar em julho/2016 evita comparar períodos com réguas diferentes.

Justificativa do fim:

- **Fim fixo, não móvel.** Com "até o último mês publicado", o resultado mudaria a cada publicação mensal do BCB. Com uma data fixa, quem rodar o pipeline depois chega aos mesmos números da entrega (reprodutibilidade).
- **Só meses fechados.** Nas duas fontes o dado fecha mês a mês: a Selic acumulada no mês é definitiva quando o mês termina, e o SCR de cada mês é a foto do saldo no último dia daquele mês. Em 2026-09-27, jun/2026 estava fechado e publicado nas duas bases.
- **Dez "anos de estudo" completos, de julho a junho** (jul/2016–jun/2017, …, jul/2025–jun/2026). Qualquer visão por ano usa essa contagem de julho a junho, e nenhum período fica pela metade.
- O recorte cobre um ciclo completo de juros (Selic alta em 2016, mínima histórica em 2020-21, alta de novo em 2022-23), que é exatamente o que a pergunta precisa.

A Bronze continua guardando tudo o que as fontes entregam (inclusive meses fora do recorte); o corte é aplicado na Silver, usando `ANO_INICIO/MES_INICIO` e `ANO_FIM/MES_FIM` do `config.py`.

**Cuidado conhecido:** o BCB pode republicar meses já publicados (ver 2.1, ago/2024). Uma revisão dentro do recorte muda os números da análise; a detecção de republicação é escopo da Sprint 3.

### 2.4. Cruzamento

- **Chave:** `ano_mes`.
- A Selic é nacional: o mesmo valor se repete para as 27 UFs em cada mês. Isso é esperado e deve estar documentado — não é erro de join.
- **Órfãos a tratar e reportar:**
  - meses da Selic sem SCR e meses do SCR sem Selic. Com o recorte fixo em jul/2016–jun/2026, os dois lados devem ter os mesmos 120 meses depois do corte da Silver; qualquer órfão dentro do recorte é problema a investigar, não defasagem esperada.
  - A contagem exata dos dois lados entra na entrega final.

---

## 3. Arquitetura de Ingestão

| Forma | Fonte | Detalhes obrigatórios |
|---|---|---|
| **Arquivo** | SCR.data | Baixa o ZIP, descompacta, lê o CSV tratando encoding, separador `;` e tipagem explícita |
| **API REST** | Ipeadata (Selic) | Requisição com timeout, tratamento de erro e retry com backoff. **Sem paginação:** a API do Ipeadata não oferece paginação — `$top` e `$skip` são ignorados e a série inteira vem numa resposta (~11 mil registros, conferido em 2026-09-27). O Requisito 2 do enunciado ("API com paginação") é atendido na medida do que a fonte permite; o volume é pequeno e a carga incremental (watermark) evita regravar o que já existe |
| **Carga incremental** | Ipeadata (Selic) | Guarda a última data já ingerida numa tabela de controle (watermark). A API do Ipeadata **ignora** `$filter`, `$top` e `$orderby` (conferido em 2026-09-27: devolve sempre a série inteira, ~60 KB), então a carga baixa a série e **grava só o que falta**: registros a partir do watermark cujo hash ainda não está na Bronze |
| **Controle de versão** | SCR.data | Antes de baixar, lê o `ETag` do ZIP com uma requisição `HEAD` (sem baixar) e compara com a tabela de controle. Se o ZIP mudou, compara o CRC32 e a data de cada CSV no índice do ZIP e ingere só os CSVs novos ou alterados |

As tabelas de controle ficam em `data/raw/_controle/` (`controle_scr.json` e `controle_selic.json`), fora do Git como todo o `data/`.

### 3.1. Metadados técnicos da Bronze

Obrigatórios em toda linha, sempre com prefixo `_`:

`_ingestion_timestamp`, `_ingestion_date`, `_source_system`, `_source_object`, `_load_id`, `_ingestion_mode` (`full` | `incremental`), `_record_hash`.

### 3.2. Idempotência

`_record_hash` é o hash SHA-256 do **conteúdo do registro concatenado com `_source_object`**.

Incluir o arquivo de origem no hash é intencional: garante que duas linhas de conteúdo idêntico vindas de arquivos diferentes sejam preservadas, e que só o reprocessamento do **mesmo arquivo** seja descartado. Sem isso, linhas legítimas duplicadas dentro da fonte sumiriam, o que violaria a regra de que a Bronze não descarta registro.

Rodar a ingestão duas vezes seguidas não pode alterar a contagem final de linhas. Isso será demonstrado ao vivo na defesa e coberto por teste automatizado (`test_idempotencia.py`).

**Versões republicadas** *(Sprint 3, 2026-09-27)*. O BCB republica meses já publicados (ver 2.1: `scrdata_202408.csv` regravado em 2026-09-15). Por isso, no SCR, `_source_object` identifica a **versão** do arquivo: `scrdata_202408.csv@2026-09-15T02:38:32` (nome + data do arquivo dentro do ZIP). Consequências:

- Uma versão republicada entra **completa** na Bronze — sem a versão no `_source_object`, as linhas que não mudaram teriam o mesmo hash da versão antiga e seriam tratadas como "já ingeridas", deixando o mês incompleto.
- A versão anterior **continua guardada**: a Bronze é imutável (4.1).
- **Regra da Silver:** para cada arquivo do SCR (`_source_object` antes do `@`), usar só a versão mais recente; para cada mês da Selic, usar só a leitura mais recente (`_ingestion_timestamp`) — o mês corrente da Selic muda de valor até fechar, e cada valor novo entra como uma linha nova.

**Execução interrompida.** A tabela de controle marca cada versão como `em_andamento` antes de gravar e `completo` depois. Se a próxima execução encontrar uma versão `em_andamento`, grava só as linhas daquela versão cujo `_record_hash` ainda não está na Bronze. Se a tabela de controle for perdida, ela é reconstruída a partir dos `_source_object` presentes na Bronze.

**Demonstração:** `python scripts/conferir_bronze.py` → `python scripts/run_pipeline.py` → `python scripts/conferir_bronze.py`: as contagens não mudam e a chave `(_source_object, _record_hash)` não tem duplicata.

### 3.3. Quarentena

Registro com estado inválido, data fora do intervalo, valor negativo ou tipo errado vai para uma tabela separada, com o motivo e o registro original preservados. O job nunca quebra por causa de dado sujo.

**Onde a quarentena acontece: na Silver, não na ingestão.** *(Decisão do grupo registrada em 2026-09-26, na mudança `correcoes-ingestao-bronze`.)* A Sprint 2 tinha colocado a validação e a quarentena dentro dos loaders da Bronze. Isso contrariava a seção 4.1 — a Bronze não descarta registro — e tinha um risco concreto: se uma regra de validação tivesse bug (por exemplo, rejeitar um mês inteiro por engano), o registro sumia da Bronze, e reprocessar depois de corrigir a regra não o traria de volta, porque o reprocessamento sempre parte da Bronze.

Por isso:

- **Bronze:** grava todo registro que conseguiu ler, sujo ou não. Só rejeita o que é **ilegível** — CSV sem as colunas esperadas, resposta da API que não é JSON OData — e registra o motivo em log (não na quarentena, porque não há registro para preservar).
- **Silver:** aplica as checagens de `src/validation/quality_checks.py` e envia o registro inválido para `data/raw/_quarentena/` com o motivo padronizado. O registro original continua na Bronze.

**Como a quarentena da Silver funciona** *(Sprint 4, 2026-09-27)*:

- Vai para a quarentena só o que é **inválido**: UF fora da lista, valor que não é número/data, valor negativo (exceto o `-1` de `numero_de_operacoes`, que é máscara), data posterior à execução, e leituras ambíguas da Selic (`duplicata_na_chave`).
- O que está só **fora do escopo** — outras modalidades, meses fora do recorte, versões antigas de meses republicados — **não** vai para a quarentena: é filtrado e contado no relatório da Silver (`data/processed/_relatorio_silver.json`). Não é dado errado, é dado que o projeto não usa.
- A quarentena de cada tabela Silver (`data/raw/_quarentena/silver_scr.parquet`, `silver_selic.parquet`) é **refeita a cada execução**, como a própria Silver — reprocessar não duplica registros rejeitados.

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

**O que "dado como veio" significa na prática** *(decisão registrada em 2026-09-26, mudança `correcoes-ingestao-bronze`)*: a Bronze guarda **todas** as colunas do CSV do SCR (24) e **todos** os campos da API da Selic, **como texto**, sem converter tipo nem separador decimal e sem recorte de período. Das 24 colunas do SCR, só as 5 de `SCR_COLUNAS_USADAS` viram Silver — esse corte, a tipagem e o recorte a partir de jul/2016 são feitos na Silver. Motivo: se a Silver um dia precisar de mais uma coluna (por exemplo `porte`), basta reprocessar a partir do disco, sem baixar de novo ~2 GB do BCB.

### 4.2. Tabelas do projeto

| Camada | Tabela | Uma linha por… | Chave primária |
|---|---|---|---|
| Bronze | `bronze_scr` | linha do CSV original | `(_source_object, _record_hash)` |
| Bronze | `bronze_selic` | data da série | `(_source_object, _record_hash)` |
| Silver | `silver_scr` | mês × estado × modalidade | `(ano_mes, uf, modalidade)` |
| Silver | `silver_selic` | mês | `(ano_mes)` |
| Gold | `gold_credito_selic` | mês × estado × modalidade | `(ano_mes, uf, modalidade)` |
| Gold | `gold_ml_dataset` | combinação UF × modalidade × mês de origem | `(uf, modalidade, origem)` |

**Prova obrigatória de ausência de duplicata na chave:**
```python
assert df.duplicated(["ano_mes", "uf", "modalidade"]).sum() == 0
```

---

## 5. Modelagem de Dados

### 5.1. Dicionário — `silver_scr`

| Coluna | Tipo | Domínio | Origem | Significado |
|---|---|---|---|---|
| `ano_mes` | date | jul/2016 a jun/2026, **primeiro dia do mês** | `data_base` | mês de referência (o SCR usa o último dia; normalizado para o primeiro, igual à Selic) |
| `uf` | string(2) | 27 estados | `uf` | estado do tomador (CEP de residência para PF, sede para PJ) |
| `modalidade` | string | 8 modalidades de financiamento | `modalidade` | tipo de financiamento |
| `qtd_operacoes` | integer | ≥ 0 | `numero_de_operacoes` | soma das quantidades **divulgadas** do grupo — **limite inferior** da quantidade real (ver nota abaixo) |
| `linhas_qtd_nao_divulgada` | integer | ≥ 0 | `numero_de_operacoes` | quantas linhas do grupo vieram com `-1` (quantidade escondida pelo BCB) |
| `volume_rs` | decimal | ≥ 0 | `carteira_ativa` | saldo em R$ nominais — completo, **indicador principal da análise** |

**Quantidade como limite inferior** *(decisão do grupo, 2026-09-27)*. Cada grupo mês × UF × modalidade soma várias linhas do CSV (abertas por cliente, porte, indexador etc.). O BCB esconde a quantidade de algumas linhas com `-1`, mas divulga o saldo delas. No perfil da Bronze real: 28,1% das linhas de financiamento têm `-1`, carregando 10,8% do saldo, e **99,9% dos grupos têm ao menos uma linha com `-1`**. Transformar o grupo em nulo apagaria a quantidade do projeto inteiro. Por isso: `qtd_operacoes` soma só o que foi divulgado (o número real é maior ou igual), `linhas_qtd_nao_divulgada` mostra o quanto está escondido, e a análise usa o **volume** como indicador principal. Ver limitação 9 na seção 11.

### 5.2. Dicionário — `silver_selic`

| Coluna | Tipo | Domínio | Origem | Significado |
|---|---|---|---|---|
| `ano_mes` | date | jul/2016 a jun/2026, **primeiro dia do mês** | `VALDATA` | mês de referência (leitura mais recente de cada mês; nunca um mês não fechado) |
| `selic_pct` | decimal | > 0 | `VALVALOR` | **Selic meta do Copom vigente no último dia do mês, % ao ano** |

### 5.3. Dicionário — `gold_credito_selic`

| Coluna | Tipo | Origem | Significado |
|---|---|---|---|
| `ano_mes` | date | Silver | mês (primeiro dia) |
| `uf` | string(2) | Silver | estado |
| `modalidade` | string | Silver | tipo de financiamento |
| `qtd_operacoes` | integer | Silver | quantidade de operações divulgadas — **limite inferior** (5.1) |
| `linhas_qtd_nao_divulgada` | integer | Silver | linhas do grupo com a quantidade escondida pelo BCB |
| `volume_rs` | decimal | Silver | saldo em R$ — indicador principal |
| `tem_mes_anterior` | boolean | derivada | a combinação tem linha no mês imediatamente anterior? Se não, as variações ficam vazias |
| `var_qtd_pct` | decimal | derivada | variação % da quantidade vs. mês anterior. Vazia sem mês anterior **ou** quando a quantidade anterior é 0 |
| `var_volume_pct` | decimal | derivada | variação % do volume vs. mês anterior. Vazia sem mês anterior |
| `selic_pct` | decimal | Silver | Selic meta do mês (% a.a., último dia do mês) — a mesma para todas as UFs e modalidades do mês |
| `var_selic_pp` | decimal | derivada | **decisão do Copom no mês**: variação da meta vs. mês anterior, em pontos percentuais ao ano (0 se não houve mudança) |
| `selic_lag_1` … `selic_lag_6` | decimal | derivada | Selic meta de 1 a 6 meses antes, **pelo calendário** |

**Regra de cálculo:** variações e lags são calculados separadamente por estado e modalidade, ordenados por mês — nunca misturando combinações diferentes. Os primeiros meses de cada combinação ficam nulos por definição; isso não é preenchido artificialmente.

**Variação só entre meses consecutivos** *(decisão do grupo, 2026-09-27)*. 42 combinações UF × modalidade têm buracos no meio da série (meses sem nenhuma operação). A variação só é calculada quando a combinação tem linha no mês **imediatamente anterior** pelo calendário (`tem_mes_anterior`); caso contrário fica vazia — nunca se compara com um mês mais antigo nem se preenche o buraco. `var_qtd_pct` fica vazia também quando a quantidade anterior é 0 (7.945 grupos em que toda a quantidade estava escondida). A Selic é nacional e não tem buracos: `var_selic_pp` e `selic_lag_k` são calculados na série da Selic pelo calendário, então uma combinação com buraco ainda recebe a Selic certa de k meses antes. Os meses de jul a dez/2016 ficam sem parte dos lags, porque a `silver_selic` começa em jul/2016.

### 5.4. Regras de análise estatística

- Comparar **variações**, não níveis absolutos. Selic e crédito têm tendência de crescimento própria; comparar níveis gera correlação alta que não significa nada (correlação espúria).
- Testar a Selic defasada em 1 a 6 meses — o crédito reage com atraso a mudanças de juros.
- Rodar a análise separadamente por modalidade. Financiamento imobiliário e rural têm juros subsidiados e indexadores próprios, e reagem menos à Selic por construção.
- Reportar como **associação**, nunca como causa.

**Como a análise é feita** *(Sprint 4, decisões do grupo de 2026-09-27)*:

- **Dois níveis.** (1) **Brasil por modalidade**: soma o `volume_rs` das 27 UFs em cada mês, calcula a variação nacional e mede a associação com a variação da Selic no mesmo mês e com 1 a 6 meses de defasagem (8 modalidades × 7 defasagens = 56 medidas). (2) **UF × modalidade**: a mesma medida para cada combinação, num mapa de calor que mostra onde o crédito reage mais.
- **Medida: correlação de Spearman** (compara a ordem dos valores), com a de Pearson ao lado. Spearman é menos sensível a meses extremos, comuns nas combinações pequenas.
- **Defasagem no mapa de calor:** cada combinação é medida só na defasagem de maior associação **da sua modalidade no nível Brasil**. Escolher a melhor defasagem combinação por combinação seria escolher o resultado a dedo (1.512 testes).
- **Amostra mínima:** combinações com menos de 24 meses válidos não têm correlação calculada ("amostra insuficiente").
- **Muitos testes:** os valores-p são ajustados por Benjamini-Hochberg, separadamente em cada nível; só é "significativo" o que tem valor-p **ajustado** < 0,05.
- Código em `src/analise/correlacao.py`; resultados em `data/final/`; figuras em `docs/figuras/`; explicação em `notebooks/02_analise_estatistica.ipynb`.

---

## 6. Base ML-Ready e Anti-Vazamento

> **Status: definido na Sprint 5 (2026-09-27)**, antes de qualquer código de treino, com números medidos na Gold real. Change `modelo-ml`.

### 6.1. Definição do problema

**A pergunta:** *"o crédito desta combinação UF × modalidade vai **ganhar força** no próximo trimestre que o decisor ainda pode usar?"* — ganhar força = o saldo crescer **mais** no trimestre futuro do que cresceu nos últimos 3 meses. Continuar crescendo, só que mais devagar, é **perder força**.

| Elemento | Definição |
|---|---|
| **Tipo de problema** | Classificação binária |
| **Label** | `ganha_forca` = 1 (**classe positiva = ganha força = expandir**); 0 = perde força (cuidado ao expandir). Conhecido quando o BCB publica o mês t+5 (~t+7) |
| **Regra de rotulagem** | `ganha_forca = (volume[t+5] / volume[t+2] − 1) > (volume[t] / volume[t−3] − 1)` por combinação, com `volume` = `volume_rs` da Gold |
| **Coorte** | As **174** combinações UF × modalidade com os 120 meses do recorte (99,995% do volume). As 42 com meses sem operação ficam de fora (as features exigiriam meses inexistentes). Filtro aplicado antes do split |
| **Janela de observação** | Até 12 meses antes da origem t, **inclusive t** (variações de 1, 3, 6 e 12 meses, aceleração, posição relativa ao Brasil, participação, Selic meta e decisões do Copom nos 3 e 6 meses anteriores, UF, modalidade) |
| **Janela de predição** | De **t+2 a t+5**. A folga de 2 meses existe porque o SCR é publicado ~60 dias depois: quando o dado de t chega ao decisor, t+1 e t+2 já passaram |
| **Baseline** | Classe majoritária e **"volta ao normal"** — prevê "ganha força" quando o crédito perdeu força nos últimos 3 meses. Acerta **64,7%** (medido na Gold): é a régua a vencer |
| **Métrica** | **AUC** (principal — ordena quem vai ganhar força, sem depender do limiar, que é da Sprint 6); **precisão nas 20 melhores apostas** de cada mês (como o decisor usa); **AUC pesada pelo volume**; precisão/recall da classe positiva. Classes equilibradas (~50%), então a acurácia também é legível |

**Números que embasaram a definição** (Gold real, coorte, 2026-09-27): ~19 mil exemplos; 50,1% "ganha força"; a Selic **sozinha** tem AUC ≈ 0,51 (0,49–0,54 por modalidade) — quase não antecipa o próximo trimestre. Por isso o modelo é avaliado **com e sem** as variáveis da Selic.

**Versão descartada da pergunta** (mesmo dia): "a combinação vai crescer **mais que o Brasil** na mesma modalidade, de t a t+3?". Trocada porque, ao comparar cada estado com a média do país, o efeito da Selic — igual para todos — **se cancela**, e porque t→t+3 ignora o atraso de publicação.

**Avaliação:** janela móvel por ano (blocos de origens 2020–2023, cada um previsto por um modelo treinado até 6 meses antes) para escolher o modelo e medir estabilidade; teste final único nas origens fev/2025–jan/2026, com treino até ago/2024 e **embargo de 5 meses** (set/2024–jan/2025), porque o rótulo olha até t+5.

### 6.2. Decisões já fechadas (valem para qualquer opção)

**Ponto de corte (t0):** o último mês **publicado** do SCR.data, não o mês corrente.

Com o recorte fixo da seção 2.3, **t0 = junho/2026**, o último mês do recorte (já publicado na data da análise). A previsão de produção sai da origem t0 e cobre **set a nov/2026** (t0+2 a t0+5). Isso é deliberado. O SCR.data sai com cerca de 60 dias de atraso, então no momento real da decisão o dado do mês corrente ainda não existe. Usar o mês corrente como t0 seria dar ao modelo uma informação que na prática ele não teria — vazamento operacional.

**Split: temporal.** Treino nos meses mais antigos, teste nos mais recentes.

Justificativa: o objetivo é prever os **mesmos estados e modalidades** em meses futuros, não generalizar para estados novos. Como não existe risco de uma entidade nova aparecer no teste, separar por tempo basta. Split por grupo não se aplica.

### 6.3. Checklist Anti-Vazamento

Respondido na Sprint 5 (2026-09-27), com a evidência de cada item. Detalhes em `notebooks/03_modelo.ipynb`.

- [x] **Toda feature existia antes do t0?** Sim — as features de uma origem t usam só meses ≤ t; a produção usa só dados até jun/2026. *Evidência:* `src/ml/dataset.py` (só `shift` para trás nas features); teste `test_mexer_no_futuro_nao_muda_as_features`.
- [x] **As agregações (lags, médias móveis) foram calculadas apenas com dados anteriores ao t0 de cada observação?** Sim — variações, aceleração, participação e Selic partem da própria origem para trás. *Evidência:* o mesmo teste (alterar volume e Selic depois da origem não muda nenhuma feature).
- [x] **O split respeita a ordem temporal? Nenhum mês de teste aparece antes de um mês de treino?** Sim, com **embargo de 5 meses** (set/2024–jan/2025) porque o rótulo olha até t+5; na janela móvel, cada ano é treinado só até julho do ano anterior. *Evidência:* `marcar_conjunto` e `janela_movel`; teste `test_conjuntos_sem_sobreposicao_e_chave_unica`.
- [x] **O split respeita tempo e grupo? Nenhuma entidade aparece em treino e teste ao mesmo tempo?** *(pergunta do enunciado)* O split é **temporal**. As mesmas 174 combinações aparecem em treino e em teste **de propósito**: o objetivo é prever o futuro dessas mesmas entidades, não generalizar para estados novos (seção 6.2). O que não pode se misturar é o **tempo**, e o embargo de 5 meses garante que nenhum mês usado por um rótulo de treino esteja no período de teste. Split por grupo não se aplica. *Evidência:* `test_conjuntos_sem_sobreposicao_e_chave_unica`.
- [x] **Imputadores foram ajustados somente no treino?** *(pergunta do enunciado)* **Não há imputação.** Origens sem 12 meses de histórico são excluídas da base, e as 42 combinações com meses faltando ficam fora da coorte — nada é preenchido. *Evidência:* `dropna` em `montar_base` e `definir_coorte` (`src/ml/dataset.py`).
- [x] **Scalers e encoders foram ajustados (`fit`) somente no treino, com apenas `transform` em teste?** Sim — pré-processamento e modelo num único `Pipeline`, ajustado só nas linhas de treino de cada avaliação. *Evidência:* `montar_pipeline` em `src/ml/treino.py`; teste `test_padronizacao_ajustada_so_no_treino`.
- [x] **A coluna que dá origem ao label foi removida das features?** Sim — o volume de t+2 e t+5 só aparece no rótulo; a quantidade de operações nem entra (limite inferior, 5.1). *Evidência:* `FEATURES_NUMERICAS` em `src/ml/dataset.py`.

Verificações extras: a escolha do modelo não muda se os rótulos do teste forem invertidos (`test_rotulos_do_teste_nao_mudam_a_escolha`); métrica acima de 0,95 gera alerta (`test_base_perfeita_dispara_alerta`) — nenhum alerta na execução real.

### 6.5. Resultado do modelo (Sprint 5, 2026-09-27)

- **Escolhido:** gradient boosting (`HistGradientBoostingClassifier`), AUC média 0,752 na janela móvel 2020–2023 (regressão logística: 0,722).
- **Teste final (fev/2025–jan/2026, usado uma vez):** AUC **0,778** contra **0,688** da "volta ao normal" — **supera o baseline**. Nas 20 melhores apostas de cada mês, acerta **82,5%** (volta ao normal: 75,0%). AUC pesada pelo volume: 0,792.
- **A Selic não ajuda a prever:** o mesmo modelo **sem** as variáveis da Selic teve AUC 0,796 no teste; a diferença "com − sem" oscila em torno de zero nos anos (+0,007, +0,035, −0,067, −0,034). O que prevê é a dinâmica do próprio crédito — sobretudo o crescimento dos últimos 3 meses (volta ao normal refinada). Coerente com a Sprint 4: a Selic está **associada** ao crédito, mas não **antecipa** o trimestre seguinte.
- **Previsão de produção:** probabilidade de cada uma das 174 combinações ganhar força em set–nov/2026 (`data/final/ml_previsao_producao.parquet`). As probabilidades mais extremas estão em combinações pequenas; o limiar de decisão é da Sprint 6 (seção 10).

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
| **Neon (Postgres) + `psycopg` + `python-dotenv`** | publicação opcional das tabelas finais (decisão 16). O `python-dotenv` lê a string de conexão do `.env`, que fica fora do Git |
| **Next.js na Vercel** (`web/`) | site só de leitura, em página única: decisão, recomendação, Selic × crédito (com o mapa de calor por estado), modelo, exploração por estado e modalidade e sobre os dados (decisão 17) |
| **GitHub Actions** | roda os testes a cada push. Custo de setup baixo (um YAML), e mostra na prática que o pipeline não quebrou |
| **Git** | exigido |

### 7.2. O que sai

| Item | Por que foi cortado |
|---|---|
| **DVC** | O enunciado exige apenas que os dados não vão para o Git. `data/` no `.gitignore` já resolve, de graça. DVC sem um remote configurado é overhead sem benefício |
| **Great Expectations / Pandera** | As validações deste projeto (domínio de UF, tipos, faixas, duplicata) cabem em funções simples em `src/validation/`, cobertas por pytest. Uma biblioteca declarativa a mais é uma coisa a mais para todo mundo saber explicar |
| **Black / Flake8 como obrigatórios** | Podem entrar no CI se o grupo quiser, mas não valem ponto e não são bloqueantes |
| **Docker + `docker-compose.yml`** | O enunciado já é satisfeito por `venv` + `requirements.txt` com versões fixadas + README, e o CI confirma o ambiente a cada push. Mantido na Sprint 1 como alternativa ao venv; removido na Sprint 6 (decisão 15) |

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
- Módulo de quarentena (`src/validation/quality_checks.py`) com os motivos padronizados, pronto para a Silver usar
- Escrita em `data/raw/`, particionada por data

**Pronto quando:** os dois loaders rodam do zero e produzem `bronze_scr` e `bronze_selic` em disco; um registro sujo injetado de propósito entra intacto na Bronze sem derrubar o job; e um arquivo ilegível é rejeitado com log.

> *Revisado em 2026-09-26 (mudança `correcoes-ingestao-bronze`).* A versão original dizia que o registro sujo "cai na quarentena" já na ingestão. O grupo decidiu que a quarentena acontece na Silver (seção 3.3). A sprint não foi desfeita: o módulo de quarentena continua existindo; só mudou quem o chama.

### Sprint 3 — Idempotência, incremental e CI

- `_record_hash` implementado conforme a seção 3.2
- Carga incremental por watermark na Selic, com tabela de controle
- `tests/test_idempotencia.py` e `tests/test_no_duplicates.py`
- GitHub Actions rodando `pytest` a cada push

**Pronto quando:** rodar o pipeline duas vezes seguidas não muda a contagem de linhas, e o CI está verde no repositório.

### Sprint 4 — Silver e Gold

- `silver_scr` e `silver_selic` com tipagem, deduplicação e validações
- Seleção das 5 colunas de `SCR_COLUNAS_USADAS` e recorte a partir de jul/2016 (a Bronze guarda tudo — seção 4.1)
- Quarentena por regra de negócio, com os motivos padronizados (seção 3.3), incluindo o descarte do mês corrente incompleto da Selic
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
- Ensaio da defesa: cada integrante explica um trecho sorteado do código

**Pronto quando:** alguém de fora do grupo consegue rodar o pipeline seguindo só o README.

---

## 9. Organização do Repositório

```
projeto-selic-credito/
├── README.md
├── requirements.txt
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
│   ├── analise/                  # Sprint 4: correlações e gráficos
│   │   └── correlacao.py
│   ├── ml/                       # Sprint 5
│   ├── publicacao/               # envio opcional ao Neon (decisão 16)
│   │   └── neon.py
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
├── web/                         # site Next.js (Vercel) — lê o Neon
│
└── docs/
    ├── architecture.md           # este arquivo
    ├── data_dictionary.md        # seção 5 consolidada
    └── figuras/                  # gráficos da análise (versionados: são entregáveis)
```

**Estratégia Git:** `main` estável, branches de feature por membro, merge via Pull Request. Commits atômicos no formato `tipo: descrição breve` (`feat:`, `fix:`, `docs:`, `test:`).

**Commits distribuídos entre os integrantes ao longo do tempo.** Um repositório com tudo no último dia e um autor só é tratado como trabalho de uma pessoa.

**`.gitignore`** cobrindo `data/`, `*.csv`, `*.zip`, `*.parquet`, `__pycache__/`, `.venv/`, `.env` (credenciais) e as pastas geradas do site (`web/node_modules`, `web/.next`).

---

## 10. Decisão de Negócio

- **Decisor:** diretoria de crédito de uma **instituição financeira de atuação nacional** (decisão 13, seção 13).
- **Ação possível:** a cada trimestre, **expandir** (ou manter, ou reduzir) a oferta de financiamento em combinações estado × modalidade — orçamento de captação e marketing, metas regionais e alocação da equipe comercial.
- **O que o modelo entrega:** para cada uma das 174 combinações, a probabilidade de o crédito **ganhar força** no trimestre que ainda está pela frente quando o dado é publicado (seção 6.1).
- **Custo de falso positivo** (expandir onde o crédito vai perder força): orçamento e captação alocados sem retorno no trimestre, equipe comercial deslocada, meta regional não batida e pressão para afrouxar o padrão de concessão para "preencher" volume. **É imediato e fica no balanço do trimestre.**
- **Custo de falso negativo** (não expandir onde o crédito vai ganhar força): receita não capturada e espaço cedido a concorrentes, com custo de reentrada depois. **É de oportunidade e diluído no tempo.**
- **Limiar adotado** (decisão 14): **a cada trimestre, expandir nas 20 combinações com maior probabilidade** — uma lista de tamanho fixo, em vez de uma nota mínima.
  - **Por quê — ligando a métrica à consequência:** como o falso positivo custa mais no curto prazo, a regra privilegia a **precisão** (acertar onde se expande) e aceita um recall baixo (deixar oportunidades de fora). No teste (fev/2025–jan/2026), as 20 maiores notas de cada mês acertaram **82,5%** — ~16,5 expansões certas e ~3,5 erradas por trimestre —, contra **75,0%** da regra simples ("volta ao normal") e **50,1%** ao acaso.
  - Uma lista fixa combina com a capacidade de execução de uma diretoria (número de frentes, não uma probabilidade) e não depende de as notas estarem calibradas.
  - **Sensibilidade** (teste, `data/final/sensibilidade_limiar.parquet`): nota ≥ 0,5 recomendaria ~107 combinações/mês com 67,7% de acerto; ≥ 0,8, ~48 com 76,2%; ≥ 0,9, ~15 com 84,8%; listas de 10 e 40 acertaram 79,2% e 77,5%. A lista de 20 equilibra acerto e alcance.
- **Recomendação para set–nov/2026** (`data/final/recomendacao_trimestre.parquet`): as 20 combinações a expandir somam **R$ 557,5 bilhões** de saldo em jun/2026; a lista também traz as 20 com maior risco de perder força, como alerta. **Leitura:** 9 das 20 são financiamentos **rurais** — coerente com o plantio da safra de verão no período, que o modelo capta pelo ritmo recente do crédito (sazonalidade não é modelada explicitamente, limitação 11). As notas mais altas da lista estão em mercados **pequenos** (exportação e importação em estados menores); por isso a recomendação é **priorizar as de maior saldo dentro da lista** (limitação 13).
- **Frase de decisão final:** preenchida na seção 1, com os números do pipeline.

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

9. **A quantidade de operações é subestimada.** O BCB esconde a quantidade (`-1`) de 28% das linhas de financiamento; a Silver soma só as divulgadas (`qtd_operacoes` é limite inferior) e registra quantas linhas estavam escondidas. Se a proporção escondida muda de um mês para o outro, a variação da quantidade mistura variação real com variação da máscara — por isso o **volume** é o indicador principal (seção 5.1).
10. **Nem toda combinação UF × modalidade existe em todos os meses.** No recorte, 42 das 216 combinações têm meses sem nenhuma linha — meses em que não havia nenhuma operação daquele tipo naquele estado. São combinações minúsculas (0,005% do volume). A Silver não preenche esses meses; a Gold só pode calcular variação entre meses consecutivos.
11. **Sazonalidade não é tratada.** O crédito tem padrão sazonal (por exemplo, o rural acompanha a safra) e a Selic não; isso pode diluir a associação medida. Um ajuste sazonal fica como evolução possível.
12. **A Selic não antecipa o trimestre seguinte.** O modelo com e sem as variáveis da Selic tem desempenho equivalente (seção 6.5): ela está associada ao crédito (seção 5.4), mas não ajuda a prever se o crédito de um estado vai ganhar força nos 3 meses seguintes.
13. **Probabilidades extremas em mercados pequenos.** As maiores e menores notas do modelo aparecem em combinações de saldo pequeno (exportação, importação, títulos em estados menores), que oscilam muito. Por isso a lista de recomendação mostra o saldo de cada combinação.
14. **Avaliação final em 12 meses.** O teste final cobre fev/2025–jan/2026, um único regime de juros altos; a janela móvel (2020–2023) dá a leitura de estabilidade, mas o desempenho futuro pode variar.
15. **Rótulos sobrepostos e choques comuns.** Previsões de meses seguidos compartilham meses do trimestre futuro, e todas as combinações sofrem os mesmos choques no mês — as métricas parecem mais firmes do que são (seção 6, notebook 03).

**O que seria preciso para afirmar mais:** série de concessões com abertura por UF (não disponível publicamente), variáveis de controle regionais mensais como renda e emprego, e informação sobre a política de crédito das instituições.

---

## 12. Governança

- **Linhagem:** cada execução do pipeline gera um `_load_id` único, registrado em log. Como a Gold é agregada (uma linha dela vem de milhares de linhas da Bronze), a rastreabilidade é feita **por execução**, não por registro individual — não é possível carregar um `_record_hash` único até a Gold.
- **Owner:** um integrante responsável por cada etapa (ingestão SCR, ingestão Selic, Silver, Gold, ML, documentação).
- **LGPD:** os dados usados são agregados por UF e modalidade, sem identificação de pessoa física. Nenhum dado pessoal entra em nenhuma camada.
- **Fontes:** URL, data de coleta e licença de cada base citadas na seção 2 e no dicionário de dados.

---

## 13. Registro de decisões

Decisões tomadas pelo grupo ao longo das sprints. O detalhe fica na seção indicada; esta tabela é o índice — útil para a defesa.

| # | Data | Decisão | Por quê | Onde |
|---|---|---|---|---|
| 1 | 2026-09-26 | A Bronze guarda **todas as colunas e campos da fonte, como texto**, sem conversão, recorte ou validação de negócio | Reprocessar sempre a partir da Bronze, sem voltar à fonte; se a Silver precisar de outra coluna, ela já está lá | 4.1 |
| 2 | 2026-09-26 | A **quarentena acontece na Silver**; a Bronze só rejeita o que não consegue ler | Uma regra com bug na ingestão apagaria o dado da fonte de reprocessamento | 3.3 |
| 3 | 2026-09-27 | **Recorte fixo de jul/2016 a jun/2026** (120 meses, 10 anos), nas duas bases | Início: quebra de série do SCR em jun/2016. Fim fixo: o resultado não muda a cada publicação do BCB e só entram meses fechados | 2.3 |
| 4 | 2026-09-27 | O SCR publica com **~60 dias** de defasagem (não ~30) | Medido: em 2026-09-26 o último mês publicado era jul/2026 | 2.1, 6.2 |
| 5 | 2026-09-27 | **Versões republicadas pelo BCB são preservadas**; a Silver usa a mais recente | A Bronze é imutável; o BCB republicou ago/2024 depois da coleta | 3.2 |
| 6 | 2026-09-27 | `qtd_operacoes` = soma só das quantidades divulgadas — **limite inferior**; o **volume** é o indicador principal | O BCB esconde a quantidade (`-1`) em 28% das linhas e em 99,9% dos grupos | 5.1, 11 |
| 7 | 2026-09-27 | **Variação só entre meses consecutivos** (`tem_mes_anterior`); buracos não são preenchidos | 42 combinações UF × modalidade têm meses sem operação | 5.3 |
| 8 | 2026-09-27 | **Análise em dois níveis**: Brasil por modalidade e UF × modalidade (mapa de calor), Spearman, ajuste de Benjamini-Hochberg | Responder "por estado e por modalidade" sem escolher resultado a dedo | 5.4 |
| 9 | 2026-09-27 | **Selic meta do Copom** (`BM366_TJOVER366`, % a.a., corte no último dia do mês) no lugar da acumulada no mês (`BM12_TJOVER12`, % a.m.) | A série antiga variava com os dias úteis (correlação 0,79) e chegou a subir quando o Copom cortou | 2.2 |
| 11 | 2026-09-27 | **ML: prever se o crédito "ganha força"** (cresce mais no trimestre t+2→t+5 do que nos últimos 3 meses), nas 174 combinações completas, avaliado com e sem a Selic | Liga o modelo ao ciclo do crédito onde a Selic atua; a folga de 2 meses respeita o atraso de publicação; a versão "cresce mais que o Brasil" cancelava o efeito da Selic | 6.1 |
| 12 | 2026-09-27 | **Publicação da Gold** num banco NeonDB com front Next.js na Vercel; a etapa de envio é opcional (só roda com a string de conexão configurada) — **implementada** (decisão 16) | Mostrar os dados na entrega; o grupo tem experiência com a stack. Revisou a decisão "sem cloud" (seção 0) | 0, 7.1, 9 |
| 13 | 2026-09-27 | **Decisor:** diretoria de crédito de uma instituição financeira de **atuação nacional** (antes: cooperativa ou financeira regional) | O enunciado exige um decisor concreto; uma instituição regional não escolhe entre os 27 estados | 0, 10 |
| 14 | 2026-09-27 | **Regra de decisão:** a cada trimestre, expandir nas **20 combinações com maior probabilidade** de ganhar força (em vez de uma nota mínima fixa) | O erro de expandir onde o crédito perde força tem custo imediato — vale ser seletivo; no teste, as 20 maiores notas acertaram 82,5% (regra simples: 75%); lista fixa combina com a capacidade de execução e não depende da calibração das notas | 10 |
| 15 | 2026-09-27 | **Docker removido** (`Dockerfile` e `docker-compose.yml`); o ambiente padrão é `venv` + `requirements.txt` | O venv com versões fixadas já atende o enunciado e o CI confirma o ambiente em Python 3.11; manter um segundo caminho de execução não agregava | 7.2 |
| 16 | 2026-09-27 | **Publicação:** o pipeline recria as tabelas finais no Neon numa única transação (`src/publicacao/neon.py`, `psycopg` com `COPY`); a string de conexão fica em `DATABASE_URL` (`.env` fora do Git, `python-dotenv`); o site em `web/` (Next.js) só lê o banco, no servidor | Recriar é o jeito mais simples de ser idempotente (o banco espelha o arquivo); a transação evita o site mostrar uma publicação pela metade; o pipeline continua rodando sem a nuvem | 0, 5, 7, 9 |
| 17 | 2026-10-01 | **Site reestruturado em página única** (`web/`), a partir de um protótipo do Claude Design: seis seções com tooltips de glossário, tema claro/escuro e gráficos em SVG próprio (sai o `recharts`). Lê **só as tabelas já publicadas** (nenhum dado novo no Neon); a série de cada combinação vem sob demanda pela rota `/api/combinacao`. As antigas `/selic-credito` e `/explorar` redirecionam para as seções | Mostrar a decisão e a análise inteiras num só lugar, com os termos técnicos explicados para quem é de fora da área; os indicadores continuam vindo prontos do banco | 7.1 |
| 18 | 2026-10-01 | **Atualização quase em tempo real do site:** cache da página e da rota `/api/combinacao` de 1 h para **10 s**; o navegador consulta `/api/publicacao` a cada 10 s (só com a aba visível, parando após 30 min sem interação) e recarrega os dados quando há publicação nova, com aviso na tela. Leituras repetem uma vez após 1 s se falharem, e há página de erro com "tentar de novo" | A equipe quer publicar e mostrar a página mudando na apresentação. O cache curto mantém a proteção do Next de servir a última versão boa se o banco falhar; a repetição cobre a leitura que coincide com a troca das tabelas na publicação (decisão 16); o limite de visibilidade e tempo evita que uma aba esquecida mantenha o Neon acordado | 7.1 |

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