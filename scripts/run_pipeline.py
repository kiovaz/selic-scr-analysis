"""
Executa o pipeline inteiro, de ponta a ponta.

Cada sprint acrescenta uma etapa aqui. Por enquanto (Sprint 1) só prepara
as pastas e confirma que a configuração carrega.

Como rodar (da raiz do projeto):
    python scripts/run_pipeline.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config  # noqa: E402


def main():
    print("Preparando as pastas de dados...")
    config.criar_pastas()
    print(f"  Bronze : {config.DIR_BRONZE}")
    print(f"  Silver : {config.DIR_SILVER}")
    print(f"  Gold   : {config.DIR_GOLD}")

    print(f"\nRecorte do projeto: {config.MES_INICIO:02d}/{config.ANO_INICIO} "
          f"a 12/{config.ANO_FIM}")
    print(f"Modalidades: as que começam com '{config.PREFIXO_MODALIDADE}'")

    print("\n--- Etapas ainda não implementadas ---")
    print("  [ ] Sprint 2: ingestão Bronze")
    print("  [ ] Sprint 3: idempotência e carga incremental")
    print("  [ ] Sprint 4: Silver e Gold")
    print("  [ ] Sprint 5: base de ML")


if __name__ == "__main__":
    main()
