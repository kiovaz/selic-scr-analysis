"use client";
/**
 * 02 · Recomendação — as 20 combinações para expandir e as 20 em alerta
 * (recomendacao_trimestre), com a probabilidade sempre ao lado do saldo.
 */
import { useState } from "react";
import type { DadosPainel, LinhaRecomendacao } from "@/lib/tipos";
import { numero, reais } from "@/lib/formato";
import { infoModalidade } from "@/lib/modalidades";
import { nomeUf } from "@/lib/ufs";
import { Alternador, Termo, useSecao } from "./apoio";
import { mesDaOrigem } from "./derivados";
import MapaGrade from "./MapaGrade";

type Aba = "expandir" | "alerta";
type Ordem = "prob" | "saldo";

export default function SecaoRecomendacao({ dados, abrirCombinacao }: {
  dados: DadosPainel;
  abrirCombinacao: (uf: string, modalidade: string) => void;
}) {
  const { ref, visivel } = useSecao();
  const [aba, setAba] = useState<Aba>("expandir");
  const [ordem, setOrdem] = useState<Ordem>("prob");
  const f = dados.frase;
  const origem = mesDaOrigem(dados);
  const cor = aba === "expandir" ? "var(--expand)" : "var(--alert)";

  const lista = dados.recomendacao
    .filter((r) => r.grupo === aba)
    .sort((a, b) => (ordem === "saldo" ? (b.volume_rs ?? 0) - (a.volume_rs ?? 0) : a.posicao - b.posicao));
  const maiorSaldo = Math.max(1, ...lista.map((r) => r.volume_rs ?? 0));

  // Estados presentes na lista (para o mapa) e contagem por modalidade.
  const porUf = new Map<string, LinhaRecomendacao[]>();
  lista.forEach((r) => porUf.set(r.uf, [...(porUf.get(r.uf) ?? []), r]));
  const porModalidade = new Map<string, number>();
  lista.forEach((r) => {
    const nome = infoModalidade(r.modalidade).nome;
    porModalidade.set(nome, (porModalidade.get(nome) ?? 0) + 1);
  });
  const contagem = [...porModalidade.entries()].sort((a, b) => b[1] - a[1]);
  const nRural = dados.recomendacao.filter(
    (r) => r.grupo === "expandir" && infoModalidade(r.modalidade).chave === "rural",
  ).length;
  const nExpandir = dados.recomendacao.filter((r) => r.grupo === "expandir").length;

  return (
    <section id="recomendacao" ref={ref} className="secao secao-clara">
      <div className="container">
        <div className="rotulo-secao">02 · A recomendação</div>
        <h2 className="titulo-secao" style={{ maxWidth: "24ch" }}>
          Onde expandir e onde ter cautela em {f.trimestre_recomendado}
        </h2>
        <p className="texto-apoio">
          Cada linha é uma combinação de estado e modalidade, com a <Termo id="prob">probabilidade de ganhar força</Termo>{" "}
          ao lado do saldo em {origem}. Clique numa linha para ver a combinação em detalhe.
        </p>

        <div className="controles">
          <Alternador<Aba>
            grande
            opcoes={[
              { id: "expandir", rotulo: "Expandir", ponto: "var(--expand)" },
              { id: "alerta", rotulo: "Alerta", ponto: "var(--alert)" },
            ]}
            atual={aba}
            aoEscolher={setAba}
          />
          <div className="controle-ordem">
            <span>Ordenar por</span>
            <Alternador<Ordem>
              opcoes={[
                { id: "prob", rotulo: "Probabilidade" },
                { id: "saldo", rotulo: "Saldo" },
              ]}
              atual={ordem}
              aoEscolher={setOrdem}
            />
          </div>
        </div>

        <div className="grade-recomendacao">
          <div className="ocupa-2" style={{ minWidth: 0 }}>
            <div className="linha-rec linha-rec-cabecalho">
              <span>Pos.</span>
              <span>Estado · modalidade</span>
              <span>Probabilidade</span>
              <span>Saldo {origem}</span>
            </div>
            {lista.map((r) => (
              <div
                key={`${r.uf}-${r.modalidade}`}
                className="linha-rec clicavel"
                role="button"
                tabIndex={0}
                onClick={() => abrirCombinacao(r.uf, r.modalidade)}
                onKeyDown={(e) => e.key === "Enter" && abrirCombinacao(r.uf, r.modalidade)}
              >
                <span className="mono apagado">{String(r.posicao).padStart(2, "0")}</span>
                <span className="linha-rec-nome">
                  <span className="truncar">
                    <strong>{r.uf}</strong> <span className="apagado">{nomeUf(r.uf)}</span>
                  </span>
                  <span className="truncar apagado pequeno">{infoModalidade(r.modalidade).nome}</span>
                </span>
                <span className="coluna-barra">
                  <strong>{numero(r.prob_ganha_forca, 3)}</strong>
                  <span className="barra-trilho barra-fina">
                    <span
                      className="barra-preenchida barra-media"
                      style={{ width: `${visivel ? r.prob_ganha_forca * 100 : 0}%`, background: cor }}
                    />
                  </span>
                </span>
                <span className="coluna-barra">
                  <span>{reais(r.volume_rs)}</span>
                  <span className="barra-trilho barra-fina">
                    <span
                      className="barra-preenchida barra-media"
                      style={{ width: `${visivel ? ((r.volume_rs ?? 0) / maiorSaldo) * 100 : 0}%`, background: "var(--muted)" }}
                    />
                  </span>
                </span>
              </div>
            ))}
          </div>

          <aside className="lateral">
            <div>
              <div className="lateral-titulo">Estados presentes na lista</div>
              <MapaGrade
                larguraMaxima={300}
                quadrado={(sigla, nome) => {
                  const itens = porUf.get(sigla) ?? [];
                  return {
                    fundo: itens.length ? cor : "var(--surface2)",
                    texto: itens.length ? "var(--on-accent)" : "var(--muted)",
                    dica:
                      `${nome}: ` +
                      (itens.length
                        ? itens
                            .map((x) => `${infoModalidade(x.modalidade).nome} (${numero(x.prob_ganha_forca, 3)}; ${reais(x.volume_rs)})`)
                            .join(" · ")
                        : "fora da lista"),
                  };
                }}
              />
              <div className="nota">Mapa em grade: cada quadrado é um estado, na posição aproximada.</div>
            </div>
            <div>
              <div className="lateral-titulo">Modalidades na lista</div>
              <div className="lista-contagem">
                {contagem.map(([nome, n]) => (
                  <div key={nome}>
                    <span className="apagado">{nome}</span>
                    <strong>{n}</strong>
                  </div>
                ))}
              </div>
            </div>
            {aba === "expandir" ? (
              <div className="texto-lateral">
                <p>
                  <strong>
                    {nRural} das {nExpandir}
                  </strong>{" "}
                  combinações são de financiamento rural, o que coincide com o plantio da safra de verão no período.
                </p>
                <p className="apagado">
                  As notas mais altas aparecem em mercados pequenos (exportação e importação em estados menores), que
                  oscilam muito. Por isso a lista mostra o saldo, e a recomendação é priorizar as de maior saldo.
                </p>
              </div>
            ) : (
              <p className="texto-lateral apagado">
                As {lista.length} combinações com menor probabilidade de ganhar força tendem a perder força no trimestre.
                Expandir nelas significa alocar capital, captação e equipe comercial sem retorno.
              </p>
            )}
          </aside>
        </div>
      </div>
    </section>
  );
}
