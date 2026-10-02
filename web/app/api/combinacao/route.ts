/**
 * Série mensal de uma combinação estado × modalidade, em JSON.
 * Usada pela seção "Explorar" quando o visitante troca o estado ou a modalidade.
 *
 * GET /api/combinacao?uf=SP&modalidade=Financiamentos%20imobili%C3%A1rios
 *
 * Só leitura: a consulta é parametrizada (sem montar SQL com texto do usuário).
 */
import { lerCombinacao } from "@/lib/consultas";
import { UFS } from "@/lib/ufs";

export async function GET(requisicao: Request) {
  const parametros = new URL(requisicao.url).searchParams;
  const uf = parametros.get("uf") ?? "";
  const modalidade = parametros.get("modalidade") ?? "";

  if (!UFS.some((u) => u.sigla === uf) || !modalidade.startsWith("Financiamentos")) {
    return Response.json({ erro: "Informe uf (sigla de um dos 27 estados) e modalidade." }, { status: 400 });
  }

  const serie = await lerCombinacao(uf, modalidade);
  // O dado só muda quando o pipeline publica de novo: a CDN pode guardar a resposta por uma hora.
  return Response.json(serie, { headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400" } });
}
