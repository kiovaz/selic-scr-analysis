"use client";
/**
 * 03 · Selic × crédito — andam juntos?
 *
 * a) Linha do tempo da Selic meta, com as decisões do Copom marcadas e, se o
 *    visitante escolher, o saldo do Brasil numa modalidade por cima.
 * b) Correlação de Spearman por modalidade e defasagem (analise_brasil_modalidade).
 * c) Por que a correlação é positiva (texto do notebook 02).
 * d) Mapa de calor estado × modalidade (analise_uf_modalidade), em grade ou mapa.
 *
 * Regra do projeto: compara-se a VARIAÇÃO do crédito com a variação da Selic,
 * nunca os níveis — as correlações já vêm prontas do pipeline.
 */
import { useRef, useState } from "react";
import type { Correlacao, CorrelacaoUf, DadosPainel } from "@/lib/tipos";
import { comSinal, mesPorExtenso, numero, reais } from "@/lib/formato";
import { infoModalidade } from "@/lib/modalidades";
import { nomeUf, UFS } from "@/lib/ufs";
import { Alternador, Pilula, Rotulos, Termo, useLargura, type Rotulo } from "./apoio";
import { alinhar, chave, mesesDoRecorte, modalidadesDoSite } from "./derivados";
import MapaGrade from "./MapaGrade";

type Abrir = (uf: string, modalidade: string) => void;

/** Cor de uma correlação: vermelho (anda junto) ou azul (sentido oposto), mais forte quanto maior o valor. */
export function corDaCorrelacao(r: number | null): string {
  if (r === null) return "repeating-linear-gradient(45deg,var(--line2) 0 2px,transparent 2px 5px)";
  const p = Math.min(1, Math.abs(r) / 0.6);
  if (p < 0.08) return "var(--cell0)";
  return `color-mix(in oklch, ${r > 0 ? "var(--pos)" : "var(--neg)"} ${Math.round(20 + 80 * p)}%, var(--cell0))`;
}

const meses = (k: number) => `${k} ${k === 1 ? "mês" : "meses"}`;

