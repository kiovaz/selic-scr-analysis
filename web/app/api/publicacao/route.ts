/**
 * Data e hora da última publicação do pipeline no banco, em JSON.
 * O navegador consulta esta rota a cada 10 s para saber se há dados novos
 * (atualização automática da página). Só leitura; não devolve nenhum dado do projeto.
 *
 * GET /api/publicacao -> { "publicadoEm": "27/09/2026 18:39" }
 */
import { lerUltimaPublicacao, repetirSeFalhar } from "@/lib/consultas";

// Sempre consulta o banco: a resposta não pode ficar guardada em cache.
export const dynamic = "force-dynamic";

export async function GET() {
  const publicadoEm = await repetirSeFalhar(lerUltimaPublicacao);
  return Response.json({ publicadoEm }, { headers: { "Cache-Control": "no-store" } });
}
