"""
Idempotência da Bronze (seção 3.2 do architecture.md; spec idempotencia-bronze).

Regra central: rodar a ingestão duas vezes seguidas, sem novidade na fonte,
não muda a contagem de linhas. E quando a fonte publica algo novo, entra
exatamente o que é novo — nem mais, nem menos.

Tudo roda sem rede (servidores simulados em tests/fontes_simuladas.py) e em
pastas temporárias (tests/conftest.py).
"""

import pandas as pd

import src.config as config
from src.ingestion import scr_file_loader
from src.ingestion.controle import ler_controle
from src.ingestion.scr_file_loader import carregar_scr, montar_source_object
from src.ingestion.selic_api_loader import carregar_selic
from tests.fontes_simuladas import BCBSimulado, ipeadata_simulado, ler_bronze, linhas_scr, selic

VERSAO_MARCO = (2026, 3, 25, 17, 29, 40)
VERSAO_SETEMBRO = (2026, 9, 15, 2, 38, 32)


def _bcb_com_2024():
    """BCB simulado com o ZIP de 2024 contendo janeiro (5 linhas) e agosto (4 linhas)."""
    bcb = BCBSimulado()
    bcb.publicar(2024, '"v1"', {
        "scrdata_202401.csv": (linhas_scr(1, 5), VERSAO_MARCO),
        "scrdata_202408.csv": (linhas_scr(8, 4), VERSAO_MARCO),
    })
    return bcb


# ---------------------------------------------------------------------
# SCR
# ---------------------------------------------------------------------

def test_pipeline_rodado_duas_vezes_nao_muda_a_contagem():
    bcb = _bcb_com_2024()
    with bcb.no_ar():
        carregar_scr(anos=[2024])
        contagem_1 = len(ler_bronze("bronze_scr"))
        carregar_scr(anos=[2024])
        contagem_2 = len(ler_bronze("bronze_scr"))

    assert contagem_1 == 9
    assert contagem_2 == contagem_1
    assert bcb.downloads == 1          # a segunda execução não baixou o ZIP


def test_republicacao_acrescenta_so_a_versao_nova_e_preserva_a_antiga():
    bcb = _bcb_com_2024()
    with bcb.no_ar():
        carregar_scr(anos=[2024])
        # O BCB republica agosto: 3 linhas (uma a menos), nova data no ZIP, novo ETag.
        bcb.publicar(2024, '"v2"', {
            "scrdata_202401.csv": (linhas_scr(1, 5), VERSAO_MARCO),
            "scrdata_202408.csv": (linhas_scr(8, 3), VERSAO_SETEMBRO),
        })
        carregar_scr(anos=[2024])

    bronze = ler_bronze("bronze_scr")
    por_versao = bronze["_source_object"].value_counts()
    assert por_versao["scrdata_202408.csv@2026-03-25T17:29:40"] == 4   # versão antiga preservada
    assert por_versao["scrdata_202408.csv@2026-09-15T02:38:32"] == 3   # versão nova completa
    assert por_versao["scrdata_202401.csv@2026-03-25T17:29:40"] == 5   # janeiro não foi regravado
    assert len(bronze) == 9 + 3
    assert bcb.downloads == 2


