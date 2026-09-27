/**
 * Selic × crédito — a série da Selic, o saldo do Brasil numa modalidade e a
 * associação medida na análise (seção 5.4 do architecture.md).
 */
import Filtros from "@/components/Filtros";
import { GraficoSaldo, GraficoSelic } from "@/components/Graficos";
import { lerCorrelacoesBrasil, lerModalidades, lerSaldoBrasil, lerSelic, type Correlacao } from "@/lib/consultas";
import { numero } from "@/lib/formato";

const MODALIDADE_PADRAO = "Financiamentos imobiliários";

/**
 * Cor da célula: azul para associação positiva, vermelho para negativa,
 * cinza perto de zero. A intensidade cresce com o tamanho do Spearman
 * (0,5 ou mais = cor cheia). O número fica escrito na célula: a cor não é
 * a única forma de ler o valor.
 */
function corCelula(rho: number) {
  const intensidade = Math.min(Math.abs(rho) / 0.5, 1) * 85;
  const polo = rho >= 0 ? "var(--positivo)" : "var(--negativo)";
  return {
    background: `color-mix(in oklab, ${polo} ${intensidade}%, var(--neutro))`,
    color: intensidade > 50 ? "#ffffff" : "var(--texto)",
  };
}

function MapaCorrelacao({ linhas }: { linhas: Correlacao[] }) {
  const modalidades = [...new Set(linhas.map((l) => l.modalidade))];
  const defasagens = [...new Set(linhas.map((l) => l.defasagem_meses))].sort((a, b) => a - b);
  const celula = (m: string, d: number) => linhas.find((l) => l.modalidade === m && l.defasagem_meses === d);

  return (
    <div className="rolagem">
      <table className="mapa">
        <thead>
          <tr>
            <th>Modalidade</th>
            {defasagens.map((d) => (
              <th key={d} className="num" style={{ textAlign: "center" }}>
                {d} {d === 1 ? "mês" : "meses"}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {modalidades.map((m) => (
            <tr key={m}>
              <td>{m}</td>
              {defasagens.map((d) => {
                const c = celula(m, d);
                if (!c) return <td key={d} className="celula">—</td>;
                return (
                  <td
                    key={d}
                    className="celula"
                    style={{ ...corCelula(c.spearman), fontWeight: c.significativo ? 700 : 400 }}
                    title={`p ajustado ${numero(c.p_ajustado, 4)}${c.significativo ? " — significativo" : ""}`}
                  >
                    {numero(c.spearman)}
                    {c.significativo ? "*" : ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function PaginaSelicCredito({ searchParams }: PageProps<"/selic-credito">) {
  const parametros = await searchParams;
  const modalidades = await lerModalidades();
  const pedida = typeof parametros.modalidade === "string" ? parametros.modalidade : MODALIDADE_PADRAO;
  const modalidade = modalidades.includes(pedida) ? pedida : modalidades[0];

  const [selic, saldo, correlacoes] = await Promise.all([
    lerSelic(),
    lerSaldoBrasil(modalidade),
    lerCorrelacoesBrasil(),
  ]);

  return (
    <main>
      <h1>Selic × crédito</h1>
      <p className="sub">
        A Selic e o saldo aparecem em gráficos separados porque têm escalas diferentes. A associação da tabela no
        fim da página compara as <strong>variações</strong> mês a mês, não os níveis dos gráficos — dois níveis que
        sobem juntos ao longo de 10 anos parecem relacionados mesmo sem ter relação.
      </p>

      <Filtros filtros={[{ nome: "modalidade", rotulo: "Modalidade", opcoes: modalidades, valor: modalidade }]} />

      <div className="duas-colunas">
        <section className="cartao">
          <p className="grafico-titulo">Selic meta do Copom</p>
          <p className="grafico-sub">% ao ano, no último dia de cada mês — igual para todos os estados</p>
          <GraficoSelic dados={selic} />
        </section>
        <section className="cartao">
          <p className="grafico-titulo">Saldo de carteira no Brasil — {modalidade}</p>
          <p className="grafico-sub">soma dos 27 estados, reais nominais, fim de cada mês</p>
          <GraficoSaldo dados={saldo} />
        </section>
      </div>

      <h2>Quanto a variação do saldo anda junto com a variação da Selic</h2>
      <p className="nota">
        Correlação de Spearman entre a variação mensal do saldo e a variação da Selic de 0 a 6 meses antes, no
        Brasil, por modalidade. Vai de −1 a +1; perto de 0 = sem associação. <strong>*</strong> = significativo
        depois do ajuste para muitos testes (Benjamini-Hochberg). Associação não é causa.
      </p>
      <MapaCorrelacao linhas={correlacoes} />
      <div className="legenda">
        <span>
          <span className="amostra" style={{ background: "var(--negativo)" }} />
          negativa
        </span>
        <span>
          <span className="amostra" style={{ background: "var(--neutro)", border: "1px solid var(--eixo)" }} />
          perto de zero
        </span>
        <span>
          <span className="amostra" style={{ background: "var(--positivo)" }} />
          positiva
        </span>
      </div>
    </main>
  );
}
