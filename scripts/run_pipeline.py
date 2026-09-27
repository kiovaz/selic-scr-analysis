"""
Executa o pipeline inteiro, de ponta a ponta.

Cada sprint acrescenta uma etapa aqui. Hoje: prepara as pastas e faz a
ingestão Bronze do SCR e da Selic (Sprints 2 e 3) e constrói a Silver
(Sprint 4).

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

    print("\n--- Etapas ainda não implementadas ---")
    print("  [ ] Sprint 4: Gold e análise")
    print("  [ ] Sprint 5: base de ML")


if __name__ == "__main__":
    main()
