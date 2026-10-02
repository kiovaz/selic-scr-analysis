"use client";
/**
 * Atualização automática da página quando o pipeline publica dados novos.
 *
 * A cada 10 s o navegador pergunta à rota /api/publicacao a data da última
 * publicação. Se ela for diferente da data com que a página foi montada, pede
 * ao Next para recarregar os dados (router.refresh), sem recarregar a página
 * inteira nem perder a rolagem e os filtros.
 *
 * Proteções:
 * - Só consulta com a aba visível, e para depois de 30 min sem interação —
 *   uma aba esquecida aberta não mantém o banco (Neon) acordado à toa.
 * - Se a consulta falhar, nada muda na tela; tenta de novo na próxima vez.
 * - Se o recarregamento ainda trouxer a versão antiga (o cache do servidor
 *   dura até 10 s), as datas continuam diferentes e ele é pedido de novo.
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const INTERVALO_MS = 10_000;
const PARAR_APOS_MS = 30 * 60_000;

/** Devolve true por alguns segundos logo depois que a página recebeu dados novos. */
export function useAtualizacaoAutomatica(publicadoEm: string | null): boolean {
  const router = useRouter();
  const ultimaInteracao = useRef(Date.now());
  const dataAtual = useRef(publicadoEm);
  const [avisoVisivel, setAvisoVisivel] = useState(false);

  // Quando a página chega com uma data nova, mostra o aviso "dados atualizados".
  useEffect(() => {
    if (dataAtual.current === publicadoEm) return;
    dataAtual.current = publicadoEm;
    setAvisoVisivel(true);
    const t = setTimeout(() => setAvisoVisivel(false), 6000);
    return () => clearTimeout(t);
  }, [publicadoEm]);

  useEffect(() => {
    const marcarInteracao = () => {
      ultimaInteracao.current = Date.now();
    };
    const eventos = ["pointermove", "keydown", "scroll", "touchstart"] as const;
    eventos.forEach((e) => window.addEventListener(e, marcarInteracao, { passive: true }));

    let consultando = false;
    const verificar = async () => {
      if (consultando || document.visibilityState !== "visible") return;
      if (Date.now() - ultimaInteracao.current > PARAR_APOS_MS) return;
      consultando = true;
      try {
        const resposta = await fetch("/api/publicacao", { cache: "no-store" });
        if (!resposta.ok) return;
        const { publicadoEm: noBanco } = (await resposta.json()) as { publicadoEm: string | null };
        if (noBanco && noBanco !== dataAtual.current) router.refresh();
      } catch {
        // Sem rede ou banco fora do ar: mantém o que está na tela.
      } finally {
        consultando = false;
      }
    };

    const relogio = setInterval(verificar, INTERVALO_MS);
    // Ao voltar para a aba, confere na hora em vez de esperar o próximo ciclo.
    const aoMudarVisibilidade = () => {
      if (document.visibilityState === "visible") {
        marcarInteracao();
        verificar();
      }
    };
    document.addEventListener("visibilitychange", aoMudarVisibilidade);

    return () => {
      clearInterval(relogio);
      document.removeEventListener("visibilitychange", aoMudarVisibilidade);
      eventos.forEach((e) => window.removeEventListener(e, marcarInteracao));
    };
  }, [router]);

  return avisoVisivel;
}
