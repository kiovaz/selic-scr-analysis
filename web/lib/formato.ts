/** Formatação de números e meses no padrão brasileiro. */

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

type Valor = number | null | undefined;

/** "2026-06" -> "jun/2026" */
export function mesPorExtenso(mes: string): string {
  const [ano, m] = mes.split("-");
  return `${MESES[Number(m) - 1]}/${ano}`;
}

/** Número com vírgula decimal e casas fixas: 0.419 -> "0,42". Vazio vira "—". */
export function numero(valor: Valor, casas = 2): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** 0.825 -> "82,5%" */
export function porcentagem(fracao: Valor, casas = 1): string {
  if (fracao === null || fracao === undefined || Number.isNaN(fracao)) return "—";
  return `${numero(fracao * 100, casas)}%`;
}

/** Número com sinal (usa o sinal de menos tipográfico): 0.42 -> "+0,42"; -0.15 -> "−0,15". */
export function comSinal(valor: Valor, casas = 2): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  // Sem sinal quando o valor arredondado é zero (evita "−0,00").
  const arredondado = Number(valor.toFixed(casas));
  const sinal = arredondado > 0 ? "+" : arredondado < 0 ? "−" : "";
  return sinal + numero(Math.abs(arredondado), casas);
}

/** Saldo em reais na escala mais legível: "R$ 1,27 tri", "R$ 557,5 bi", "R$ 236 mil". */
export function reais(valor: Valor): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
  if (valor === 0) return "R$ 0";
  if (valor >= 1e12) return `R$ ${numero(valor / 1e12, 2)} tri`;
  if (valor >= 1e9) return `R$ ${numero(valor / 1e9, 1)} bi`;
  if (valor >= 1e6) return `R$ ${numero(valor / 1e6, 1)} mi`;
  return `R$ ${numero(valor / 1e3, 0)} mil`;
}
