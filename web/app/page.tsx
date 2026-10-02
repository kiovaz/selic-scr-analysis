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
} from "@/lib/consultas";
import { infoModalidade } from "@/lib/modalidades";

// Página regerada no máximo a cada hora: uma nova publicação aparece sem novo deploy.
export const revalidate = 3600;

// Combinação mostrada na seção "Explorar" ao abrir o site.
const UF_INICIAL = "SP";
const MODALIDADE_INICIAL = "imobiliario";

export default async function Pagina() {
  const [frase, recomendacao, selic, saldoBrasil, correlacoesBrasil, correlacoesUf, previsoes, sensibilidade, publicadoEm] =
    await Promise.all([
      lerFrase(),
      lerRecomendacao(),
      lerSelic(),
      lerSaldoBrasil(),
      lerCorrelacoesBrasil(),
      lerCorrelacoesUf(),
      lerPrevisoes(),
      lerSensibilidade(),
      lerUltimaPublicacao(),
    ]);

  // O nome da modalidade no banco é o do SCR.data; procura o do imobiliário pela chave.
  const modalidadeInicial =
    correlacoesBrasil.map((c) => c.modalidade).find((m) => infoModalidade(m).chave === MODALIDADE_INICIAL) ??
    correlacoesBrasil[0].modalidade;
  const serie = await lerCombinacao(UF_INICIAL, modalidadeInicial);

  return (
    <Painel
      dados={{
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
      }}
    />
  );
}
