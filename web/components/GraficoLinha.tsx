"use client";

/**
 * Gráfico de linha de uma série mensal, com dica (tooltip) ao passar o mouse.
 * Um gráfico = uma medida = um eixo. Selic e saldo nunca dividem o mesmo
 * gráfico: têm escalas diferentes e dois eixos enganam a leitura.
 */
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { mesPorExtenso } from "@/lib/formato";

type Ponto = { mes: string; valor: number | null };

type Props = {
  dados: Ponto[];
  cor: string; // variável CSS, ex.: "var(--serie-1)"
  formatar: (valor: number) => string; // texto do valor na dica
  formatarEixo: (valor: number) => string; // texto curto no eixo
  nome: string; // nome da série na dica
  altura?: number;
};

export default function GraficoLinha({ dados, cor, formatar, formatarEixo, nome, altura = 260 }: Props) {
  // Marcas do eixo só em janeiro, a cada 2 anos: cada ano aparece uma vez só.
  const janeiros = dados.map((p) => p.mes).filter((m) => m.endsWith("-01") && Number(m.slice(0, 4)) % 2 === 0);
  return (
    <ResponsiveContainer width="100%" height={altura}>
      <LineChart data={dados} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grade)" vertical={false} />
        <XAxis
          dataKey="mes"
          ticks={janeiros}
          tickFormatter={(m: string) => m.slice(0, 4)}
          stroke="var(--eixo)"
          tick={{ fill: "var(--texto-3)", fontSize: 12 }}
        />
        <YAxis
          tickFormatter={formatarEixo}
          width={70}
          stroke="var(--eixo)"
          tick={{ fill: "var(--texto-3)", fontSize: 12 }}
        />
        <Tooltip
          cursor={{ stroke: "var(--eixo)" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const ponto = payload[0].payload as Ponto;
            return (
              <div className="dica">
                <div>{mesPorExtenso(ponto.mes)}</div>
                <div>
                  <span className="amostra" style={{ background: cor }} />
                  {nome}: <strong>{ponto.valor === null ? "sem dado" : formatar(ponto.valor)}</strong>
                </div>
              </div>
            );
          }}
        />
        <Line
          type="monotone"
          dataKey="valor"
          stroke={cor}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 5, stroke: "var(--superficie)", strokeWidth: 2 }}
          connectNulls={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
