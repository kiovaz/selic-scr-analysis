"use client";

/**
 * Os dois gráficos do site, já com cor, nome e formato de número.
 * Ficam do lado do navegador (o recharts desenha na tela); os dados chegam
 * prontos da página, que consultou o banco no servidor.
 */
import GraficoLinha from "./GraficoLinha";
import { numero, reais } from "@/lib/formato";

type Ponto = { mes: string; valor: number | null };

export function GraficoSelic({ dados }: { dados: Ponto[] }) {
  return (
    <GraficoLinha
      dados={dados}
      cor="var(--serie-2)"
      nome="Selic meta"
      formatar={(v) => `${numero(v)}% ao ano`}
      formatarEixo={(v) => `${numero(v, 0)}%`}
    />
  );
}

export function GraficoSaldo({ dados }: { dados: Ponto[] }) {
  return (
    <GraficoLinha
      dados={dados}
      cor="var(--serie-1)"
      nome="Saldo"
      formatar={(v) => reais(v)}
      formatarEixo={(v) => reais(v).replace("R$ ", "")}
    />
  );
}
