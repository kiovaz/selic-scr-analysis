/**
 * Explicações curtas dos termos técnicos, mostradas ao passar o mouse (ou
 * focar com o teclado) sobre uma palavra sublinhada. Texto do projeto:
 * mesmas definições do architecture.md, em linguagem simples.
 */
export const GLOSSARIO = {
  selic: ["Selic meta", "Taxa básica de juros definida pelo Copom, em % ao ano. Aqui, o valor vigente no último dia de cada mês."],
  copom: ["Copom", "Comitê do Banco Central que decide a Selic."],
  decisao: ["Decisão do Copom no mês", "Quanto a meta mudou em relação ao mês anterior, em pontos percentuais. Zero quando não mudou."],
  saldo: ["Saldo de carteira", "Quanto ainda está emprestado no fim do mês. Não é o valor concedido no mês."],
  modalidade: ["Modalidade", "Tipo de financiamento (imobiliário, rural, exportação etc.)."],
  defasagem: ["Defasagem", "Quantos meses separam a mudança da Selic do mês do crédito comparado."],
  spearman: ["Correlação de Spearman", "Mede se duas coisas sobem e descem juntas, de −1 (sentidos opostos) a +1 (juntas); 0 = sem relação."],
  significativo: ["Significativo", "Forte demais para ser só acaso, já considerando que muitos testes foram feitos ao mesmo tempo."],
  amostra: ["Amostra insuficiente", "Menos de 24 meses de dados válidos; a correlação não é calculada."],
  associacao: ["Associação x causa", "Andar junto não prova que uma coisa provoca a outra."],
  forca: ["Ganhar força", "O saldo crescer mais nos próximos 3 meses do que cresceu nos últimos 3."],
  prob: ["Probabilidade de ganhar força", "Nota de 0 a 1 que o modelo dá a cada combinação de estado e modalidade."],
  auc: ["AUC", "Nota de 0,5 (chute) a 1 (perfeito) que mede se o modelo coloca na frente quem de fato ganhou força."],
  regra: ["Regra simples (\"volta ao normal\")", "Palpite de que quem perdeu força nos últimos 3 meses vai ganhar força. É a régua que o modelo precisa superar."],
  acerto20: ["Acerto nas 20 melhores apostas", "Das 20 combinações que o modelo mais recomendou em cada mês, quantas de fato ganharam força."],
  trimestre: ["Trimestre recomendado", "O Banco Central publica o dado cerca de 60 dias depois do fim do mês. Por isso a previsão feita com dados de junho vale para setembro a novembro."],
  limiteInferior: ["Limite inferior", "O Banco Central esconde a quantidade de operações em parte das linhas. O número real é maior ou igual ao mostrado."],
} as const satisfies Record<string, readonly [string, string]>;

export type IdTermo = keyof typeof GLOSSARIO;
