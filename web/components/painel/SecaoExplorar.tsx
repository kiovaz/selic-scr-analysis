"use client";
/**
 * 05 · Explorar — uma combinação estado × modalidade em detalhe.
 *
 * A série mensal (gold_credito_selic) vem da rota /api/combinacao quando o
 * visitante troca a seleção; as demais informações (probabilidade, correlação,
 * posição nas listas) já estão nos dados da página.
 */
import { useEffect, useRef, useState } from "react";
import type { DadosPainel, MesCombinacao } from "@/lib/tipos";
import { comSinal, mesPorExtenso, numero, reais } from "@/lib/formato";
import { infoModalidade } from "@/lib/modalidades";
import { UFS } from "@/lib/ufs";
import { Rotulos, Termo, useLargura, type Rotulo } from "./apoio";
import { alinhar, chave, mesDaOrigem, mesesDoRecorte, modalidadesDoSite } from "./derivados";

type Combinacao = { uf: string; modalidade: string };

export default function SecaoExplorar({ dados, combinacao, setCombinacao }: {
  dados: DadosPainel;
  combinacao: Combinacao;
  setCombinacao: (c: Combinacao) => void;
}) {
  const { uf, modalidade } = combinacao;
  const k = chave(uf, modalidade);

  // Séries já buscadas ficam guardadas: voltar a uma combinação não consulta o banco de novo.
  const guardadas = useRef(
    new Map<string, MesCombinacao[]>([
      [chave(dados.combinacaoInicial.uf, dados.combinacaoInicial.modalidade), dados.combinacaoInicial.serie],
    ]),
  );
  const [serie, setSerie] = useState<MesCombinacao[]>(dados.combinacaoInicial.serie);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    const guardada = guardadas.current.get(k);
    if (guardada) {
      setSerie(guardada);
      setErro(false);
      return;
    }
    let cancelado = false;
    setCarregando(true);
    fetch(`/api/combinacao?uf=${encodeURIComponent(uf)}&modalidade=${encodeURIComponent(modalidade)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((linhas: MesCombinacao[]) => {
        guardadas.current.set(k, linhas);
        if (!cancelado) {
          setSerie(linhas);
          setErro(false);
        }
      })
      .catch(() => !cancelado && setErro(true))
      .finally(() => !cancelado && setCarregando(false));
    return () => {
      cancelado = true;
    };
  }, [k, uf, modalidade]);

  const meses = mesesDoRecorte(dados);
  const volume = alinhar(serie, meses, (l) => l.volume_rs);
  const variacao = alinhar(serie, meses, (l) => l.var_volume_pct);
  const qtd = alinhar(serie, meses, (l) => l.qtd_operacoes);
  const selic = dados.selic.map((p) => p.selic_pct);
  const ultimo = meses.length - 1;
  const origem = mesDaOrigem(dados);

  const previsao = dados.previsoes.find((p) => p.uf === uf && p.modalidade === modalidade);
  const correlacao = dados.correlacoesUf.find((c) => c.uf === uf && c.modalidade === modalidade);
  const naLista = dados.recomendacao.find((r) => r.uf === uf && r.modalidade === modalidade);
  const corSelo = naLista ? (naLista.grupo === "expandir" ? "var(--expand)" : "var(--alert)") : "var(--muted)";
  const textoSelo = naLista
    ? `Lista ${naLista.grupo} · ${naLista.posicao}ª posição`
    : "Fora das listas do trimestre";
  const semCorrelacao = !correlacao || correlacao.amostra_insuficiente || correlacao.spearman === null;

  return (
    <section id="explorar" className="secao">
      <div className="container">
        <div className="rotulo-secao">05 · Explorar</div>
        <h2 className="titulo-secao">Uma combinação em detalhe</h2>

        <div className="seletores">
          <label>
            Estado
            <select value={uf} onChange={(e) => setCombinacao({ uf: e.target.value, modalidade })}>
              {UFS.map((u) => (
                <option key={u.sigla} value={u.sigla}>
                  {u.sigla} · {u.nome}
                </option>
              ))}
            </select>
          </label>
          <label>
            Modalidade
            <select value={modalidade} onChange={(e) => setCombinacao({ uf, modalidade: e.target.value })}>
              {modalidadesDoSite(dados).map((m) => (
                <option key={m} value={m}>
                  {infoModalidade(m).nome}
                </option>
              ))}
            </select>
          </label>
          <span className="selo" style={{ borderColor: corSelo, color: corSelo }}>
            <span className="ponto" style={{ background: corSelo }} />
            {textoSelo}
          </span>
        </div>

        <div className="indicadores-explorar">
          <div>
            <div className="apagado pequeno-medio">
              <Termo id="prob">Probabilidade de ganhar força</Termo>
            </div>
            <div className="numero-explorar">{previsao ? numero(previsao.prob_ganha_forca, 3) : "sem previsão"}</div>
            <div className="apagado pequeno-medio">
              {previsao ? dados.frase.trimestre_recomendado : "Fora das 174 combinações analisadas pelo modelo"}
            </div>
          </div>
          <div>
            <div className="apagado pequeno-medio">
              <Termo id="saldo">Saldo de carteira</Termo>
            </div>
            <div className="numero-explorar">{reais(volume[ultimo])}</div>
            <div className="apagado pequeno-medio">{origem}</div>
          </div>
          <div>
            <div className="apagado pequeno-medio">
              Correlação com a <Termo id="selic">Selic</Termo>
            </div>
            <div className="numero-explorar">{semCorrelacao ? "—" : comSinal(correlacao!.spearman)}</div>
            <div className="apagado pequeno-medio">
              {semCorrelacao
                ? `Amostra insuficiente (${correlacao?.n_meses ?? 0} meses)`
                : `Defasagem ${correlacao!.defasagem_meses} meses · ${correlacao!.significativo ? "significativo" : "não significativo"}`}
            </div>
          </div>
          <div>
            <div className="apagado pequeno-medio">Operações divulgadas</div>
            <div className="numero-explorar">{qtd[ultimo] === null ? "—" : `≥ ${numero(qtd[ultimo], 0)}`}</div>
            <div className="apagado pequeno-medio">
              {origem} · <Termo id="limiteInferior">limite inferior</Termo>
            </div>
          </div>
        </div>

        <div className={carregando ? "graficos-explorar carregando" : "graficos-explorar"} aria-busy={carregando}>
          {erro ? (
            <p className="apagado">Não foi possível carregar a série desta combinação. Tente de novo em instantes.</p>
          ) : (
            <GraficosCombinacao meses={meses} volume={volume} variacao={variacao} qtd={qtd} selic={selic} />
          )}
        </div>
      </div>
    </section>
  );
}

function GraficosCombinacao({ meses, volume, variacao, qtd, selic }: {
  meses: string[];
  volume: (number | null)[];
  variacao: (number | null)[];
  qtd: (number | null)[];
  selic: number[];
}) {
  const caixa = useRef<HTMLDivElement>(null);
  const W = Math.max(300, Math.min(useLargura(caixa), 1100));
  const estreito = W < 620;
  const n = meses.length;

  // ----- Saldo (eixo à esquerda) e Selic (eixo à direita) -----
  const H = estreito ? 220 : 280;
  const [pl, pr, pt, pb] = [estreito ? 64 : 72, 40, 12, 26];
  const iw = W - pl - pr;
  const ih = H - pt - pb;
  const x = (i: number) => pl + (i * iw) / Math.max(1, n - 1);
  const vMax = Math.max(1, ...volume.map((v) => v ?? 0)) * 1.08;
  const topoSelic = Math.max(4, Math.ceil(Math.max(...selic) / 4) * 4);
  const y = (v: number) => pt + ih * (1 - v / vMax);
  const ys = (v: number) => pt + ih * (1 - v / topoSelic);

  // Mês sem dado interrompe a linha do saldo: a lacuna aparece, sem preenchimento.
  let caminho = "";
  let caneta = false;
  volume.forEach((v, i) => {
    if (v === null) {
      caneta = false;
      return;
    }
    caminho += `${caneta ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    caneta = true;
  });
  let caminhoSelic = `M${x(0)},${ys(selic[0])}`;
  for (let i = 1; i < n; i++) caminhoSelic += `H${x(i).toFixed(1)}V${ys(selic[i]).toFixed(1)}`;

  const grade = [0, 0.5, 1];
  const anos = meses
    .map((m, i) => ({ m, i }))
    .filter((o) => o.m.endsWith("-01") && (!estreito || Number(o.m.slice(0, 4)) % 2 === 0));
  const rotulos: Rotulo[] = [
    ...grade.map((fr) => ({ x: pl - 8, y: y(vMax * fr) + 4, texto: reais(vMax * fr), ancora: "fim" as const })),
    ...grade.map((fr) => ({ x: W - pr + 8, y: y(vMax * fr) + 4, texto: `${numero(topoSelic * fr, 0)}%`, ancora: "inicio" as const })),
    ...anos.map((a) => ({ x: x(a.i), y: H - 6, texto: a.m.slice(0, 4) })),
  ];
  const textoVariacao = (v: number | null) => (v === null ? "sem dado" : `${comSinal(v, 1)}%`);

  // ----- Variação mensal do saldo -----
  const VH = 110;
  const vpt = 8;
  const vih = VH - vpt - 8;
  // Limite da escala no percentil 98, para um mês extremo não achatar os demais.
  const absolutas = variacao.filter((v): v is number => v !== null).map(Math.abs).sort((a, b) => a - b);
  const limite = Math.max(1, absolutas.length ? absolutas[Math.floor(absolutas.length * 0.98)] : 1);
  const y0 = vpt + vih / 2;
  const larguraBarra = Math.max(1, (iw / n) * 0.7);

  return (
    <div ref={caixa}>
      <div className="legenda" style={{ marginTop: 0 }}>
        <span><span className="legenda-linha" style={{ background: "var(--primary)" }} />Saldo de carteira (eixo à esquerda)</span>
        <span><span className="legenda-tracejada" />Selic meta (eixo à direita)</span>
      </div>
      <div className="grafico" style={{ marginTop: 10 }}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Saldo de carteira e Selic meta mês a mês">
          {grade.map((fr) => (
            <line key={fr} x1={pl} x2={W - pr} y1={y(vMax * fr)} y2={y(vMax * fr)} stroke="var(--line)" strokeWidth={1} />
          ))}
          <path d={caminhoSelic} fill="none" stroke="var(--muted)" strokeWidth={1.5} strokeDasharray="4 3" />
          <path d={caminho} fill="none" stroke="var(--primary)" strokeWidth={2.25} strokeLinejoin="round" />
          {meses.map((m, i) => (
            <rect
              key={m}
              x={x(i) - iw / (2 * (n - 1))}
              y={pt}
              width={iw / (n - 1)}
              height={ih}
              fill="transparent"
              data-tip={
                `${mesPorExtenso(m)} · saldo ${reais(volume[i])} · var. ${textoVariacao(variacao[i])} · ` +
                `Selic ${numero(selic[i], 2)}% · operações ${qtd[i] === null ? "—" : `≥ ${numero(qtd[i], 0)}`}`
              }
            />
          ))}
        </svg>
        <Rotulos itens={rotulos} largura={W} altura={H} />
      </div>

      <div className="titulo-variacao">Variação mensal do saldo</div>
      <div className="apagado pequeno">
        Faixas cinza: mês sem dado anterior para comparar. A lacuna é mostrada, sem preenchimento.
      </div>
      <div className="grafico" style={{ marginTop: 8 }}>
        <svg viewBox={`0 0 ${W} ${VH}`} width="100%" role="img" aria-label="Variação mensal do saldo">
          {variacao.map((v, i) =>
            v === null && i > 0 ? (
              <rect
                key={`lacuna-${i}`}
                x={x(i) - iw / (2 * (n - 1))}
                y={vpt}
                width={iw / (n - 1)}
                height={vih}
                fill="var(--line)"
                data-tip={`${mesPorExtenso(meses[i])} · ${volume[i] === null ? "sem operação no mês" : "sem dado no mês anterior"}`}
              />
            ) : null,
          )}
          <line x1={pl} x2={W - pr} y1={y0} y2={y0} stroke="var(--line2)" strokeWidth={1} />
          {variacao.map((v, i) => {
            if (v === null) return null;
            const c = Math.max(-limite, Math.min(limite, v));
            const h = Math.max(0.5, ((Math.abs(c) / limite) * vih) / 2);
            return (
              <rect
                key={meses[i]}
                x={x(i) - larguraBarra / 2}
                y={c >= 0 ? y0 - h : y0}
                width={larguraBarra}
                height={h}
                fill={c >= 0 ? "var(--primary)" : "var(--muted)"}
                data-tip={`${mesPorExtenso(meses[i])} · ${comSinal(v, 1)}% no mês`}
              />
            );
          })}
        </svg>
        <Rotulos
          itens={[
            { x: pl - 8, y: vpt + 10, texto: `${comSinal(limite, 1)}%`, ancora: "fim" },
            { x: pl - 8, y: vpt + vih, texto: `${comSinal(-limite, 1)}%`, ancora: "fim" },
          ]}
          largura={W}
          altura={VH}
        />
      </div>
    </div>
  );
}
