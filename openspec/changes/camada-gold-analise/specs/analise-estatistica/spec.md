## Purpose

Mede a associação entre a variação do crédito e a variação da Selic, com defasagens de 0 a 6 meses, em dois níveis — Brasil por modalidade e UF × modalidade — seguindo as regras da seção 5.4 de `docs/architecture.md`, e produz os gráficos da entrega.

## ADDED Requirements

### Requirement: Nível Brasil por modalidade

Para cada modalidade, a análise SHALL somar `volume_rs` das 27 UFs em cada mês (uma UF sem linha no mês contribui zero, porque não havia operação) e calcular a variação mensal nacional. Para cada defasagem k de 0 a `DEFASAGEM_MAXIMA` (6), a análise SHALL medir a correlação entre a variação nacional do volume no mês t e `var_selic_pp` no mês t − k, e SHALL registrar: modalidade, k, número de meses usados, coeficiente de Spearman, valor-p e valor-p ajustado.

Só meses com as duas variações disponíveis SHALL entrar no cálculo. A análise SHALL usar **variações**, nunca níveis (seção 5.4).

#### Scenario: Tabela de resultados

- **WHEN** a análise roda sobre a Gold com 8 modalidades
- **THEN** o resultado tem 8 × 7 = 56 linhas (modalidade × k de 0 a 6)
- **AND** cada linha tem o número de meses usados, o coeficiente, o valor-p e o valor-p ajustado

#### Scenario: Relação conhecida é recuperada

- **WHEN** numa Gold sintética a variação do volume é exatamente o oposto da variação da Selic de 2 meses antes
- **THEN** o coeficiente para k = 2 é −1
- **AND** é o de maior valor absoluto entre as defasagens daquela modalidade

### Requirement: Nível UF × modalidade

Para cada combinação `(uf, modalidade)`, a análise SHALL medir a correlação de Spearman entre `var_volume_pct` e `var_selic_pp` defasada em k*, onde k* é a defasagem de maior associação, em valor absoluto, **daquela modalidade no nível Brasil**. Só linhas com `tem_mes_anterior` verdadeiro e as duas variações disponíveis SHALL entrar. Combinações com menos de `MESES_MINIMOS_CORRELACAO` meses válidos SHALL ter o coeficiente vazio e SHALL ser marcadas como "amostra insuficiente", sem valor calculado.

#### Scenario: Combinação com poucos meses

- **WHEN** a combinação AP × títulos tem só 5 meses válidos e o mínimo configurado é 24
- **THEN** o coeficiente dela fica vazio e ela aparece marcada como amostra insuficiente

#### Scenario: Defasagem vinda do nível Brasil

- **WHEN** no nível Brasil a maior associação de `Financiamentos imobiliários` é em k = 3
- **THEN** todas as combinações UF × `Financiamentos imobiliários` são medidas com k = 3

### Requirement: Muitos testes e forma de relatar

Os valores-p SHALL ser ajustados pelo método de Benjamini-Hochberg, separadamente em cada nível (Brasil e UF × modalidade), porque centenas de correlações ao mesmo tempo produzem resultados "significativos" por acaso. Um resultado SHALL ser considerado estatisticamente significativo apenas se o valor-p **ajustado** for menor que 0,05. Textos, gráficos e o notebook SHALL descrever os resultados como **associação**, nunca como causa (seção 5.4).

#### Scenario: Ajuste para muitos testes

- **WHEN** 56 correlações são calculadas no nível Brasil
- **THEN** cada uma tem valor-p ajustado maior ou igual ao valor-p original
- **AND** a coluna de significância usa o valor-p ajustado

### Requirement: Gráficos e notebook

A análise SHALL gerar, em `docs/figuras/`:
- o **primeiro gráfico**: o coeficiente de correlação por defasagem (0 a 6) para cada modalidade no nível Brasil, destacando os resultados significativos;
- o **mapa de calor** UF × modalidade, com as células de amostra insuficiente visivelmente distintas.

O `notebooks/02_analise_estatistica.ipynb` SHALL ler os resultados de `data/final/`, mostrar os dois gráficos e explicar em texto como ler cada um, com as saídas gravadas.

#### Scenario: Figuras geradas

- **WHEN** a etapa de análise do pipeline termina
- **THEN** existem `docs/figuras/correlacao_por_modalidade.png` e `docs/figuras/mapa_calor_uf_modalidade.png`
