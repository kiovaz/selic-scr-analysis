"use client";

/**
 * Caixas de seleção que mudam o endereço da página (?uf=...&modalidade=...).
 * A página lê o endereço no servidor e consulta o banco com a escolha — assim
 * o link da tela pode ser copiado e compartilhado.
 */
import { usePathname, useRouter, useSearchParams } from "next/navigation";

type Filtro = { nome: string; rotulo: string; opcoes: string[]; valor: string };

export default function Filtros({ filtros }: { filtros: Filtro[] }) {
  const router = useRouter();
  const caminho = usePathname();
  const parametros = useSearchParams();

  function mudar(nome: string, valor: string) {
    const novos = new URLSearchParams(parametros.toString());
    novos.set(nome, valor);
    router.push(`${caminho}?${novos.toString()}`, { scroll: false });
  }

  return (
    <div className="filtros">
      {filtros.map((f) => (
        <label key={f.nome}>
          {f.rotulo}
          <select value={f.valor} onChange={(e) => mudar(f.nome, e.target.value)}>
            {f.opcoes.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}
