/**
 * Consultas ao banco. Cada função devolve exatamente o que uma seção do site mostra.
 *
 * Regra do projeto: os indicadores (variações, correlações, probabilidades)
 * vêm prontos das tabelas publicadas pelo pipeline. Aqui o site só FILTRA e,
 * no caso do saldo do Brasil, SOMA os 27 estados.
 *
 * Os meses saem do banco como texto "AAAA-MM" (to_char) para não haver
 * confusão de fuso horário com datas no navegador. Colunas inteiras (bigint)
 * são convertidas para int ou float8, porque o driver devolve bigint como texto.
 */
import "server-only";
import { banco } from "./db";
import type {
  Correlacao,
  CorrelacaoUf,
  Frase,
  LinhaRecomendacao,
  MesCombinacao,
  PontoSelic,
  Previsao,
  SaldoBrasil,
  Sensibilidade,
} from "./tipos";

/**
 * Executa a leitura e, se falhar, espera um pouco e tenta mais uma vez.
 *
 * Por quê: a publicação do pipeline apaga e recria as tabelas numa transação
 * (src/publicacao/neon.py). Uma leitura que chega bem nessa hora espera a
 * transação terminar e pode falhar, porque a tabela foi trocada. Um segundo
 * depois, a tabela nova já está lá.
 */
export async function repetirSeFalhar<T>(ler: () => Promise<T>, tentativas = 2, esperaMs = 1000): Promise<T> {
  for (let i = 1; ; i++) {
    try {
      return await ler();
    } catch (erro) {
      if (i >= tentativas) throw erro;
      await new Promise((resolver) => setTimeout(resolver, esperaMs));
    }
  }
}

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

/**
 * A Selic meta do Copom (% ao ano, último dia do mês) e a decisão do Copom no
 * mês, uma linha por mês. É igual para todas as UFs, por isso o max().
 */
export async function lerSelic(): Promise<PontoSelic[]> {
  const linhas = await banco()`
    SELECT to_char(ano_mes, 'YYYY-MM') AS mes, max(selic_pct) AS selic_pct, max(var_selic_pp) AS var_selic_pp
    FROM gold_credito_selic GROUP BY ano_mes ORDER BY ano_mes`;
  return linhas as PontoSelic[];
}

/** Saldo de carteira do Brasil em cada modalidade: soma dos 27 estados, mês a mês. */
export async function lerSaldoBrasil(): Promise<SaldoBrasil[]> {
  const linhas = await banco()`
    SELECT to_char(ano_mes, 'YYYY-MM') AS mes, modalidade, sum(volume_rs) AS valor
    FROM gold_credito_selic GROUP BY ano_mes, modalidade ORDER BY modalidade, ano_mes`;
  return linhas as SaldoBrasil[];
}

/** Associação entre a variação da Selic (0 a 6 meses antes) e a do saldo, por modalidade (nível Brasil). */
export async function lerCorrelacoesBrasil(): Promise<Correlacao[]> {
  const linhas = await banco()`
    SELECT modalidade, defasagem_meses::int AS defasagem_meses, n_meses::int AS n_meses,
           spearman, p_ajustado, significativo
    FROM analise_brasil_modalidade ORDER BY modalidade, defasagem_meses`;
  return linhas as Correlacao[];
}

/** Associação de cada combinação estado × modalidade, na defasagem da modalidade (mapa de calor). */
export async function lerCorrelacoesUf(): Promise<CorrelacaoUf[]> {
  const linhas = await banco()`
    SELECT uf, modalidade, defasagem_meses::int AS defasagem_meses, n_meses::int AS n_meses,
           amostra_insuficiente, spearman, p_ajustado, coalesce(significativo, false) AS significativo
    FROM analise_uf_modalidade ORDER BY uf, modalidade`;
  return linhas as CorrelacaoUf[];
}

/** Probabilidade de cada combinação da coorte (174) ganhar força no trimestre recomendado. */
export async function lerPrevisoes(): Promise<Previsao[]> {
  const linhas = await banco()`
    SELECT uf, modalidade, to_char(origem, 'YYYY-MM') AS origem, prob_ganha_forca
    FROM ml_previsao_producao ORDER BY prob_ganha_forca DESC`;
  return linhas as Previsao[];
}

/** Regras de decisão testadas no período de teste (nota mínima e tamanho de lista). */
export async function lerSensibilidade(): Promise<Sensibilidade[]> {
  const linhas = await banco()`
    SELECT regra, parametro, recomendadas_por_mes, precisao_modelo, recall_modelo, precisao_regra_simples
    FROM sensibilidade_limiar`;
  return linhas as Sensibilidade[];
}

/** Série mensal de uma combinação estado × modalidade. */
export async function lerCombinacao(uf: string, modalidade: string): Promise<MesCombinacao[]> {
  const linhas = await banco()`
    SELECT to_char(ano_mes, 'YYYY-MM') AS mes, volume_rs, var_volume_pct,
           qtd_operacoes::float8 AS qtd_operacoes, selic_pct
    FROM gold_credito_selic WHERE uf = ${uf} AND modalidade = ${modalidade}
    ORDER BY ano_mes`;
  return linhas as MesCombinacao[];
}
