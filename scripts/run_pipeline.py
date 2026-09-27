"""
Executa o pipeline inteiro, de ponta a ponta.

Cada sprint acrescenta uma etapa aqui. Hoje: prepara as pastas e faz a
ingestão Bronze do SCR e da Selic (Sprint 2).

Como rodar (da raiz do projeto):
    python scripts/run_pipeline.py              # todos os anos (~2 GB de download)
    python scripts/run_pipeline.py --anos 2024  # só os anos escolhidos do SCR
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config  # noqa: E402
from src.ingestion.scr_file_loader import carregar_scr
from src.ingestion.selic_api_loader import carregar_selic


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
          f"a 12/{config.ANO_FIM}")
    print(f"Modalidades: as que começam com '{config.PREFIXO_MODALIDADE}'")

    # --- Sprint 2: Ingestão Bronze ---
    print("\n=== Sprint 2: Ingestão Bronze ===")

    print("\nIngerindo SCR.data...")
    load_id_scr = carregar_scr(anos=args.anos)
    print(f"  SCR concluído (load_id: {load_id_scr})")

    print("\nIngerindo Selic (Ipeadata)...")
    load_id_selic = carregar_selic()
    print(f"  Selic concluído (load_id: {load_id_selic})")

    print("\n--- Etapas ainda não implementadas ---")
    print("  [ ] Sprint 3: idempotência e carga incremental")
    print("  [ ] Sprint 4: Silver e Gold")
    print("  [ ] Sprint 5: base de ML")


if __name__ == "__main__":
    main()
