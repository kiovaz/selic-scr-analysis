/** Formatação de números e meses no padrão brasileiro. */

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** "2026-06" -> "jun/2026" */
export function mesPorExtenso(mes: string): string {
  const [ano, m] = mes.split("-");
  return `${MESES[Number(m) - 1]}/${ano}`;
}

/** Valor em reais na escala mais legível: "R$ 1,27 bi", "R$ 236,3 mil". */
export function reais(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  const escalas: [number, string][] = [
    [1e12, "tri"],
    [1e9, "bi"],
    [1e6, "mi"],
    [1e3, "mil"],
  ];
  for (const [base, nome] of escalas) {
    if (Math.abs(valor) >= base) {
      return `R$ ${(valor / base).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} ${nome}`;
    }
  }
  return `R$ ${valor.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`;
}

/** 0.825 -> "82,5%" */
export function porcentagem(fracao: number | null | undefined, casas = 1): string {
  if (fracao === null || fracao === undefined) return "—";
  return `${(fracao * 100).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })}%`;
}

/** Número com vírgula decimal: 0.419 -> "0,42" */
export function numero(valor: number | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined) return "—";
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}
