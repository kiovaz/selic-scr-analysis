/**
 * Conexão com o banco Neon (Postgres), onde o pipeline publica as tabelas
 * finais (src/publicacao/neon.py).
 *
 * Este arquivo só roda no SERVIDOR: a string de conexão (DATABASE_URL) vem
 * das variáveis de ambiente da Vercel ou do web/.env.local e nunca é enviada
 * ao navegador. O site só LÊ o banco — nada aqui grava.
 */
import "server-only";
import { neon } from "@neondatabase/serverless";

export function banco() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error(
      "DATABASE_URL não configurada: crie web/.env.local (veja web/.env.exemplo) " +
        "ou defina a variável no painel da Vercel.",
    );
  }
  return neon(url);
}
