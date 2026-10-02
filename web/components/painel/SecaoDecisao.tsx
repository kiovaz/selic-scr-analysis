"use client";
/**
 * 01 · Decisão — a recomendação em resumo e a frase de fechamento do projeto.
 * Todos os números vêm de frase_fechamento (gerada pelo pipeline em src/ml/decisao.py).
 */
import type { DadosPainel } from "@/lib/tipos";
import { comSinal, numero, porcentagem } from "@/lib/formato";
import { Termo, useProgresso } from "./apoio";
import { mesDaOrigem } from "./derivados";
import { infoModalidade } from "@/lib/modalidades";

export default function SecaoDecisao({ dados }: { dados: DadosPainel }) {
  const f = dados.frase;
  const t = useProgresso(); // contagem de 0 até o valor, ao abrir a página
  const origem = mesDaOrigem(dados);
  const assoc = f.associacao_mais_forte_sprint4;
  // Modalidade de associação mais forte (Imobiliário na última execução), em minúsculas para a frase.
  const modForte = infoModalidade(assoc.modalidade).nome.toLowerCase();

  const comparacao = [
    { nome: "Modelo", valor: f.precisao_lista_modelo, cor: "var(--primary)" },
    { nome: "Regra simples", valor: f.precisao_lista_regra_simples, cor: "var(--muted)" },
    { nome: "Acaso", valor: f.precisao_acaso, cor: "var(--line2)" },
  ];

  return (
    <section id="decisao" className="secao secao-abertura">
      <div className="container">
        <div className="rotulo-secao">Projeto de Engenharia de Dados · SCR.data × Selic meta</div>
        <h1 className="titulo-principal">
          Expandir crédito em {f.tamanho_lista} combinações de estado e modalidade em {f.trimestre_recomendado}
        </h1>
        <p className="subtitulo">
          A <Termo id="selic">Selic meta</Termo> anda junto com o crédito {modForte}, mas não ajuda a prever o
          trimestre seguinte. O que antecipa é o ritmo recente do próprio crédito em cada estado.
        </p>

        <div className="indicadores">
          <div className="indicador">
            <div className="indicador-rotulo">
              <Termo id="acerto20">Acerto nas {f.tamanho_lista} recomendações</Termo>
            </div>
            <div className="indicador-valor">{porcentagem(f.precisao_lista_modelo * t)}</div>
            <div className="mini-barras">
              {comparacao.map((c) => (
                <div key={c.nome} className="mini-barra">
                  <span>{c.nome}</span>
                  <span className="barra-trilho">
                    <span className="barra-preenchida" style={{ width: `${c.valor * 100 * t}%`, background: c.cor }} />
                  </span>
                  <span className="mini-barra-valor">{porcentagem(c.valor)}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="indicador">
            <div className="indicador-rotulo">
              <Termo id="saldo">Saldo</Termo> das combinações recomendadas
            </div>
            <div className="indicador-valor">
              <span className="indicador-unidade">R$</span>
              {numero((f.saldo_total_lista_expandir_rs / 1e9) * t, 1)}
              <span className="indicador-unidade">bi</span>
            </div>
            <div className="indicador-nota">Saldo de carteira em {origem}</div>
          </div>
          <div className="indicador">
            <div className="indicador-rotulo">Combinações recomendadas</div>
            <div className="indicador-valor">{Math.round(f.tamanho_lista * t)}</div>
            <div className="indicador-nota">
              Estado × <Termo id="modalidade">modalidade</Termo>
            </div>
          </div>
          <div className="indicador">
            <div className="indicador-rotulo">
              <Termo id="trimestre">Trimestre recomendado</Termo>
            </div>
            <div className="indicador-valor indicador-valor-texto">{f.trimestre_recomendado}</div>
            <div className="indicador-nota">Previsão feita com dados de {origem}</div>
          </div>
        </div>

        <div className="conclusao">
          <div className="rotulo-secao conclusao-rotulo">A conclusão</div>
          <p className="ocupa-2">
            Cruzando o SCR.data (Banco Central) e a <Termo id="selic">Selic meta</Termo> do <Termo id="copom">Copom</Termo>{" "}
            (Ipeadata), identificamos que o saldo do crédito {modForte} anda junto com a Selic de {assoc.defasagem_meses}{" "}
            meses antes (<Termo id="spearman">Spearman</Termo> {comSinal(assoc.spearman)}), mas a Selic não antecipa o
            trimestre seguinte. O que antecipa é o ritmo recente do próprio crédito em cada estado. Recomendamos que a
            diretoria de crédito de uma instituição financeira de atuação nacional expanda a oferta de financiamento nas{" "}
            {f.tamanho_lista} combinações estado × modalidade com maior{" "}
            <Termo id="prob">probabilidade de ganhar força</Termo> nos próximos 3 meses ({f.trimestre_recomendado}),
            priorizando as de maior saldo dentro da lista. Se agir, o ganho esperado é acertar cerca de{" "}
            {numero(f.acertos_esperados_modelo, 1)} de {f.tamanho_lista} expansões por trimestre (
            {porcentagem(f.precisao_lista_modelo)}), contra cerca de {numero(f.acertos_esperados_regra_simples, 1)} da{" "}
            <Termo id="regra">regra simples</Termo> e cerca de {numero(f.acertos_esperados_acaso, 1)} ao acaso. Se
            errarmos, o custo é de cerca de {numero(f.erros_esperados_modelo, 1)} expansões por trimestre em mercados que
            estão perdendo força: capital, captação e equipe comercial alocados sem retorno no trimestre.
          </p>
        </div>
      </div>
    </section>
  );
}
