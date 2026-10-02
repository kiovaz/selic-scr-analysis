"use client";
/**
 * Mapa do Brasil "em grade": cada estado é um quadrado numa posição
 * aproximada da geografia. Quem usa decide a cor, o texto e o tooltip de cada estado.
 */
import { UFS } from "@/lib/ufs";

export type QuadradoUf = {
  fundo: string;
  texto: string;
  opacidade?: number;
  detalhe?: string; // segunda linha, menor (ex.: o valor da correlação)
  dica: string;
  aoClicar?: () => void;
};

export default function MapaGrade({ quadrado, larguraMaxima }: {
  quadrado: (sigla: string, nome: string) => QuadradoUf;
  larguraMaxima: number;
}) {
  return (
    <div className="mapa-grade" style={{ maxWidth: larguraMaxima }}>
      {UFS.map((u) => {
        const q = quadrado(u.sigla, u.nome);
        return (
          <div
            key={u.sigla}
            data-tip={q.dica}
            onClick={q.aoClicar}
            className={q.aoClicar ? "mapa-uf clicavel" : "mapa-uf"}
            style={{ gridColumn: u.coluna, gridRow: u.linha, background: q.fundo, color: q.texto, opacity: q.opacidade ?? 1 }}
          >
            <span className="mapa-uf-sigla">{u.sigla}</span>
            {q.detalhe && <span className="mapa-uf-detalhe">{q.detalhe}</span>}
          </div>
        );
      })}
    </div>
  );
}
