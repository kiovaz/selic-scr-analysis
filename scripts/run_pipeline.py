"""
Executa o pipeline inteiro, de ponta a ponta.

Cada sprint acrescenta uma etapa aqui. Hoje: prepara as pastas e faz a
ingestão Bronze do SCR e da Selic (Sprints 2 e 3) e constrói a Silver,
a Gold e a análise (Sprint 4), o modelo de ML (Sprint 5), a
recomendação de decisão (Sprint 6) e, se houver DATABASE_URL no .env,
publica as tabelas finais no Neon.

Como rodar (da raiz do projeto):
    python scripts/run_pipeline.py              # todos os anos (~2 GB de download)
    python scripts/run_pipeline.py --anos 2024  # só os anos escolhidos do SCR
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config  # noqa: E402
from src.ingestion.scr_file_loader import carregar_scr
from src.ingestion.selic_api_loader import carregar_selic
from src.transformation.silver_scr import construir_silver_scr
from src.transformation.silver_selic import construir_silver_selic
from src.transformation.gold_credito_selic import construir_gold
from src.analise.correlacao import executar_analise
from src.ml.treino import executar_ml
from src.ml.decisao import executar_decisao
from src.publicacao.neon import executar_publicacao


def main():
    parser = argparse.ArgumentParser(description="Pipeline Selic x SCR, ponta a ponta.")
    parser.add_argument(
        "--anos", type=int, nargs="*",
        help="Anos do SCR a processar (padrão: ANO_INICIO a ANO_FIM). "
             "Cada ano é um ZIP de ~170 MB.",
    )
    args = parser.parse_args()

    # Mostra no terminal o que os loaders registram (downloads, CSVs
    # rejeitados, linhas gravadas).
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    print("Preparando as pastas de dados...")
    config.criar_pastas()
    print(f"  Bronze : {config.DIR_BRONZE}")
    print(f"  Silver : {config.DIR_SILVER}")
    print(f"  Gold   : {config.DIR_GOLD}")

    print(f"\nRecorte do projeto: {config.MES_INICIO:02d}/{config.ANO_INICIO} "
          f"a {config.MES_FIM:02d}/{config.ANO_FIM}")
    print(f"Modalidades: as que começam com '{config.PREFIXO_MODALIDADE}'")

    # --- Sprint 2: Ingestão Bronze ---
    print("\n=== Sprint 2: Ingestão Bronze ===")

    print("\nIngerindo SCR.data...")
    load_id_scr = carregar_scr(anos=args.anos)
    print(f"  SCR concluído (load_id: {load_id_scr})")

    print("\nIngerindo Selic (Ipeadata)...")
    load_id_selic = carregar_selic()
    print(f"  Selic concluído (load_id: {load_id_selic})")

    # --- Sprint 4: Silver (reconstruída inteira a partir da Bronze) ---
    print("\n=== Sprint 4: Silver ===")
    silver_scr = construir_silver_scr()
    silver_selic = construir_silver_selic()
    if silver_scr is not None and silver_selic is not None:
        relatorio = json.loads(config.ARQUIVO_RELATORIO_SILVER.read_text(encoding="utf-8"))
        r_scr, r_selic = relatorio["silver_scr"], relatorio["silver_selic"]
        print(f"  silver_scr  : {r_scr['linhas_silver']:,} linhas, {r_scr['meses']} meses, "
              f"{len(r_scr['modalidades'])} modalidades")
        print(f"                quarentena: {r_scr['quarentena_por_motivo'] or 'vazia'}")
        print(f"                combinações UF × modalidade com meses faltando: "
              f"{len(r_scr['combinacoes_incompletas'])}")
        print(f"  silver_selic: {r_selic['linhas_silver']} meses, "
              f"quarentena: {r_selic['quarentena_por_motivo'] or 'vazia'}")
        print(f"  Relatório completo: {config.ARQUIVO_RELATORIO_SILVER}")

    # --- Sprint 4: Gold e análise ---
    print("\n=== Sprint 4: Gold ===")
    gold = construir_gold()
    if gold is not None:
        rel = json.loads(config.ARQUIVO_RELATORIO_GOLD.read_text(encoding="utf-8"))
        print(f"  gold_credito_selic: {rel['linhas_gold']:,} linhas, {rel['meses']} meses")
        print(f"  órfãos: SCR sem Selic {rel['orfaos_meses_scr_sem_selic'] or 'nenhum'} | "
              f"Selic sem SCR {rel['orfaos_meses_selic_sem_scr'] or 'nenhum'}")
        print(f"  linhas sem mês anterior (variação vazia): {rel['linhas_sem_mes_anterior']:,}")

        print("\n=== Sprint 4: Análise (associação, não causa) ===")
        brasil, uf_modalidade = executar_analise()
        fortes = brasil.dropna(subset=["spearman"]).assign(abs_rho=lambda d: d["spearman"].abs()) \
                       .sort_values("abs_rho", ascending=False).head(3)
        print("  Associações mais fortes no nível Brasil:")
        for _, r in fortes.iterrows():
            print(f"    {r['modalidade']}: k={r['defasagem_meses']}, Spearman {r['spearman']:+.2f}, "
                  f"p ajustado {r['p_ajustado']:.3f}{' (significativa)' if r['significativo'] else ''}")
        calculadas = (~uf_modalidade["amostra_insuficiente"]).sum()
        print(f"  UF × modalidade: {calculadas} combinações calculadas, "
              f"{uf_modalidade['amostra_insuficiente'].sum()} com amostra insuficiente, "
              f"{int(uf_modalidade['significativo'].sum())} significativas")
        print(f"  Figuras em {config.DIR_FIGURAS}")

    # --- Sprint 5: ML — o crédito vai ganhar força no trimestre t+2 a t+5? ---
    print("\n=== Sprint 5: ML ===")
    resultados = executar_ml()
    if resultados is not None:
        r = resultados["resumo"]
        print(f"  linhas por conjunto: {resultados['linhas_por_conjunto']}")
        print(f"  modelo escolhido (janela móvel 2020–2023): {resultados['modelo_escolhido']} "
              f"{ {k: round(v, 3) for k, v in resultados['auc_media_janela_movel'].items()} }")
        print(f"  teste final — AUC modelo {r['auc_modelo']:.3f} | sem Selic {r['auc_sem_selic']:.3f} | "
              f"volta ao normal {r['auc_volta_ao_normal']:.3f} | supera a volta ao normal: "
              f"{'sim' if r['supera_volta_ao_normal'] else 'NÃO'}")
        print(f"  melhores apostas (20/mês): modelo {r['melhores_apostas_modelo']:.1%} | "
              f"volta ao normal {r['melhores_apostas_volta_ao_normal']:.1%}")
        for alerta in resultados["alertas"]:
            print(f"  ⚠ {alerta}")
        print(f"  previsão set–nov/2026: {config.ARQUIVO_ML_PREVISAO_PRODUCAO}")

        # --- Sprint 6: decisão — frase de fechamento com os números do pipeline ---
        print("\n=== Sprint 6: Decisão ===")
        n = executar_decisao()
        if n is not None:
            assoc = n["associacao_mais_forte_sprint4"]
            print(f"  Regra: expandir nas {n['tamanho_lista']} combinações com maior probabilidade de ganhar força.")
            print(f"  Frase de fechamento (números deste pipeline):")
            print(f"    Cruzando o SCR.data (BCB) e a Selic meta do Copom (Ipeadata), identificamos que o crédito "
                  f"da modalidade \"{assoc['modalidade']}\" anda junto com a Selic de {assoc['defasagem_meses']} meses antes "
                  f"(Spearman {assoc['spearman']:+.2f}), mas a Selic não antecipa o trimestre seguinte "
                  f"(AUC com Selic {n['auc_modelo']:.3f} × sem Selic {n['auc_sem_selic']:.3f}); o que antecipa é "
                  f"o ritmo recente do próprio crédito.")
            print(f"    Recomendamos que a diretoria de crédito de uma instituição financeira de atuação nacional "
                  f"expanda a oferta de financiamento nas {n['tamanho_lista']} combinações estado × modalidade com "
                  f"maior probabilidade de ganhar força nos próximos 3 meses ({n['trimestre_recomendado']}), "
                  f"priorizando as de maior saldo dentro da lista.")
            print(f"    Se agir, o ganho esperado é acertar ~{n['acertos_esperados_modelo']:.1f} de "
                  f"{n['tamanho_lista']} expansões por trimestre ({n['precisao_lista_modelo']:.1%}), contra "
                  f"~{n['acertos_esperados_regra_simples']:.1f} da regra simples e ~{n['acertos_esperados_acaso']:.1f} "
                  f"ao acaso; se errarmos, o custo é ~{n['erros_esperados_modelo']:.1f} expansões por trimestre em "
                  f"mercados que estão perdendo força.")
            print(f"  Lista: {config.ARQUIVO_RECOMENDACAO}")
    else:
        print("  ML e decisão pulados: dados insuficientes (a coorte exige os 120 meses do recorte).")
        print("  Rode o pipeline completo, sem --anos, para treinar o modelo e gerar a recomendação.")

    # --- Publicação no Neon (opcional: só com DATABASE_URL no .env) ---
    print("\n=== Publicação no Neon ===")
    linhas = executar_publicacao()
    if linhas is None:
        print(f"  Pulada: sem {config.VARIAVEL_CONEXAO} no .env ou com saídas faltando (ver o aviso acima).")
    else:
        for tabela, n in linhas.items():
            print(f"  {tabela}: {n} linhas")


if __name__ == "__main__":
    main()
