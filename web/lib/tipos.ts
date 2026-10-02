/**
 * Formato das linhas que o site lê do banco. Fica separado de consultas.ts
 * (que só roda no servidor) para os componentes do navegador poderem usar os
 * mesmos tipos. Cada tipo corresponde a uma tabela descrita em
 * docs/data_dictionary.md ("Tabelas publicadas no Neon").
 */

/** frase_fechamento.dados — os números da frase de fechamento e da seção 10. */
export type Frase = {
  trimestre_recomendado: string;
  tamanho_lista: number;
  precisao_lista_modelo: number;
  precisao_lista_regra_simples: number;
  precisao_acaso: number;
  acertos_esperados_modelo: number;
  erros_esperados_modelo: number;
  acertos_esperados_regra_simples: number;
  acertos_esperados_acaso: number;
  auc_modelo: number;
  auc_regra_simples: number;
  auc_sem_selic: number;
  efeito_selic_auc_teste: number;
  saldo_total_lista_expandir_rs: number;
  associacao_mais_forte_sprint4: {
    modalidade: string;
    defasagem_meses: number;
    spearman: number;
    p_ajustado: number;
  };
};

/** recomendacao_trimestre */
export type LinhaRecomendacao = {
  grupo: "expandir" | "alerta";
  posicao: number;
  uf: string;
  modalidade: string;
  prob_ganha_forca: number;
  volume_rs: number | null;
};

/** Selic meta e decisão do Copom no mês (gold_credito_selic, uma linha por mês). */
export type PontoSelic = { mes: string; selic_pct: number; var_selic_pp: number | null };

/** Soma do saldo dos 27 estados numa modalidade e mês (gold_credito_selic). */
export type SaldoBrasil = { mes: string; modalidade: string; valor: number | null };

/** analise_brasil_modalidade */
export type Correlacao = {
  modalidade: string;
  defasagem_meses: number;
  n_meses: number;
  spearman: number | null;
  p_ajustado: number | null;
  significativo: boolean;
};

/** analise_uf_modalidade */
export type CorrelacaoUf = {
  uf: string;
  modalidade: string;
  defasagem_meses: number;
  n_meses: number;
  amostra_insuficiente: boolean;
  spearman: number | null;
  p_ajustado: number | null;
  significativo: boolean;
};

/** ml_previsao_producao */
export type Previsao = { uf: string; modalidade: string; origem: string; prob_ganha_forca: number };

/** sensibilidade_limiar */
export type Sensibilidade = {
  regra: string; // "nota mínima" ou "maiores notas do mês"
  parametro: number;
  recomendadas_por_mes: number;
  precisao_modelo: number | null;
  recall_modelo: number | null;
  precisao_regra_simples: number | null;
};

/** Um mês de uma combinação estado × modalidade (gold_credito_selic). */
export type MesCombinacao = {
  mes: string;
  volume_rs: number | null;
  var_volume_pct: number | null;
  qtd_operacoes: number | null;
  selic_pct: number | null;
};

/** Tudo o que a página entrega ao navegador de uma vez (a série de cada combinação vem sob demanda). */
export type DadosPainel = {
  frase: Frase;
  recomendacao: LinhaRecomendacao[];
  selic: PontoSelic[];
  saldoBrasil: SaldoBrasil[];
  correlacoesBrasil: Correlacao[];
  correlacoesUf: CorrelacaoUf[];
  previsoes: Previsao[];
  sensibilidade: Sensibilidade[];
  publicadoEm: string | null;
  combinacaoInicial: { uf: string; modalidade: string; serie: MesCombinacao[] };
};
