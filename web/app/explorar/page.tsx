/**
 * Explorar — uma combinação estado × modalidade: o saldo mês a mês, os
 * últimos 12 meses em tabela e a chance prevista pelo modelo para o trimestre.
 */
import Filtros from "@/components/Filtros";
import { GraficoSaldo } from "@/components/Graficos";
import { lerCombinacao, lerFrase, lerModalidades, lerPrevisao, lerUfs } from "@/lib/consultas";
import { mesPorExtenso, numero, porcentagem, reais } from "@/lib/formato";

export default async function PaginaExplorar({ searchParams }: PageProps<"/explorar">) {
  const parametros = await searchParams;
  const [ufs, modalidades, frase] = await Promise.all([lerUfs(), lerModalidades(), lerFrase()]);

  const ufPedida = typeof parametros.uf === "string" ? parametros.uf : "SP";
  const modPedida = typeof parametros.modalidade === "string" ? parametros.modalidade : "Financiamentos imobiliários";
  const uf = ufs.includes(ufPedida) ? ufPedida : ufs[0];
  const modalidade = modalidades.includes(modPedida) ? modPedida : modalidades[0];

  const [meses, previsao] = await Promise.all([lerCombinacao(uf, modalidade), lerPrevisao(uf, modalidade)]);
  const ultimos = meses.slice(-12).reverse();
  const saldo = meses.map((m) => ({ mes: m.mes, valor: m.volume_rs }));

  return (
    <main>
      <h1>Explorar por estado e modalidade</h1>
      <p className="sub">Escolha um estado e uma modalidade para ver o saldo de carteira mês a mês.</p>

      <Filtros
        filtros={[
          { nome: "uf", rotulo: "Estado (UF)", opcoes: ufs, valor: uf },
          { nome: "modalidade", rotulo: "Modalidade", opcoes: modalidades, valor: modalidade },
        ]}
      />

      {meses.length === 0 ? (
        <p className="cartao">Não há operações registradas nesta combinação no recorte.</p>
      ) : (
        <>
          <div className="numeros">
            <div className="cartao">
              <div className="numero-rotulo">Saldo em {mesPorExtenso(meses[meses.length - 1].mes)}</div>
              <div className="numero-valor">{reais(meses[meses.length - 1].volume_rs)}</div>
              <div className="numero-nota">{meses.length} meses com operação desde jul/2016</div>
            </div>
            <div className="cartao">
              <div className="numero-rotulo">Chance de ganhar força em {frase.trimestre_recomendado}</div>
              <div className="numero-valor">{previsao === null ? "—" : porcentagem(previsao, 0)}</div>
              <div className="numero-nota">
                {previsao === null
                  ? "sem previsão: o modelo só cobre as 174 combinações com os 120 meses completos"
                  : "previsão do modelo (origem jun/2026)"}
              </div>
            </div>
          </div>

          <section className="cartao">
            <p className="grafico-titulo">
              Saldo de carteira — {uf}, {modalidade}
            </p>
            <p className="grafico-sub">reais nominais, fim de cada mês; meses sem operação ficam em branco</p>
            <GraficoSaldo dados={saldo} />
          </section>

          <h2>Últimos 12 meses</h2>
          <div className="rolagem">
            <table>
              <thead>
                <tr>
                  <th>Mês</th>
                  <th className="num">Saldo</th>
                  <th className="num">Variação no mês</th>
                  <th className="num">Operações (mínimo)</th>
                  <th className="num">Selic meta</th>
                </tr>
              </thead>
              <tbody>
                {ultimos.map((m) => (
                  <tr key={m.mes}>
                    <td>{mesPorExtenso(m.mes)}</td>
                    <td className="num">{reais(m.volume_rs)}</td>
                    <td className="num">{m.var_volume_pct === null ? "—" : `${numero(m.var_volume_pct, 1)}%`}</td>
                    <td className="num">
                      {m.qtd_operacoes === 0 && m.linhas_qtd_nao_divulgada > 0
                        ? "não divulgada"
                        : m.qtd_operacoes.toLocaleString("pt-BR")}
                    </td>
                    <td className="num">{m.selic_pct === null ? "—" : `${numero(m.selic_pct)}%`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="nota">
            A quantidade de operações é um mínimo: o Banco Central esconde a quantidade em parte das linhas (“não
            divulgada” quando todas as linhas do mês estão escondidas). Por isso o indicador principal é o saldo.
          </p>
        </>
      )}
    </main>
  );
}
