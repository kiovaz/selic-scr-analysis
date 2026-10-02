/**
 * Os 27 estados, com o nome por extenso e a posição no "mapa em grade"
 * (cada estado é um quadrado, numa posição aproximada da geografia real).
 * É informação fixa de geografia — nenhum dado do projeto mora aqui.
 */

export type Uf = { sigla: string; nome: string; coluna: number; linha: number };

export const UFS: Uf[] = [
  ["AC", "Acre", 1, 3], ["AL", "Alagoas", 6, 4], ["AP", "Amapá", 4, 1], ["AM", "Amazonas", 2, 2],
  ["BA", "Bahia", 4, 4], ["CE", "Ceará", 5, 2], ["DF", "Distrito Federal", 3, 5], ["ES", "Espírito Santo", 5, 5],
  ["GO", "Goiás", 3, 4], ["MA", "Maranhão", 4, 2], ["MT", "Mato Grosso", 2, 4], ["MS", "Mato Grosso do Sul", 2, 5],
  ["MG", "Minas Gerais", 4, 5], ["PA", "Pará", 3, 2], ["PB", "Paraíba", 6, 3], ["PR", "Paraná", 2, 6],
  ["PE", "Pernambuco", 5, 3], ["PI", "Piauí", 4, 3], ["RJ", "Rio de Janeiro", 4, 6], ["RN", "Rio Grande do Norte", 6, 2],
  ["RS", "Rio Grande do Sul", 2, 8], ["RO", "Rondônia", 2, 3], ["RR", "Roraima", 2, 1], ["SC", "Santa Catarina", 2, 7],
  ["SP", "São Paulo", 3, 6], ["SE", "Sergipe", 5, 4], ["TO", "Tocantins", 3, 3],
].map(([sigla, nome, coluna, linha]) => ({
  sigla: sigla as string,
  nome: nome as string,
  coluna: coluna as number,
  linha: linha as number,
}));

export function nomeUf(sigla: string): string {
  return UFS.find((u) => u.sigla === sigla)?.nome ?? sigla;
}
