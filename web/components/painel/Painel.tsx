"use client";
/**
 * Página única do site, no navegador: cabeçalho, as seis seções, o tooltip
 * compartilhado e o tema claro/escuro.
 *
 * O tooltip é um só para a página inteira: qualquer elemento com `data-tip`
 * (valor de um gráfico) ou `data-termo` (palavra do glossário) mostra a caixa
 * ao passar o mouse ou receber foco do teclado.
 */
import { useCallback, useEffect, useRef, useState, type FocusEvent, type MouseEvent } from "react";
import type { DadosPainel } from "@/lib/tipos";
import { GLOSSARIO, type IdTermo } from "./glossario";
import SecaoDecisao from "./SecaoDecisao";
import SecaoRecomendacao from "./SecaoRecomendacao";
import SecaoSelic from "./SecaoSelic";
import SecaoModelo from "./SecaoModelo";
import SecaoExplorar from "./SecaoExplorar";
import SecaoDados from "./SecaoDados";

type Dica = { titulo: string; texto: string; x: number; y: number; acima: boolean };

const SECOES = [
  ["decisao", "Decisão"],
  ["recomendacao", "Recomendação"],
  ["selic", "Selic e crédito"],
  ["modelo", "Modelo"],
  ["explorar", "Explorar"],
  ["dados", "Dados"],
];

export default function Painel({ dados }: { dados: DadosPainel }) {
  // ---------- Tema ----------
  const [escuro, setEscuro] = useState(false);
  useEffect(() => {
    // O script do layout já aplicou a escolha salva; aqui só lemos o tema em uso.
    const definido = document.documentElement.getAttribute("data-theme");
    setEscuro(definido ? definido === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);
  const alternarTema = () => {
    const novo = escuro ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", novo);
    try {
      localStorage.setItem("tema", novo);
    } catch {
      // Sem acesso ao armazenamento (janela privada): o tema vale só nesta visita.
    }
    setEscuro(!escuro);
  };

  // ---------- Combinação aberta na seção Explorar ----------
  const [combinacao, setCombinacao] = useState({
    uf: dados.combinacaoInicial.uf,
    modalidade: dados.combinacaoInicial.modalidade,
  });
  // Clicar numa linha da recomendação ou numa célula do mapa abre a combinação e rola até ela.
  const abrirCombinacao = useCallback((uf: string, modalidade: string) => {
    setCombinacao({ uf, modalidade });
    const el = document.getElementById("explorar");
    if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 64, behavior: "smooth" });
  }, []);

  // ---------- Tooltip ----------
  const [dica, setDica] = useState<Dica | null>(null);
  const alvoAtual = useRef<Element | null>(null);

  const mostrarDica = (e: MouseEvent | FocusEvent) => {
    const alvo = (e.target as Element).closest?.("[data-tip],[data-termo]") ?? null;
    if (!alvo) {
      alvoAtual.current = null;
      setDica(null);
      return;
    }
    if (alvo === alvoAtual.current) return;
    alvoAtual.current = alvo;
    let titulo = "";
    let texto = alvo.getAttribute("data-tip") ?? "";
    const termo = alvo.getAttribute("data-termo") as IdTermo | null;
    if (termo && GLOSSARIO[termo]) [titulo, texto] = GLOSSARIO[termo];
    if (!texto) return;
    const r = alvo.getBoundingClientRect();
    const x = Math.max(150, Math.min(window.innerWidth - 150, r.left + r.width / 2));
    const acima = r.top > 130;
    setDica({ titulo, texto, x, y: acima ? r.top - 8 : r.bottom + 8, acima });
  };
  const esconderDica = () => {
    alvoAtual.current = null;
    setDica(null);
  };
  // Ao rolar, a posição da caixa deixaria de bater com o elemento: esconde.
  useEffect(() => {
    const aoRolar = () => esconderDica();
    window.addEventListener("scroll", aoRolar, { passive: true });
    return () => window.removeEventListener("scroll", aoRolar);
  }, []);

  return (
    <div className="pagina" onMouseOver={mostrarDica} onFocus={mostrarDica} onMouseLeave={esconderDica} onBlur={esconderDica}>
      <header className="topo">
        <div className="container topo-conteudo">
          <a href="#decisao" className="marca">
            <span className="marca-ponto" />
            Selic × Crédito
          </a>
          <nav className="menu" aria-label="Seções">
            {SECOES.map(([id, nome]) => (
              <a key={id} href={`#${id}`}>
                {nome}
              </a>
            ))}
          </nav>
          <button className="botao-tema" onClick={alternarTema} aria-label="Alternar tema">
            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
              <path d="M7 1.5 A5.5 5.5 0 0 1 7 12.5 Z" fill="currentColor" />
            </svg>
            {escuro ? "Modo claro" : "Modo escuro"}
          </button>
        </div>
      </header>

      <main>
        <SecaoDecisao dados={dados} />
        <SecaoRecomendacao dados={dados} abrirCombinacao={abrirCombinacao} />
        <SecaoSelic dados={dados} abrirCombinacao={abrirCombinacao} />
        <SecaoModelo dados={dados} />
        <SecaoExplorar dados={dados} combinacao={combinacao} setCombinacao={setCombinacao} />
        <SecaoDados publicadoEm={dados.publicadoEm} />
      </main>

      {dica && (
        <div
          role="tooltip"
          className="dica"
          style={{ left: dica.x, top: dica.y, transform: dica.acima ? "translate(-50%,-100%)" : "translate(-50%,0)" }}
        >
          {dica.titulo && <div className="dica-titulo">{dica.titulo}</div>}
          <div>{dica.texto}</div>
        </div>
      )}
    </div>
  );
}
