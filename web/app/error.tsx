"use client";
/**
 * Página de erro amigável. Aparece só se o banco não responder nem na
 * segunda tentativa e não houver uma versão anterior da página em cache
 * (por exemplo, logo depois de um deploy com o Neon fora do ar).
 */
import { useEffect } from "react";

export default function Erro({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="container erro-pagina">
      <div className="rotulo-secao">Selic × Crédito</div>
      <h1 className="titulo-secao">Não foi possível carregar os dados agora</h1>
      <p className="texto-apoio">
        O banco pode estar recebendo uma nova publicação ou iniciando depois de um tempo parado. Isso costuma levar
        poucos segundos.
      </p>
      <button onClick={() => retry()}>Tentar de novo</button>
    </main>
  );
}