export default function SecaoSelic({ dados, abrirCombinacao }: { dados: DadosPainel; abrirCombinacao: Abrir }) {
  const forte = dados.frase.associacao_mais_forte_sprint4;
  const nMudancas = dados.selic.filter((p) => (p.var_selic_pp ?? 0) !== 0).length;

  return (
    <section id="selic" className="secao">
      <div className="container">
        <div className="rotulo-secao">03 · Selic × crédito</div>
        <h2 className="titulo-secao">Andam juntos?</h2>
        <p className="texto-apoio">
          Em parte. O crédito {infoModalidade(forte.modalidade).nome.toLowerCase()} mostra a{" "}
          <Termo id="associacao">associação</Termo> mais forte com a Selic, com {meses(forte.defasagem_meses)} de{" "}
          <Termo id="defasagem">defasagem</Termo>. Nas demais modalidades, a relação é fraca ou pode ser acaso.
        </p>

        <div className="bloco">
          <div className="bloco-cabecalho">
            <h3>Selic meta, mês a mês</h3>
            <div className="apagado pequeno-medio">
              O <Termo id="copom">Copom</Termo> mudou a taxa em <strong className="tinta">{nMudancas}</strong> dos{" "}
              {dados.selic.length} meses
            </div>
          </div>
          <GraficoSelic dados={dados} />
        </div>

        <div className="bloco">
          <h3>Correlação por modalidade e defasagem</h3>
          <p className="texto-apoio texto-menor">
            Cada barra é a <Termo id="spearman">correlação de Spearman</Termo> entre a variação do saldo do Brasil e a
            variação da Selic de 0 a 6 meses antes. Barra cheia: <Termo id="significativo">significativo</Termo>. Só
            contorno: pode ser acaso.
          </p>
          <CartoesCorrelacao dados={dados} />
          <div className="nota">Eixo: defasagem em meses. Vermelho: anda junto. Azul: sentidos opostos.</div>
        </div>

        <div className="bloco caixa-explicacao">
          <h3>Por que a correlação é positiva?</h3>
          <p className="ocupa-2">
            A intuição diz que juros altos derrubam o crédito, o que daria uma correlação negativa. A correlação positiva
            é compatível com o Copom subindo os juros justamente quando a economia e o crédito estão aquecidos, e
            cortando quando esfriam: os dois respondem ao mesmo ciclo. Além disso, o crédito imobiliário e o rural têm
            juros subsidiados e indexadores próprios, que reagem menos à Selic. Por isso o resultado é descrito como{" "}
            <Termo id="associacao">associação</Termo>, não como efeito da Selic.
          </p>
        </div>

        <MapaDeCalor dados={dados} abrirCombinacao={abrirCombinacao} />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------
// a) Linha do tempo da Selic
// ---------------------------------------------------------------------

function GraficoSelic({ dados }: { dados: DadosPainel }) {
  const caixa = useRef<HTMLDivElement>(null);
  const W = Math.max(300, Math.min(useLargura(caixa), 1100));
  const estreito = W < 620;
  const [modSobreposta, setModSobreposta] = useState("");

  const S = dados.selic;
  const listaMeses = mesesDoRecorte(dados);
  const n = S.length;
  const H = estreito ? 240 : 300;
  const [pl, pr, pt, pb] = [40, modSobreposta ? 64 : 12, 24, 28];
  const iw = W - pl - pr;
  const ih = H - pt - pb;
  const valores = S.map((p) => p.selic_pct);
  const topo = Math.max(4, Math.ceil(Math.max(...valores) / 4) * 4); // eixo até o múltiplo de 4 acima do máximo
  const x = (i: number) => pl + (i * iw) / Math.max(1, n - 1);
  const y = (v: number) => pt + ih * (1 - v / topo);

  // A meta só muda nas reuniões do Copom: o desenho é em degraus.
  let caminho = `M${x(0)},${y(S[0].selic_pct)}`;
  for (let i = 1; i < n; i++) caminho += `H${x(i).toFixed(1)}V${y(S[i].selic_pct).toFixed(1)}`;

  const linhasGrade = [0, 1, 2, 3, 4].map((k) => (topo * k) / 4);
  const anos = listaMeses
    .map((m, i) => ({ m, i }))
    .filter((o) => o.m.endsWith("-01") && (!estreito || Number(o.m.slice(0, 4)) % 2 === 0));
  const decisoes = S.map((p, i) => ({ p, i })).filter((o) => (o.p.var_selic_pp ?? 0) !== 0);
  const iMax = valores.indexOf(Math.max(...valores));
  const iMin = valores.indexOf(Math.min(...valores));

  // Saldo do Brasil na modalidade escolhida, com eixo próprio à direita.
  const brasil = modSobreposta
    ? alinhar(dados.saldoBrasil.filter((s) => s.modalidade === modSobreposta), listaMeses, (s) => s.valor)
    : null;
  const bMax = brasil ? Math.max(1, ...brasil.map((v) => v ?? 0)) * 1.1 : 1;
  const yb = (v: number) => pt + ih * (1 - v / bMax);
  let caminhoBrasil = "";
  if (brasil) {
    let caneta = false;
    brasil.forEach((v, i) => {
      if (v === null) {
        caneta = false;
        return;
      }
      caminhoBrasil += `${caneta ? "L" : "M"}${x(i).toFixed(1)},${yb(v).toFixed(1)}`;
      caneta = true;
    });
  }

  const rotulos: Rotulo[] = [
    ...linhasGrade.map((g) => ({ x: pl - 8, y: y(g) + 4, texto: `${numero(g, 0)}%`, ancora: "fim" as const })),
    ...anos.map((a) => ({ x: x(a.i), y: H - 8, texto: a.m.slice(0, 4) })),
    ...(brasil
      ? [0, 0.5, 1].map((fr) => ({ x: W - pr + 8, y: yb(bMax * fr) + 4, texto: reais(bMax * fr), ancora: "inicio" as const, cor: "var(--expand)" }))
      : []),
    { x: x(iMax), y: y(valores[iMax]) - 10, texto: `máx. ${numero(valores[iMax], 2)}% · ${mesPorExtenso(listaMeses[iMax])}`, cor: "var(--ink)", peso: 600, tamanho: 12 },
    { x: x(iMin), y: y(valores[iMin]) + 20, texto: `mín. ${numero(valores[iMin], 2)}% · ${mesPorExtenso(listaMeses[iMin])}`, cor: "var(--ink)", peso: 600, tamanho: 12 },
  ];
  const nomeSobreposta = modSobreposta ? infoModalidade(modSobreposta).nome.toLowerCase() : "";

  return (
    <>
      <div className="filtros-pilula">
        <span className="apagado pequeno-medio">Sobrepor saldo do Brasil:</span>
        <Pilula ativo={modSobreposta === ""} onClick={() => setModSobreposta("")}>
          Nenhum
        </Pilula>
        {modalidadesDoSite(dados).map((m) => (
          <Pilula key={m} ativo={modSobreposta === m} onClick={() => setModSobreposta(m)}>
            {infoModalidade(m).nome}
          </Pilula>
        ))}
      </div>
      <div ref={caixa} className="grafico">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Selic meta mês a mês">
          {linhasGrade.map((g) => (
            <line key={g} x1={pl} x2={W - pr} y1={y(g)} y2={y(g)} stroke="var(--line)" strokeWidth={1} />
          ))}
          {brasil && <path d={caminhoBrasil} fill="none" stroke="var(--expand)" strokeWidth={2} strokeLinejoin="round" />}
          <path d={caminho} fill="none" stroke="var(--primary)" strokeWidth={2.25} strokeLinejoin="round" />
          {decisoes.map(({ p, i }) => (
            <circle
              key={p.mes}
              cx={x(i)}
              cy={y(p.selic_pct)}
              r={3.2}
              fill={(p.var_selic_pp ?? 0) > 0 ? "var(--primary)" : "var(--bg)"}
              stroke="var(--primary)"
              strokeWidth={1.5}
            />
          ))}
          {S.map((p, i) => (
            <rect
              key={p.mes}
              x={x(i) - iw / (2 * (n - 1))}
              y={pt}
              width={iw / (n - 1)}
              height={ih}
              fill="transparent"
              data-tip={
                `${mesPorExtenso(p.mes)} · Selic ${numero(p.selic_pct, 2)}% a.a.` +
                (p.var_selic_pp ? ` · Copom ${comSinal(p.var_selic_pp)} p.p.` : "") +
                (brasil ? ` · saldo ${reais(brasil[i])}` : "")
              }
            />
          ))}
        </svg>
        <Rotulos itens={rotulos} largura={W} altura={H} />
      </div>
      <div className="legenda">
        <span><span className="legenda-linha" style={{ background: "var(--primary)" }} />Selic meta (% a.a.)</span>
        <span><span className="legenda-ponto" style={{ background: "var(--primary)" }} />Alta do Copom</span>
        <span><span className="legenda-ponto legenda-ponto-vazio" />Corte do Copom</span>
        {brasil && (
          <span>
            <span className="legenda-linha" style={{ background: "var(--expand)" }} />
            Saldo do Brasil, {nomeSobreposta} (eixo à direita)
          </span>
        )}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------
// b) Correlação por modalidade e defasagem
// ---------------------------------------------------------------------

function CartoesCorrelacao({ dados }: { dados: DadosPainel }) {
  const forte = dados.frase.associacao_mais_forte_sprint4.modalidade;
  return (
    <div className="grade-cartoes">
      {modalidadesDoSite(dados).map((m) => {
        const linhas = dados.correlacoesBrasil
          .filter((c) => c.modalidade === m && c.spearman !== null)
          .sort((a, b) => a.defasagem_meses - b.defasagem_meses);
        if (!linhas.length) return null;
        // Destaque: a defasagem de maior |Spearman| da modalidade.
        const melhor = linhas.reduce((a, b) => (Math.abs(b.spearman!) > Math.abs(a.spearman!) ? b : a));
        const nome = infoModalidade(m).nome;
        return (
          <div key={m} className={m === forte ? "cartao cartao-destaque" : "cartao"}>
            <div className="cartao-cabecalho">
              <span>{nome}</span>
              {m === forte && <span className="selo-forte">Mais forte</span>}
            </div>
            <div className="apagado pequeno">
              Melhor defasagem: {meses(melhor.defasagem_meses)}
              {melhor.significativo ? " · significativo" : ""}
            </div>
            <BarrasDefasagem linhas={linhas} melhor={melhor} nome={nome} />
          </div>
        );
      })}
    </div>
  );
}

function BarrasDefasagem({ linhas, melhor, nome }: { linhas: Correlacao[]; melhor: Correlacao; nome: string }) {
  const [W, H, zero, escala] = [210, 112, 54, 90];
  const xBarra = (k: number) => 14 + k * 27;
  const alturaMelhor = Math.abs(melhor.spearman!) * escala;
  const rotulos: Rotulo[] = [
    ...linhas.map((c) => ({
      x: xBarra(c.defasagem_meses) + 9,
      y: 108,
      texto: String(c.defasagem_meses),
      cor: c === melhor ? "var(--ink)" : "var(--muted)",
      peso: c === melhor ? 600 : 400,
      tamanho: 10,
    })),
    {
      x: xBarra(melhor.defasagem_meses) + 9,
      y: melhor.spearman! >= 0 ? zero - alturaMelhor - 6 : zero + alturaMelhor + 13,
      texto: comSinal(melhor.spearman),
      cor: "var(--ink)",
      peso: 600,
    },
  ];
  return (
    <div className="grafico" style={{ marginTop: 6 }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%">
        <line x1={8} x2={202} y1={zero} y2={zero} stroke="var(--line2)" strokeWidth={1} />
        {linhas.map((c) => {
          const r = c.spearman!;
          const h = Math.max(1, Math.abs(r) * escala);
          const cor = r >= 0 ? "var(--pos)" : "var(--neg)";
          return (
            <rect
              key={c.defasagem_meses}
              x={xBarra(c.defasagem_meses)}
              y={r >= 0 ? zero - h : zero}
              width={18}
              height={h}
              rx={2}
              fill={c.significativo ? cor : "transparent"}
              stroke={cor}
              strokeWidth={1.25}
              data-tip={`${nome} · defasagem ${meses(c.defasagem_meses)} · Spearman ${comSinal(r, 3)} · ${
                c.significativo ? "significativo" : "não significativo"
              } · ${c.n_meses} meses`}
            />
          );
        })}
      </svg>
      <Rotulos itens={rotulos} largura={W} altura={H} />
    </div>
  );
}

// ---------------------------------------------------------------------
// d) Mapa de calor estado × modalidade
// ---------------------------------------------------------------------

function MapaDeCalor({ dados, abrirCombinacao }: { dados: DadosPainel; abrirCombinacao: Abrir }) {
  const caixa = useRef<HTMLDivElement>(null);
  const largura = useLargura(caixa);
  const [vista, setVista] = useState<"grade" | "mapa">("grade");
  const modalidades = modalidadesDoSite(dados);
  const [modMapa, setModMapa] = useState(dados.frase.associacao_mais_forte_sprint4.modalidade);

  const porChave = new Map(dados.correlacoesUf.map((c) => [chave(c.uf, c.modalidade), c]));
  const todas = dados.correlacoesUf;
  const calculadas = todas.filter((c) => !c.amostra_insuficiente && c.spearman !== null);
  const significativas = calculadas.filter((c) => c.significativo);
  const contadores = [
    { n: calculadas.length, rotulo: "combinações calculadas", cor: "var(--ink)" },
    { n: significativas.length, rotulo: "significativas", cor: "var(--ink)" },
    { n: significativas.filter((c) => c.spearman! > 0).length, rotulo: "positivas", cor: "var(--pos)" },
    { n: significativas.filter((c) => c.spearman! < 0).length, rotulo: "negativas", cor: "var(--neg)" },
    { n: todas.length - calculadas.length, rotulo: "sem amostra suficiente", cor: "var(--muted)" },
  ];
  // Defasagem usada em cada coluna: a mesma para toda a modalidade (a mais forte no nível Brasil).
  const defasagemDa = (m: string) => todas.find((c) => c.modalidade === m)?.defasagem_meses;
  const mostrarValores = largura >= 700;

  const celula = (uf: string, m: string) => {
    const c: CorrelacaoUf | undefined = porChave.get(chave(uf, m));
    const insuficiente = !c || c.amostra_insuficiente || c.spearman === null;
    const r = insuficiente ? null : c!.spearman;
    const intensidade = r === null ? 0 : Math.min(1, Math.abs(r) / 0.6);
    const nome = infoModalidade(m).nome;
    return {
      fundo: corDaCorrelacao(r),
      opacidade: insuficiente || c!.significativo ? 1 : 0.38,
      texto: !insuficiente && c!.significativo && intensidade > 0.5 ? "#fff" : "var(--ink)",
      valor: r === null ? "" : comSinal(r),
      dica:
        `${nomeUf(uf)} · ${nome} · ` +
        (insuficiente
          ? `amostra insuficiente (${c?.n_meses ?? 0} meses)`
          : `Spearman ${comSinal(r, 3)} · defasagem ${meses(c!.defasagem_meses)} · ${c!.significativo ? "significativo" : "não significativo"}`),
      aoClicar: () => abrirCombinacao(uf, m),
    };
  };

  return (
    <div className="bloco" ref={caixa}>
      <div className="bloco-cabecalho bloco-cabecalho-fim">
        <div>
          <h3>Estado × modalidade</h3>
          <p className="texto-apoio texto-menor">
            Correlação de Spearman entre a variação do saldo de cada combinação e a variação da Selic, na defasagem
            indicada sob cada coluna (a mais forte da modalidade no Brasil). Clique para ver a combinação em detalhe.
          </p>
        </div>
        <Alternador
          opcoes={[
            { id: "grade", rotulo: "Grade" },
            { id: "mapa", rotulo: "Mapa" },
          ]}
          atual={vista}
          aoEscolher={setVista}
        />
      </div>

      <div className="contadores">
        {contadores.map((k) => (
          <div key={k.rotulo}>
            <span className="contador-numero" style={{ color: k.cor }}>{k.n}</span>
            <span className="apagado pequeno-medio">{k.rotulo}</span>
          </div>
        ))}
      </div>

      {vista === "grade" ? (
        <div className="rolagem-horizontal">
          <div className="grade-calor">
            <span />
            {modalidades.map((m) => (
              <span key={m} className="grade-calor-cabeca" data-tip={infoModalidade(m).nome}>
                {infoModalidade(m).curto}
              </span>
            ))}
            {UFS.map((u) => (
              <GradeLinha key={u.sigla} sigla={u.sigla} modalidades={modalidades} celula={celula} mostrarValores={mostrarValores} />
            ))}
            <span className="grade-calor-pe">Defas.</span>
            {modalidades.map((m) => (
              <span key={m} className="grade-calor-pe centro">
                {defasagemDa(m) ?? "—"} m
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div className="grade-mapa-calor">
          <div className="filtros-pilula">
            {modalidades.map((m) => (
              <Pilula key={m} ativo={modMapa === m} onClick={() => setModMapa(m)}>
                {infoModalidade(m).nome}
              </Pilula>
            ))}
          </div>
          <MapaGrade
            larguraMaxima={380}
            quadrado={(sigla) => {
              const c = celula(sigla, modMapa);
              return { fundo: c.fundo, opacidade: c.opacidade, texto: c.texto, detalhe: c.valor, dica: c.dica, aoClicar: c.aoClicar };
            }}
          />
        </div>
      )}

      <div className="legenda legenda-calor">
        <span>
          −0,6<span className="escala-calor" />+0,6
        </span>
        <span><span className="amostra-cor" style={{ background: "var(--pos)", opacity: 0.38 }} />Não significativo (esmaecido)</span>
        <span>
          <span className="amostra-cor hachura" />
          <Termo id="amostra">Amostra insuficiente</Termo> (hachurado)
        </span>
      </div>
    </div>
  );
}

function GradeLinha({ sigla, modalidades, celula, mostrarValores }: {
  sigla: string;
  modalidades: string[];
  celula: (uf: string, m: string) => { fundo: string; opacidade: number; texto: string; valor: string; dica: string; aoClicar: () => void };
  mostrarValores: boolean;
}) {
  return (
    <>
      <span className="grade-calor-uf">{sigla}</span>
      {modalidades.map((m) => {
        const c = celula(sigla, m);
        return (
          <span
            key={m}
            className="grade-calor-celula"
            data-tip={c.dica}
            onClick={c.aoClicar}
            style={{ background: c.fundo, opacity: c.opacidade, color: c.texto }}
          >
            {mostrarValores ? c.valor : ""}
          </span>
        );
      })}
    </>
  );
}
