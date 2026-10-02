"use client";
/**
 * Peças pequenas usadas por todas as seções: ganchos (largura, visibilidade,
 * animação de entrada), o termo com explicação, os rótulos sobre os gráficos
 * e os botões de alternância.
 */
import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { GLOSSARIO, type IdTermo } from "./glossario";

/** Largura atual de um elemento, atualizada quando a janela muda de tamanho. */
export function useLargura(ref: RefObject<HTMLElement | null>, inicial = 1000): number {
  const [largura, setLargura] = useState(inicial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observador = new ResizeObserver((entradas) => {
      const w = Math.round(entradas[0].contentRect.width);
      if (w) setLargura((atual) => (Math.abs(w - atual) > 2 ? w : atual));
    });
    observador.observe(el);
    return () => observador.disconnect();
  }, [ref]);
  return largura;
}

/** Vira true quando o elemento aparece na tela pela primeira vez (dispara as barras animadas). */
export function useVisivel(ref: RefObject<HTMLElement | null>): boolean {
  const [visivel, setVisivel] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || visivel) return;
    const observador = new IntersectionObserver(
      (entradas) => {
        if (entradas.some((e) => e.isIntersecting)) setVisivel(true);
      },
      { threshold: 0.08 },
    );
    observador.observe(el);
    return () => observador.disconnect();
  }, [ref, visivel]);
  return visivel;
}

/** Vai de 0 a 1 em `duracao` ms, desacelerando no fim (contagem dos números da abertura). */
export function useProgresso(duracao = 1400): number {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setT(1);
      return;
    }
    const inicio = performance.now();
    let quadro = 0;
    const passo = (agora: number) => {
      const p = Math.min(1, (agora - inicio) / duracao);
      setT(1 - Math.pow(1 - p, 3));
      if (p < 1) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [duracao]);
  return t;
}

/** Atalho para a seção de largura medida + visibilidade. */
export function useSecao() {
  const ref = useRef<HTMLElement>(null);
  const visivel = useVisivel(ref);
  return { ref, visivel };
}

/** Termo técnico sublinhado; ao passar o mouse ou focar, o Painel mostra a explicação do glossário. */
export function Termo({ id, children }: { id: IdTermo; children?: ReactNode }) {
  return (
    <span className="termo" data-termo={id} tabIndex={0}>
      {children ?? GLOSSARIO[id][0]}
    </span>
  );
}

/** Texto posicionado sobre um gráfico SVG, em coordenadas do próprio gráfico. */
export type Rotulo = {
  x: number;
  y: number;
  texto: string;
  ancora?: "inicio" | "meio" | "fim";
  cor?: string;
  peso?: number;
  tamanho?: number;
};

/**
 * Os rótulos ficam em HTML por cima do SVG (e não dentro dele) para o texto não
 * esticar quando o gráfico muda de largura. A posição é em % do tamanho do gráfico.
 */
export function Rotulos({ itens, largura, altura }: { itens: Rotulo[]; largura: number; altura: number }) {
  const deslocamento = { inicio: "translate(0,-85%)", meio: "translate(-50%,-85%)", fim: "translate(-100%,-85%)" };
  return (
    <>
      {itens.map((r, i) => (
        <span
          key={i}
          className="rotulo-grafico"
          style={{
            left: `${(r.x / largura) * 100}%`,
            top: `${(r.y / altura) * 100}%`,
            transform: deslocamento[r.ancora ?? "meio"],
            color: r.cor ?? "var(--muted)",
            fontWeight: r.peso ?? 400,
            fontSize: r.tamanho ?? 11,
          }}
        >
          {r.texto}
        </span>
      ))}
    </>
  );
}

/** Grupo de botões em que só um fica ativo (abas, ordenação, grade/mapa). */
export function Alternador<T extends string>({
  opcoes,
  atual,
  aoEscolher,
  grande = false,
}: {
  opcoes: { id: T; rotulo: string; ponto?: string }[];
  atual: T;
  aoEscolher: (id: T) => void;
  grande?: boolean;
}) {
  return (
    <div className={grande ? "alternador alternador-grande" : "alternador"} role="tablist">
      {opcoes.map((o) => (
        <button
          key={o.id}
          role="tab"
          aria-selected={o.id === atual}
          className={o.id === atual ? "ativo" : ""}
          onClick={() => aoEscolher(o.id)}
        >
          {o.ponto && <span className="ponto" style={{ background: o.ponto }} />}
          {o.rotulo}
        </button>
      ))}
    </div>
  );
}

/** Botão em formato de pílula para filtros (modalidade no gráfico da Selic e no mapa). */
export function Pilula({ ativo, onClick, children }: { ativo: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button className={ativo ? "pilula ativo" : "pilula"} onClick={onClick} aria-pressed={ativo}>
      {children}
    </button>
  );
}

/** Barra horizontal com rótulo e valor (comparações do modelo e da abertura). */
export function BarraValor({ nome, valor, fracao, cor, marcaMeio = false }: {
  nome: string;
  valor: string;
  fracao: number;
  cor: string;
  marcaMeio?: boolean;
}) {
  return (
    <div>
      <div className="barra-cabecalho">
        <span>{nome}</span>
        <strong>{valor}</strong>
      </div>
      <div className="barra-trilho barra-grossa">
        <div className="barra-preenchida barra-lenta" style={{ width: `${fracao * 100}%`, background: cor }} />
        {marcaMeio && <div className="barra-marca-meio" />}
      </div>
    </div>
  );
}
