"use client";
/**
 * 04 · O modelo — dá para prever?
 * Comparação com as réguas e o efeito da Selic vêm de frase_fechamento;
 * as regras de decisão testadas vêm de sensibilidade_limiar.
 */
import { useState } from "react";
import type { DadosPainel, Sensibilidade } from "@/lib/tipos";
import { comSinal, numero, porcentagem } from "@/lib/formato";
import { BarraValor, Termo, useSecao } from "./apoio";

/** Rótulo de uma regra da tabela de sensibilidade: "Nota mínima 0,5" ou "Maiores notas: 20". */
function nomeDaRegra(r: Sensibilidade): string {
  return r.regra === "nota mínima" ? `Nota mínima ${numero(r.parametro, 1)}` : `Maiores notas: ${numero(r.parametro, 0)}`;
}

export default function SecaoModelo({ dados }: { dados: DadosPainel }) {
  const { ref, visivel } = useSecao();
  const v = visivel ? 1 : 0; // as barras crescem quando a seção aparece
  const f = dados.frase;

  // Regras com nota mínima primeiro, depois as listas de tamanho fixo, cada grupo em ordem crescente.
  const regras = [...dados.sensibilidade].sort(
    (a, b) => Number(a.regra !== "nota mínima") - Number(b.regra !== "nota mínima") || a.parametro - b.parametro,
  );
  const adotada = Math.max(0, regras.findIndex((r) => r.regra !== "nota mínima" && r.parametro === f.tamanho_lista));
  const [escolhida, setEscolhida] = useState(adotada);
  const sel = regras[escolhida];
  const ehNota = (r?: Sensibilidade) => r?.regra === "nota mínima";
  // Com nota mínima o tamanho da lista muda a cada mês: o número é uma média ("cerca de").
  const porMes = (r: Sensibilidade) => (ehNota(r) ? `cerca de ${numero(r.recomendadas_por_mes, 0)}` : numero(r.recomendadas_por_mes, 0));

  return (
    <section id="modelo" ref={ref} className="secao secao-clara">
      <div className="container">
        <div className="rotulo-secao">04 · O modelo</div>
        <h2 className="titulo-secao">Dá para prever?</h2>
        <p className="texto-apoio">
          Para cada combinação de estado e modalidade, o modelo estima a probabilidade de o crédito{" "}
          <Termo id="forca">ganhar força</Termo>, isto é, de o saldo crescer mais nos próximos 3 meses do que cresceu nos
          últimos 3. O teste cobre fev/2025 a jan/2026, um período que o modelo não usou para aprender.
        </p>

        <div className="duas-colunas">
          <div>
            <h3 className="titulo-menor">
              <Termo id="auc">AUC</Termo> no teste
            </h3>
            <div className="apagado pequeno-medio">0,5 é chute; 1 é perfeito</div>
            <div className="pilha-barras">
              <BarraValor nome="Modelo" valor={numero(f.auc_modelo, 3)} fracao={f.auc_modelo * v} cor="var(--primary)" marcaMeio />
              <BarraValor nome="Regra simples" valor={numero(f.auc_regra_simples, 3)} fracao={f.auc_regra_simples * v} cor="var(--muted)" marcaMeio />
              <BarraValor nome="Chute" valor={numero(0.5, 3)} fracao={0.5 * v} cor="var(--line2)" marcaMeio />
            </div>
          </div>
          <div>
            <h3 className="titulo-menor">
              <Termo id="acerto20">Acerto nas {f.tamanho_lista} melhores apostas</Termo>
            </h3>
            <div className="apagado pequeno-medio">Quantas de fato ganharam força, por mês</div>
            <div className="pilha-barras">
              <BarraValor nome="Modelo" valor={porcentagem(f.precisao_lista_modelo)} fracao={f.precisao_lista_modelo * v} cor="var(--primary)" />
              <BarraValor nome="Regra simples" valor={porcentagem(f.precisao_lista_regra_simples)} fracao={f.precisao_lista_regra_simples * v} cor="var(--muted)" />
              <BarraValor nome="Acaso" valor={porcentagem(f.precisao_acaso)} fracao={f.precisao_acaso * v} cor="var(--line2)" />
            </div>
          </div>
        </div>

        <div className="duas-colunas separado">
          <div>
            <h3>A Selic ajuda a prever?</h3>
            <p className="paragrafo">
              O mesmo modelo, treinado sem as variáveis da Selic, teve desempenho equivalente, e até um pouco melhor no
              teste. A Selic está associada ao crédito, mas não avisa com antecedência qual combinação vai ganhar força no
              trimestre seguinte. O que prevê é o comportamento recente do próprio crédito.
            </p>
          </div>
          <div>
            <div className="pilha-barras" style={{ marginTop: 0 }}>
              <BarraValor nome="Modelo com a Selic" valor={`AUC ${numero(f.auc_modelo, 3)}`} fracao={f.auc_modelo * v} cor="var(--primary)" />
              <BarraValor nome="Modelo sem a Selic" valor={`AUC ${numero(f.auc_sem_selic, 3)}`} fracao={f.auc_sem_selic * v} cor="var(--muted)" />
            </div>
            <div className="diferenca">
              <span className="diferenca-valor">{comSinal(f.efeito_selic_auc_teste, 3)}</span>
              <span className="apagado pequeno-medio">de AUC no teste ao incluir a Selic</span>
            </div>
          </div>
        </div>

        <div className="separado">
          <h3>Por que {f.tamanho_lista} combinações?</h3>
          <p className="texto-apoio texto-menor">
            Regras de decisão testadas no período de teste. Selecione uma para ver quantas combinações ela recomenda por mês
            e quanto acerta.
          </p>
          <div className="duas-colunas" style={{ marginTop: 24 }}>
            <div role="radiogroup" className="lista-regras">
              {regras.map((r, i) => (
                <button
                  key={`${r.regra}-${r.parametro}`}
                  role="radio"
                  aria-checked={i === escolhida}
                  className={i === escolhida ? "regra ativa" : "regra"}
                  onClick={() => setEscolhida(i)}
                >
                  <span className="regra-nome">
                    <span>{nomeDaRegra(r)}</span>
                    <span className="apagado pequeno">{porMes(r)} por mês</span>
                  </span>
                  <span className="barra-trilho">
                    <span
                      className="barra-preenchida"
                      style={{ width: `${(r.precisao_modelo ?? 0) * 100 * v}%`, background: i === escolhida ? "var(--primary)" : "var(--line2)" }}
                    />
                  </span>
                  <strong>{porcentagem(r.precisao_modelo)}</strong>
                </button>
              ))}
            </div>
            {sel && (
              <div>
                <div className="numeros-regra">
                  <div>
                    <div className="apagado pequeno-medio">Combinações por mês</div>
                    <div className="numero-medio">{(ehNota(sel) ? "≈ " : "") + numero(sel.recomendadas_por_mes, 0)}</div>
                  </div>
                  <div>
                    <div className="apagado pequeno-medio">Acerto do modelo</div>
                    <div className="numero-medio">{porcentagem(sel.precisao_modelo)}</div>
                  </div>
                  {sel.precisao_regra_simples !== null && (
                    <div>
                      <div className="apagado pequeno-medio">Acerto da regra simples</div>
                      <div className="numero-medio apagado">{porcentagem(sel.precisao_regra_simples)}</div>
                    </div>
                  )}
                </div>
                <div className="apagado pequeno-medio" style={{ marginTop: 16 }}>
                  {escolhida === adotada
                    ? "Regra adotada na recomendação."
                    : ehNota(sel)
                      ? "Com nota mínima, o tamanho da lista varia a cada mês."
                      : "Lista fixa por mês."}
                </div>
                <p className="paragrafo separado-leve">
                  Expandir onde o crédito vai perder força tem custo imediato: capital, captação e equipe comercial alocados
                  sem retorno no trimestre. Deixar de expandir é custo de oportunidade, diluído no tempo. Por isso a regra
                  privilegia acertar onde se expande. Uma lista fixa de {f.tamanho_lista} equilibra acerto e alcance,
                  combina com a capacidade de execução da diretoria e não depende de as notas estarem calibradas.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
