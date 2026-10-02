/**
 * Nomes de exibição das 8 modalidades de financiamento.
 *
 * O banco guarda o nome como vem do SCR.data ("Financiamentos imobiliários",
 * "Financiamentos rurais  (ex-financiamentos rurais e agroindustriais)" etc.).
 * Aqui só traduzimos para um nome curto de leitura — o dado não muda.
 * A ordem da lista é a ordem em que as modalidades aparecem no site.
 */

type InfoModalidade = { chave: string; nome: string; curto: string };

// Cada modalidade é reconhecida por um trecho do nome original (sem acento e em minúsculas).
const CONHECIDAS: (InfoModalidade & { trecho: string })[] = [
  { chave: "imobiliario", trecho: "imobiliario", nome: "Imobiliário", curto: "Imob." },
  { chave: "rural", trecho: "rura", nome: "Rural", curto: "Rural" },
  { chave: "geral", trecho: "", nome: "Financiamentos (geral)", curto: "Fin. geral" },
  { chave: "exportacao", trecho: "exportacao", nome: "Exportação", curto: "Export." },
  { chave: "interveniencia", trecho: "interveniencia", nome: "Com interveniência", curto: "Interv." },
  { chave: "infraestrutura", trecho: "infraestrutura", nome: "Infraestrutura e desenvolvimento", curto: "Infra." },
  { chave: "titulos", trecho: "titulos", nome: "Títulos e valores mobiliários", curto: "Títulos" },
  { chave: "importacao", trecho: "importacao", nome: "Importação", curto: "Import." },
];

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Informações de exibição a partir do nome da modalidade no banco. */
export function infoModalidade(nomeBanco: string): InfoModalidade {
  const texto = semAcento(nomeBanco);
  // "Financiamentos" puro é a modalidade geral; as demais têm um complemento no nome.
  if (texto.trim() === "financiamentos") return CONHECIDAS[2];
  const achada = CONHECIDAS.find((m) => m.trecho && texto.includes(m.trecho));
  if (achada) return achada;
  // Modalidade nova que não está na lista: mostra o nome original sem o prefixo.
  const resto = nomeBanco.replace(/^Financiamentos\s*/i, "").split("(")[0].trim() || nomeBanco;
  return { chave: semAcento(nomeBanco), nome: resto, curto: resto.slice(0, 8) };
}

/** Ordena os nomes do banco na ordem de exibição do site. */
export function ordenarModalidades(nomesBanco: string[]): string[] {
  const posicao = (nome: string) => {
    const i = CONHECIDAS.findIndex((m) => m.chave === infoModalidade(nome).chave);
    return i === -1 ? CONHECIDAS.length : i;
  };
  return [...nomesBanco].sort((a, b) => posicao(a) - posicao(b) || a.localeCompare(b));
}
