import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Selic e Crédito por Estado",
  description:
    "Saldo de financiamentos por estado e modalidade (SCR.data/BCB) cruzado com a Selic meta do Copom (Ipeadata), e a recomendação do trimestre.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="topo">
          <div className="topo-conteudo">
            <Link href="/" className="marca">
              Selic e Crédito por Estado
            </Link>
            <nav className="menu" aria-label="Páginas">
              <Link href="/">Recomendação</Link>
              <Link href="/selic-credito">Selic × crédito</Link>
              <Link href="/explorar">Explorar</Link>
            </nav>
          </div>
        </header>
        {children}
        <footer className="rodape">
          <div>
            Fontes: <a href="https://dadosabertos.bcb.gov.br/dataset/scr_data">SCR.data</a> (Banco Central do
            Brasil, licença ODbL) e Selic meta do Copom, série BM366_TJOVER366 (
            <a href="http://www.ipeadata.gov.br">Ipeadata</a>). Recorte: jul/2016 a jun/2026. Os valores são{" "}
            <strong>saldo de carteira</strong> no fim de cada mês, em reais nominais — não o volume de
            financiamentos novos.
          </div>
        </footer>
      </body>
    </html>
  );
}
