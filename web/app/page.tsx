/**
 * Página única do site. Aqui (no servidor) leem-se as tabelas publicadas pelo
 * pipeline; o componente Painel monta as seções no navegador, com os filtros,
 * gráficos e tooltips. A série de cada combinação estado × modalidade vem sob
 * demanda pela rota /api/combinacao, para não enviar a Gold inteira de uma vez.
 */
import Painel from "@/components/painel/Painel";
import {
  lerCombinacao,
  lerCorrelacoesBrasil,
  lerCorrelacoesUf,
  lerFrase,
  lerPrevisoes,
  lerRecomendacao,
  lerSaldoBrasil,
  lerSelic,
  lerSensibilidade,
  lerUltimaPublicacao,
  repetirSeFalhar,
} from "@/lib/consultas";
import { infoModalidade } from "@/lib/modalidades";
import type { DadosPainel } from "@/lib/tipos";

// Cache curto: a página é regerada no máximo a cada 10 s, então uma nova
// publicação aparece quase na hora. Se o banco falhar na regeração, o Next
// continua servindo a última versão boa (por isso não tiramos o cache de vez).
export const revalidate = 10;

// Combinação mostrada na seção "Explorar" ao abrir o site.
const UF_INICIAL = "SP";
const MODALIDADE_INICIAL = "imobiliario";

async function carregarDados(): Promise<DadosPainel> {
  // A data da publicação é lida ANTES das tabelas. Se uma publicação terminar
  // no meio das leituras, a página fica com a data antiga e a atualização
  // automática (no navegador) percebe a diferença e recarrega tudo de novo.
  const publicadoEm = await lerUltimaPublicacao();
  const [frase, recomendacao, selic, saldoBrasil, correlacoesBrasil, correlacoesUf, previsoes, sensibilidade] =
    await Promise.all([
      lerFrase(),
      lerRecomendacao(),
      lerSelic(),
      lerSaldoBrasil(),
      lerCorrelacoesBrasil(),
      lerCorrelacoesUf(),
      lerPrevisoes(),
      lerSensibilidade(),
    ]);

  // O nome da modalidade no banco é o do SCR.data; procura o do imobiliário pela chave.
  const modalidadeInicial =
    correlacoesBrasil.map((c) => c.modalidade).find((m) => infoModalidade(m).chave === MODALIDADE_INICIAL) ??
    correlacoesBrasil[0].modalidade;
  const serie = await lerCombinacao(UF_INICIAL, modalidadeInicial);

  return {
    frase,
    recomendacao,
    selic,
    saldoBrasil,
    correlacoesBrasil,
    correlacoesUf,
    previsoes,
    sensibilidade,
    publicadoEm,
    combinacaoInicial: { uf: UF_INICIAL, modalidade: modalidadeInicial, serie },
  };
}

export default async function Pagina() {
  return <Painel dados={await repetirSeFalhar(carregarDados)} />;
}
