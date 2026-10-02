/**
 * Pequenas contas de apresentação, feitas no navegador sobre os dados já
 * prontos do banco: listas de meses e modalidades e alinhamento de séries
 * ao eixo de meses. Nenhum indicador é recalculado aqui.
 */
import type { DadosPainel } from "@/lib/tipos";
import { ordenarModalidades } from "@/lib/modalidades";
import { mesPorExtenso } from "@/lib/formato";

/** Os meses do recorte (jul/2016 a jun/2026), na ordem, a partir da série da Selic. */
export function mesesDoRecorte(dados: DadosPainel): string[] {
  return dados.selic.map((p) => p.mes);
}

/** O mês de origem da previsão (t0, jun/2026), por extenso. */
export function mesDaOrigem(dados: DadosPainel): string {
  const origem = dados.previsoes[0]?.origem ?? dados.selic[dados.selic.length - 1]?.mes;
  return origem ? mesPorExtenso(origem) : "—";
}

/** As 8 modalidades (nome do banco), na ordem de exibição. */
export function modalidadesDoSite(dados: DadosPainel): string[] {
  return ordenarModalidades([...new Set(dados.correlacoesBrasil.map((c) => c.modalidade))]);
}

/**
 * Coloca uma série no eixo de meses do recorte: o mês sem linha no banco vira
 * null (lacuna no gráfico), nunca é preenchido.
 */
export function alinhar<T extends { mes: string }>(
  serie: T[],
  meses: string[],
  valor: (linha: T) => number | null,
): (number | null)[] {
  const porMes = new Map(serie.map((linha) => [linha.mes, valor(linha)]));
  return meses.map((m) => porMes.get(m) ?? null);
}

/** Chave de uma combinação estado × modalidade, para buscas em mapas. */
export const chave = (uf: string, modalidade: string) => `${uf}|${modalidade}`;
