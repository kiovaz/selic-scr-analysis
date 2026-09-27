"""
Executa o pipeline inteiro, de ponta a ponta.

Cada sprint acrescenta uma etapa aqui. Hoje: prepara as pastas e faz a
ingestão Bronze do SCR e da Selic (Sprints 2 e 3) e constrói a Silver,
a Gold e a análise (Sprint 4).

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

    print("\n--- Etapas ainda não implementadas ---")
    print("  [ ] Sprint 5: base de ML")


if __name__ == "__main__":
    main()
