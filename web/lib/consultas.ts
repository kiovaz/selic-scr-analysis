/**
 * Consultas ao banco. Cada função devolve exatamente o que uma página mostra.
 *
 * Regra do projeto: os indicadores (variações, correlações, probabilidades)
 * vêm prontos das tabelas publicadas pelo pipeline. Aqui o site só FILTRA e,
 * no caso do saldo do Brasil, SOMA os 27 estados.
 *
 * Os meses saem do banco como texto "AAAA-MM" (to_char) para não haver
 * confusão de fuso horário com datas no navegador.
 */
import "server-only";
import { banco } from "./db";

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
  saldo_total_lista_expandir_rs: number;
  associacao_mais_forte_sprint4: {
    modalidade: string;
    defasagem_meses: number;
    spearman: number;
    p_ajustado: number;
  };
};

export type LinhaRecomendacao = {
  grupo: "expandir" | "alerta";
  posicao: number;
  uf: string;
  modalidade: string;
  prob_ganha_forca: number;
  volume_rs: number | null;
};

export type PontoMensal = { mes: string; valor: number | null };

export type Correlacao = {
  modalidade: string;
  defasagem_meses: number;
  spearman: number;
  p_ajustado: number;
  significativo: boolean;
};

/** Números da frase de fechamento (data/final/frase_fechamento.json). */
export async function lerFrase(): Promise<Frase> {
  const linhas = await banco()`SELECT dados FROM frase_fechamento LIMIT 1`;
  return linhas[0].dados as Frase;
}

/** Data e hora da última publicação do pipeline no banco. */
export async function lerUltimaPublicacao(): Promise<string | null> {
  const linhas = await banco()`
    SELECT to_char(publicado_em AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI') AS quando
    FROM publicacao_controle ORDER BY publicado_em DESC LIMIT 1`;
  return linhas.length ? (linhas[0].quando as string) : null;
}

/** As 20 combinações "expandir" e as 20 "alerta" do trimestre. */
export async function lerRecomendacao(): Promise<LinhaRecomendacao[]> {
  const linhas = await banco()`
    SELECT grupo, posicao::int AS posicao, uf, modalidade, prob_ganha_forca, volume_rs
    FROM recomendacao_trimestre ORDER BY grupo DESC, posicao`;
  return linhas as LinhaRecomendacao[];
}

/** A Selic meta do Copom (% ao ano) no último dia de cada mês — igual para todas as UFs. */
export async function lerSelic(): Promise<PontoMensal[]> {
  const linhas = await banco()`
    SELECT to_char(ano_mes, 'YYYY-MM') AS mes, max(selic_pct) AS valor
    FROM gold_credito_selic GROUP BY ano_mes ORDER BY ano_mes`;
  return linhas as PontoMensal[];
}

/** Lista das modalidades publicadas, em ordem alfabética. */
export async function lerModalidades(): Promise<string[]> {
  const linhas = await banco()`SELECT DISTINCT modalidade FROM gold_credito_selic ORDER BY modalidade`;
  return linhas.map((l) => l.modalidade as string);
}

/** Lista das UFs publicadas. */
export async function lerUfs(): Promise<string[]> {
  const linhas = await banco()`SELECT DISTINCT uf FROM gold_credito_selic ORDER BY uf`;
  return linhas.map((l) => l.uf as string);
}

/** Saldo de carteira do Brasil numa modalidade: soma dos 27 estados, mês a mês. */
export async function lerSaldoBrasil(modalidade: string): Promise<PontoMensal[]> {
  const linhas = await banco()`
    SELECT to_char(ano_mes, 'YYYY-MM') AS mes, sum(volume_rs) AS valor
    FROM gold_credito_selic WHERE modalidade = ${modalidade}
    GROUP BY ano_mes ORDER BY ano_mes`;
  return linhas as PontoMensal[];
}

/** Associação entre a variação da Selic (0 a 6 meses antes) e a do saldo, por modalidade. */
export async function lerCorrelacoesBrasil(): Promise<Correlacao[]> {
  const linhas = await banco()`
    SELECT modalidade, defasagem_meses::int AS defasagem_meses, spearman, p_ajustado, significativo
    FROM analise_brasil_modalidade ORDER BY modalidade, defasagem_meses`;
  return linhas as Correlacao[];
}

export type MesCombinacao = {
  mes: string;
  volume_rs: number;
  var_volume_pct: number | null;
  qtd_operacoes: number;
  linhas_qtd_nao_divulgada: number;
  selic_pct: number | null;
};

/** Série mensal de uma combinação estado × modalidade. */
export async function lerCombinacao(uf: string, modalidade: string): Promise<MesCombinacao[]> {
  const linhas = await banco()`
    SELECT to_char(ano_mes, 'YYYY-MM') AS mes, volume_rs, var_volume_pct,
           qtd_operacoes::float8 AS qtd_operacoes,
           linhas_qtd_nao_divulgada::float8 AS linhas_qtd_nao_divulgada, selic_pct
    FROM gold_credito_selic WHERE uf = ${uf} AND modalidade = ${modalidade}
    ORDER BY ano_mes`;
  return linhas as MesCombinacao[];
}

/** Probabilidade de o crédito da combinação ganhar força no trimestre recomendado (se houver previsão). */
export async function lerPrevisao(uf: string, modalidade: string): Promise<number | null> {
  const linhas = await banco()`
    SELECT prob_ganha_forca FROM ml_previsao_producao
    WHERE uf = ${uf} AND modalidade = ${modalidade} LIMIT 1`;
  return linhas.length ? (linhas[0].prob_ganha_forca as number) : null;
}
