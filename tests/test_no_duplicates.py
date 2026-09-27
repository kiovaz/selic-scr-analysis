"""
Prova de que a chave da Bronze não tem duplicata (seção 4.2 do architecture.md):

    df.duplicated(["_source_object", "_record_hash"]).sum() == 0

vale para bronze_scr e bronze_selic depois de qualquer sequência de execuções
— repetida, com republicação e com interrupção no meio.
"""

import src.config as config
from src.ingestion import scr_file_loader
from src.ingestion.scr_file_loader import carregar_scr
from src.ingestion.selic_api_loader import carregar_selic
from tests.fontes_simuladas import BCBSimulado, ipeadata_simulado, ler_bronze, linhas_scr, selic

CHAVE = ["_source_object", "_record_hash"]


def test_bronze_scr_sem_duplicata_na_chave_apos_varias_execucoes(monkeypatch):
    monkeypatch.setattr(config, "SCR_TAMANHO_BLOCO", 2)
    bcb = BCBSimulado()
    bcb.publicar(2024, '"v1"', {"scrdata_202401.csv": (linhas_scr(1, 5), (2026, 3, 25, 0, 0, 0))})

    original = scr_file_loader.anexar_metadados
    chamadas = {"n": 0}

    def falha_uma_vez(*args, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 3:
            raise RuntimeError("queda simulada")
        return original(*args, **kwargs)

    with bcb.no_ar():
        with monkeypatch.context() as m:
            m.setattr(scr_file_loader, "anexar_metadados", falha_uma_vez)
            carregar_scr(anos=[2024])                      # interrompida
        carregar_scr(anos=[2024])                          # completa
        carregar_scr(anos=[2024])                          # repetida
        bcb.publicar(2024, '"v2"', {"scrdata_202401.csv": (linhas_scr(1, 4, extra="x"), (2026, 9, 1, 0, 0, 0))})
        carregar_scr(anos=[2024])                          # republicada
        carregar_scr(anos=[2024])                          # repetida de novo

    bronze = ler_bronze("bronze_scr")
    assert len(bronze) == 5 + 4
    assert bronze.duplicated(CHAVE).sum() == 0


def test_bronze_selic_sem_duplicata_na_chave_apos_varias_execucoes():
    for serie in [
        selic(("2026-08-01", 1.09), ("2026-09-01", 0.50)),
        selic(("2026-08-01", 1.09), ("2026-09-01", 0.50)),
        selic(("2026-08-01", 1.09), ("2026-09-01", 0.88)),
        selic(("2026-08-01", 1.09), ("2026-09-01", 0.88), ("2026-10-01", 0.30)),
        selic(("2026-08-01", 1.09), ("2026-09-01", 0.88), ("2026-10-01", 0.30)),
    ]:
        with ipeadata_simulado(serie):
            carregar_selic()

    bronze = ler_bronze("bronze_selic")
    assert len(bronze) == 4        # ago, set (0.50), set (0.88), out
    assert bronze.duplicated(CHAVE).sum() == 0
