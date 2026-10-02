import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Não gerar AGENTS.md/CLAUDE.md em web/ a cada `next dev`: as regras do projeto ficam no CLAUDE.md da raiz.
  agentRules: false,
  // As antigas páginas separadas viraram seções da página única.
  async redirects() {
    return [
      { source: "/selic-credito", destination: "/#selic", permanent: true },
      { source: "/explorar", destination: "/#explorar", permanent: true },
    ];
  },
};

export default nextConfig;
