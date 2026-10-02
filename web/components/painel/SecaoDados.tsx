/**
 * 06 · Sobre os dados — fontes, recorte, as três camadas do pipeline e as
 * limitações (seção 11 do architecture.md, em versão curta).
 */
import { Termo } from "./apoio";

const CAMADAS = [
  ["Bruto", "Arquivos do SCR.data e série da Selic como publicados"],
  ["Limpo", "Tipos, estados e modalidades padronizados; registros inválidos separados"],
  ["Pronto para análise", "Uma linha por mês × estado × modalidade, com a Selic"],
];

export default function SecaoDados({ publicadoEm }: { publicadoEm: string | null }) {
  return (
    <section id="dados" className="secao secao-clara secao-final">
      <div className="container">
        <div className="rotulo-secao">06 · Sobre os dados</div>
        <h2 className="titulo-secao">De onde vêm os números</h2>

        <div className="duas-colunas">
          <div>
            <h3 className="titulo-pequeno">Fontes</h3>
            <ul className="lista-filetes">
              <li>
                <a href="https://dadosabertos.bcb.gov.br/dataset/scr_data">SCR.data</a>, Banco Central do Brasil. Licença
                ODbL.
              </li>
              <li>
                Selic meta do Copom, série BM366_TJOVER366, via <a href="http://www.ipeadata.gov.br">Ipeadata</a>, com o
                Banco Central como produtor original.
              </li>
            </ul>
          </div>
          <div>
            <h3 className="titulo-pequeno">Recorte</h3>
            <p className="filete">
              Jul/2016 a jun/2026: 120 meses, 27 estados e 8 modalidades de financiamento. Começa em jul/2016 porque, antes
              disso, o limite mínimo de registro do SCR era outro e os dados não são comparáveis.
            </p>
          </div>
        </div>

        <div className="bloco-medio">
          <h3 className="titulo-pequeno">Pipeline em três camadas</h3>
          <div className="camadas">
            {CAMADAS.map(([nome, descricao], i) => (
              <div key={nome} className="camada-grupo">
                {i > 0 && <div className="camada-seta" aria-hidden="true">→</div>}
                <div className={i === CAMADAS.length - 1 ? "camada camada-final" : "camada"}>
                  <div className="mono apagado pequeno">{i + 1}</div>
                  <div className="camada-nome">{nome}</div>
                  <div className="apagado pequeno-medio">{descricao}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bloco-medio">
          <h3 className="titulo-pequeno">Limitações</h3>
          <ul className="lista-limitacoes">
            <li>
              O dado é <Termo id="saldo">saldo de carteira</Termo> no fim do mês, não o valor concedido no mês.
            </li>
            <li>Valores nominais, sem correção pela inflação.</li>
            <li>
              A quantidade de operações é subestimada: o Banco Central esconde a quantidade em parte das linhas. Por isso o
              indicador principal é o saldo.
            </li>
            <li>
              <Termo id="associacao">Associação não é causa.</Termo> Renda, emprego, safra e política de crédito dos bancos
              não são controlados.
            </li>
            <li>O estado vem do endereço do cliente, não de onde o dinheiro é usado.</li>
            <li>A avaliação final cobre 12 meses, um único período de juros altos.</li>
          </ul>
        </div>

        <footer className="rodape">
          <span>Dados atualizados em {publicadoEm ?? "—"}</span>
          <span>Fontes: SCR.data (Banco Central, ODbL) · Selic meta BM366_TJOVER366 (Ipeadata / Banco Central)</span>
        </footer>
      </div>
    </section>
  );
}