def test_execucao_interrompida_e_completada_sem_duplicar(monkeypatch):
    monkeypatch.setattr(config, "SCR_TAMANHO_BLOCO", 2)   # 5 linhas de janeiro = 3 blocos
    bcb = BCBSimulado()
    bcb.publicar(2024, '"v1"', {"scrdata_202401.csv": (linhas_scr(1, 5), VERSAO_MARCO)})

    # Primeira execução "morre" ao anexar os metadados do segundo bloco.
    original = scr_file_loader.anexar_metadados
    chamadas = {"n": 0}

    def falha_no_segundo_bloco(*args, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 2:
            raise RuntimeError("queda simulada")
        return original(*args, **kwargs)

    with bcb.no_ar():
        with monkeypatch.context() as m:
            m.setattr(scr_file_loader, "anexar_metadados", falha_no_segundo_bloco)
            carregar_scr(anos=[2024])
        assert len(ler_bronze("bronze_scr")) == 2          # só o primeiro bloco chegou
        status = ler_controle(config.ARQUIVO_CONTROLE_SCR)["2024"]["csvs"]["scrdata_202401.csv"]["status"]
        assert status == "em_andamento"

        carregar_scr(anos=[2024])                          # execução seguinte, normal

    bronze = ler_bronze("bronze_scr")
    assert len(bronze) == 5
    assert bronze.duplicated(["_source_object", "_record_hash"]).sum() == 0
    status = ler_controle(config.ARQUIVO_CONTROLE_SCR)["2024"]["csvs"]["scrdata_202401.csv"]["status"]
    assert status == "completo"


def test_controle_apagado_e_reconstruido_sem_duplicar():
    bcb = _bcb_com_2024()
    with bcb.no_ar():
        carregar_scr(anos=[2024])
        contagem = len(ler_bronze("bronze_scr"))
        config.ARQUIVO_CONTROLE_SCR.unlink()               # alguém apagou o controle
        carregar_scr(anos=[2024])

    assert len(ler_bronze("bronze_scr")) == contagem
    assert config.ARQUIVO_CONTROLE_SCR.exists()            # e ele foi refeito


def test_mes_novo_publicado_entra_sozinho():
    bcb = _bcb_com_2024()
    with bcb.no_ar():
        carregar_scr(anos=[2024])
        bcb.publicar(2024, '"v2"', {
            "scrdata_202401.csv": (linhas_scr(1, 5), VERSAO_MARCO),
            "scrdata_202408.csv": (linhas_scr(8, 4), VERSAO_MARCO),
            "scrdata_202409.csv": (linhas_scr(9, 2), VERSAO_SETEMBRO),
        })
        carregar_scr(anos=[2024])

    por_arquivo = ler_bronze("bronze_scr")["_source_object"].str.split("@").str[0].value_counts()
    assert por_arquivo.to_dict() == {"scrdata_202401.csv": 5, "scrdata_202408.csv": 4, "scrdata_202409.csv": 2}


def test_consulta_de_versao_falha_e_zip_local_e_usado():
    bcb = _bcb_com_2024()
    with bcb.no_ar():
        carregar_scr(anos=[2024])
    # Agora sem servidor (a rede está bloqueada pelo conftest): HEAD falha.
    carregar_scr(anos=[2024])
    assert len(ler_bronze("bronze_scr")) == 9


def test_source_object_com_versao_e_caso_de_crc_sem_data_nova():
    assert montar_source_object("scrdata_202408.csv", "2026-09-15T02:38:32", "aaaa") == \
        "scrdata_202408.csv@2026-09-15T02:38:32"
    anterior = {"data": "2026-09-15T02:38:32", "crc32": "bbbb"}
    assert montar_source_object("scrdata_202408.csv", "2026-09-15T02:38:32", "aaaa", anterior) == \
        "scrdata_202408.csv@2026-09-15T02:38:32#crcaaaa"


# ---------------------------------------------------------------------
# Selic
# ---------------------------------------------------------------------

def test_selic_nada_mudou_nao_grava_nada():
    serie = selic(("2026-07-01", 1.22), ("2026-08-01", 1.09), ("2026-09-01", 0.88))
    with ipeadata_simulado(serie):
        carregar_selic()
        carregar_selic()

    bronze = ler_bronze("bronze_selic")
    assert len(bronze) == 3
    assert set(bronze["_ingestion_mode"]) == {"full"}


def test_selic_mes_corrente_mudou_de_valor_vira_linha_nova():
    with ipeadata_simulado(selic(("2026-08-01", 1.09), ("2026-09-01", 0.88))):
        carregar_selic()
    with ipeadata_simulado(selic(("2026-08-01", 1.09), ("2026-09-01", 1.05))):
        carregar_selic()

    bronze = ler_bronze("bronze_selic")
    setembro = bronze[bronze["VALDATA"].str.startswith("2026-09")]
    assert sorted(setembro["VALVALOR"]) == ["0.88", "1.05"]        # a leitura antiga fica
    assert len(bronze) == 3
    assert list(setembro.sort_values("_ingestion_timestamp")["_ingestion_mode"]) == ["full", "incremental"]


def test_selic_mes_novo_avanca_o_watermark_e_antigos_nao_sao_regravados():
    with ipeadata_simulado(selic(("1974-01-01", 1.46), ("2026-09-01", 1.10))):
        carregar_selic()
    assert ler_controle(config.ARQUIVO_CONTROLE_SELIC)["watermark"] == "2026-09-01"

    with ipeadata_simulado(selic(("1974-01-01", 1.46), ("2026-09-01", 1.10), ("2026-10-01", 0.40))):
        carregar_selic()

    bronze = ler_bronze("bronze_selic")
    assert len(bronze) == 3                                            # só outubro entrou
    assert ler_controle(config.ARQUIVO_CONTROLE_SELIC)["watermark"] == "2026-10-01"
    assert (bronze["VALDATA"].str.startswith("1974")).sum() == 1
