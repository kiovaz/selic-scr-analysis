/**
 * Página inicial — a recomendação do trimestre (seção 10 do architecture.md).
 * Tudo aqui vem das tabelas que o pipeline publicou: frase_fechamento,
 * recomendacao_trimestre e publicacao_controle.
 */
import { lerFrase, lerRecomendacao, lerUltimaPublicacao, type LinhaRecomendacao } from "@/lib/consultas";
import { numero, porcentagem, reais } from "@/lib/formato";

// Página regerada no máximo a cada hora: uma nova publicação aparece sem novo deploy.
export const revalidate = 3600;

function TabelaLista({ linhas, grupo }: { linhas: LinhaRecomendacao[]; grupo: "expandir" | "alerta" }) {
  return (
    <div className={`rolagem ${grupo}`}>
      <table>
        <thead>
          <tr>
            <th className="num">#</th>
            <th>UF</th>
            <th>Modalidade</th>
            <th>Chance de ganhar força</th>
            <th className="num">Saldo em jun/2026</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={`${l.uf}-${l.modalidade}`}>
              <td className="num">{l.posicao}</td>
              <td>{l.uf}</td>
              <td>{l.modalidade}</td>
              <td className="num" style={{ textAlign: "left" }}>
                <span className="barra-prob" style={{ width: `${Math.round(l.prob_ganha_forca * 60)}px` }} />
                {porcentagem(l.prob_ganha_forca, 0)}
              </td>
              <td className="num">{reais(l.volume_rs)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function PaginaRecomendacao() {
  const [frase, recomendacao, publicadoEm] = await Promise.all([
    lerFrase(),
    lerRecomendacao(),
    lerUltimaPublicacao(),
  ]);
  const expandir = recomendacao.filter((l) => l.grupo === "expandir");
  const alerta = recomendacao.filter((l) => l.grupo === "alerta");
  const assoc = frase.associacao_mais_forte_sprint4;
  const n = frase.tamanho_lista;

  return (
    <main>
      <h1>Onde expandir o crédito em {frase.trimestre_recomendado}</h1>
      <p className="sub">
        Recomendação para a diretoria de crédito de uma instituição financeira de atuação nacional, gerada pelo
        pipeline com dados até jun/2026. Última publicação: {publicadoEm ?? "—"}.
      </p>

      <section className="cartao frase" aria-label="Frase de fechamento">
        <p>
          Cruzando o SCR.data (BCB) e a Selic meta do Copom (Ipeadata), identificamos que o crédito da modalidade
          “{assoc.modalidade}” anda junto com a Selic de {assoc.defasagem_meses} meses antes (Spearman{" "}
          {numero(assoc.spearman)}), mas a Selic não antecipa o trimestre seguinte (AUC com Selic{" "}
          {numero(frase.auc_modelo, 3)} × sem Selic {numero(frase.auc_sem_selic, 3)}); o que antecipa é o ritmo
          recente do próprio crédito.
        </p>
        <p>
          Recomendamos expandir a oferta de financiamento nas <strong>{n} combinações estado × modalidade</strong>{" "}
          com maior probabilidade de ganhar força nos próximos 3 meses ({frase.trimestre_recomendado}), priorizando
          as de maior saldo dentro da lista.
        </p>
        <p>
          Se agir, o ganho esperado é acertar ~{numero(frase.acertos_esperados_modelo, 1)} de {n} expansões por
          trimestre ({porcentagem(frase.precisao_lista_modelo)}), contra ~
          {numero(frase.acertos_esperados_regra_simples, 1)} da regra simples e ~
          {numero(frase.acertos_esperados_acaso, 1)} ao acaso; se errarmos, o custo é ~
          {numero(frase.erros_esperados_modelo, 1)} expansões por trimestre em mercados que estão perdendo força.
        </p>
      </section>

      <div className="numeros">
        <div className="cartao">
          <div className="numero-rotulo">Acerto da lista de {n} (modelo)</div>
          <div className="numero-valor">{porcentagem(frase.precisao_lista_modelo)}</div>
          <div className="numero-nota">medido no teste, fev/2025–jan/2026</div>
        </div>
        <div className="cartao">
          <div className="numero-rotulo">Regra simples “volta ao normal”</div>
          <div className="numero-valor">{porcentagem(frase.precisao_lista_regra_simples)}</div>
          <div className="numero-nota">se perdeu força, aposta que ganha</div>
        </div>
        <div className="cartao">
          <div className="numero-rotulo">Ao acaso</div>
          <div className="numero-valor">{porcentagem(frase.precisao_acaso)}</div>
          <div className="numero-nota">fração que ganhou força no teste</div>
        </div>
        <div className="cartao">
          <div className="numero-rotulo">Saldo somado da lista “expandir”</div>
          <div className="numero-valor">{reais(frase.saldo_total_lista_expandir_rs)}</div>
          <div className="numero-nota">saldo de carteira em jun/2026</div>
        </div>
      </div>

      <div className="duas-colunas">
        <section>
          <h2>Expandir: {n} maiores chances de ganhar força</h2>
          <p className="nota">
            “Ganhar força” = o saldo crescer mais no trimestre {frase.trimestre_recomendado} do que cresceu nos
            últimos 3 meses.
          </p>
          <TabelaLista linhas={expandir} grupo="expandir" />
        </section>
        <section>
          <h2>Alerta: {n} maiores chances de perder força</h2>
          <p className="nota">Combinações onde expandir agora tende a custar caro.</p>
          <TabelaLista linhas={alerta} grupo="alerta" />
        </section>
      </div>

      <p className="nota" style={{ marginTop: 24 }}>
        Ressalvas: associação não é causa; as chances mais extremas aparecem em mercados pequenos (por isso a
        prioridade para os de maior saldo); a avaliação cobre 12 meses de um só ciclo de juros altos.
      </p>
    </main>
  );
}
