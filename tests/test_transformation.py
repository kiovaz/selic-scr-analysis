"""
Testes da camada Silver (specs silver-scr e silver-selic).

A Bronze de cada teste é montada pelos próprios loaders, com o BCB e o
Ipeadata simulados (tests/fontes_simuladas.py) — assim a Silver é testada
sobre uma Bronze no formato real. Sem rede, em pastas temporárias (conftest).
"""

import datetime

import pandas as pd

import src.config as config
from src.ingestion.scr_file_loader import carregar_scr
from src.ingestion.selic_api_loader import carregar_selic
from src.transformation.silver_scr import construir_silver_scr
from src.transformation.silver_selic import construir_silver_selic
from tests.fontes_simuladas import BCBSimulado, ipeadata_simulado, selic

IMOB = "Financiamentos imobiliários"
VERSAO_1 = (2026, 3, 25, 17, 29, 40)
VERSAO_2 = (2026, 9, 15, 2, 38, 32)


def linha(data_base="2024-08-31", uf="SP", modalidade=IMOB, qtd="10", saldo="100,00"):
    """Uma linha do CSV do SCR com as 5 colunas usadas e uma coluna extra (tudo texto)."""
    return {"data_base": data_base, "uf": uf, "modalidade": modalidade,
            "numero_de_operacoes": qtd, "carteira_ativa": saldo, "porte": "PF"}


def ingerir_scr(*publicacoes):
    """Publica, em sequência, versões do ZIP de 2024 e ingere cada uma na Bronze."""
    bcb = BCBSimulado()
    with bcb.no_ar():
        for etag, csvs in publicacoes:
            bcb.publicar(2024, etag, csvs)
            carregar_scr(anos=[2024])


def relatorio():
    return pd.read_json(config.ARQUIVO_RELATORIO_SILVER, typ="series")


def quarentena(tabela):
    caminho = config.DIR_QUARENTENA / f"{tabela}.parquet"
    return pd.read_parquet(caminho) if caminho.exists() else pd.DataFrame(columns=["motivo"])


# ---------------------------------------------------------------------
# silver_scr
# ---------------------------------------------------------------------

def test_agregacao_com_quantidade_como_limite_inferior():
    ingerir_scr(('"v1"', {"scrdata_202408.csv": ([
        linha(qtd="10", saldo="100,00"),
        linha(qtd="-1", saldo="50,00"),
        linha(qtd="5", saldo="25,00"),
        linha(uf="RJ", qtd="-1", saldo="7,50"),
        linha(uf="RJ", qtd="-1", saldo="2,50"),
    ], VERSAO_1)}))

    silver = construir_silver_scr().set_index("uf")

    assert silver.loc["SP", "qtd_operacoes"] == 15
    assert silver.loc["SP", "linhas_qtd_nao_divulgada"] == 1
    assert silver.loc["SP", "volume_rs"] == 175.0
    assert silver.loc["RJ", "qtd_operacoes"] == 0          # tudo escondido: 0, não nulo
    assert silver.loc["RJ", "linhas_qtd_nao_divulgada"] == 2
    assert silver.loc["RJ", "volume_rs"] == 10.0
    assert silver.loc["SP", "ano_mes"] == datetime.date(2024, 8, 1)   # primeiro dia do mês


def test_usa_so_a_versao_mais_recente_de_cada_csv():
    ingerir_scr(
        ('"v1"', {"scrdata_202408.csv": ([linha(saldo="100,00"), linha(saldo="1,00")], VERSAO_1)}),
        ('"v2"', {"scrdata_202408.csv": ([linha(saldo="300,00")], VERSAO_2)}),
    )

    silver = construir_silver_scr()

    assert list(silver["volume_rs"]) == [300.0]
    assert relatorio()["silver_scr"]["descartadas_versao_antiga"] == 2


def test_fora_do_escopo_e_filtrado_e_contado_sem_quarentena():
    ingerir_scr(('"v1"', {"scrdata_202408.csv": ([
        linha(),
        linha(modalidade="Empréstimos"),
        linha(data_base="2016-06-30"),
        linha(data_base="2026-07-31"),
    ], VERSAO_1)}))

    silver = construir_silver_scr()
    rel = relatorio()["silver_scr"]

    assert len(silver) == 1
    assert rel["descartadas_modalidade_fora_do_escopo"] == 1
    assert rel["descartadas_fora_do_recorte"] == 2
    assert len(quarentena("silver_scr")) == 0


def test_invalidos_vao_para_a_quarentena_com_o_motivo_certo():
    ingerir_scr(('"v1"', {"scrdata_202408.csv": ([
        linha(saldo="100,00"),
        linha(uf="XX", saldo="-3,00"),     # dois problemas: fica o primeiro (uf)
        linha(saldo="abc"),
        linha(qtd="-5"),
        linha(qtd="-1", saldo="1,00"),     # -1 é máscara, não é inválido
    ], VERSAO_1)}))

    silver = construir_silver_scr()
    motivos = quarentena("silver_scr")["motivo"].value_counts().to_dict()

    assert motivos == {"uf_invalida": 1, "tipagem_invalida": 1, "valor_negativo": 1}
    assert silver.loc[0, "volume_rs"] == 101.0
    assert silver.loc[0, "linhas_qtd_nao_divulgada"] == 1
    assert '"uf": "XX"' in quarentena("silver_scr").query("motivo == 'uf_invalida'").iloc[0]["payload"]


def test_reconstrucao_e_idempotente_e_nao_duplica_a_quarentena():
    ingerir_scr(('"v1"', {"scrdata_202408.csv": ([linha(), linha(uf="XX"), linha(uf="MG")], VERSAO_1)}))

    primeira = construir_silver_scr().drop(columns="_load_id")
    quarentena_1 = quarentena("silver_scr").drop(columns=["_load_id", "quarantined_at"])
    segunda = construir_silver_scr().drop(columns="_load_id")
    quarentena_2 = quarentena("silver_scr").drop(columns=["_load_id", "quarantined_at"])

    pd.testing.assert_frame_equal(primeira, segunda)
    pd.testing.assert_frame_equal(quarentena_1, quarentena_2)
    assert len(quarentena_2) == 1


def test_meses_faltando_nao_sao_preenchidos_e_vao_para_o_relatorio():
    ingerir_scr(('"v1"', {
        "scrdata_202401.csv": ([linha(data_base="2024-01-31"), linha(data_base="2024-01-31", uf="AP")], VERSAO_1),
        "scrdata_202402.csv": ([linha(data_base="2024-02-29")], VERSAO_1),
    }))

    silver = construir_silver_scr()
    incompletas = {(c["uf"], c["meses_presentes"]) for c in relatorio()["silver_scr"]["combinacoes_incompletas"]}

    assert len(silver[silver["uf"] == "AP"]) == 1           # só janeiro, fevereiro não foi inventado
    assert ("AP", 1) in incompletas and ("SP", 2) in incompletas


# ---------------------------------------------------------------------
# silver_selic — Selic META do Copom, diária, % ao ano; corte pelo último dia do mês
# ---------------------------------------------------------------------

HOJE = datetime.date(2026, 9, 27)


def dias(inicio, fim, valor):
    """Pares (dia, valor) para todos os dias corridos de `inicio` a `fim` (como a série do Ipeadata)."""
    return [(d.strftime("%Y-%m-%d"), valor) for d in pd.date_range(inicio, fim, freq="D")]


def test_selic_corte_pelo_ultimo_dia_do_mes():
    # Março/2026: 15,00 até o dia 18 e 14,75 a partir do 19 (corte do Copom).
    serie = dias("2026-02-01", "2026-02-28", 15.0) + dias("2026-03-01", "2026-03-18", 15.0) \
        + dias("2026-03-19", "2026-03-31", 14.75)
    with ipeadata_simulado(selic(*serie)):
        carregar_selic()

    silver = construir_silver_selic(hoje=HOJE).set_index("ano_mes")["selic_pct"]

    assert silver[datetime.date(2026, 2, 1)] == 15.0
    assert silver[datetime.date(2026, 3, 1)] == 14.75
    assert len(silver) == 2                                   # uma linha por mês, não por dia


def test_selic_usa_a_leitura_mais_recente_do_ultimo_dia():
    with ipeadata_simulado(selic(("2026-05-30", 14.5), ("2026-05-31", 14.25))):
        carregar_selic()
    with ipeadata_simulado(selic(("2026-05-30", 14.5), ("2026-05-31", 14.0))):
        carregar_selic()

    silver = construir_silver_selic(hoje=HOJE)

    assert list(silver["selic_pct"]) == [14.0]


def test_selic_recorte_e_mes_nao_fechado():
    serie = selic(("1996-07-31", 23.3), ("2016-06-30", 14.25), ("2016-07-31", 14.25),
                  ("2026-06-30", 14.25), ("2026-07-31", 14.0))
    with ipeadata_simulado(serie):
        carregar_selic()

    # Executando em junho/2026: junho ainda não fechou e não pode entrar.
    silver = construir_silver_selic(hoje=datetime.date(2026, 6, 15))
    rel = relatorio()["silver_selic"]

    assert [d.isoformat() for d in silver["ano_mes"]] == ["2016-07-01"]
    assert rel["meses_fora_do_recorte"] == 3                  # jul/1996, jun/2016, jul/2026
    assert rel["meses_nao_fechados"] == 1                     # jun/2026


def test_selic_ultimo_dia_invalido_usa_o_dia_valido_anterior():
    with ipeadata_simulado(selic(("2024-02-28", 11.25), ("2024-02-29", None))):
        carregar_selic()

    silver = construir_silver_selic(hoje=HOJE)

    assert list(silver["selic_pct"]) == [11.25]
    assert quarentena("silver_selic")["motivo"].tolist() == ["tipagem_invalida"]


def test_selic_leituras_ambiguas_vao_para_a_quarentena():
    # Duas leituras do mesmo dia, no mesmo instante, com valores diferentes.
    instante = pd.Timestamp("2026-09-27 10:00:00")
    bronze = pd.DataFrame({
        "VALDATA": ["2024-03-31T00:00:00-03:00", "2024-03-31T00:00:00-03:00",
                    "2024-03-30T00:00:00-03:00", "2024-04-30T00:00:00-03:00"],
        "VALVALOR": ["10.75", "11.0", "10.75", "10.75"],
        "_ingestion_timestamp": [instante] * 4,
        "_ingestion_date": [datetime.date(2026, 9, 27)] * 4,
        "_source_object": [config.SELIC_URL] * 4,
        "_record_hash": ["a", "b", "c", "d"],
    })
    bronze.to_parquet(config.DIR_BRONZE / "bronze_selic", partition_cols=["_ingestion_date"], index=False)

    silver = construir_silver_selic(hoje=HOJE).set_index("ano_mes")["selic_pct"]

    assert quarentena("silver_selic")["motivo"].tolist() == ["duplicata_na_chave", "duplicata_na_chave"]
    assert silver[datetime.date(2024, 3, 1)] == 10.75          # usou o dia 30, o último dia não ambíguo


def test_selic_ignora_linhas_de_outra_serie():
    with ipeadata_simulado(selic(("2024-01-31", 11.75))):
        carregar_selic()
    # Linhas da série antiga (outra URL) esquecidas na Bronze.
    antiga = pd.DataFrame({
        "VALDATA": ["2024-01-01T00:00:00-02:00"], "VALVALOR": ["0.97"],
        "_ingestion_timestamp": [pd.Timestamp("2026-09-27 12:00:00")],
        "_ingestion_date": [datetime.date(2026, 9, 27)],
        "_source_object": ["http://.../ValoresSerie(SERCODIGO='BM12_TJOVER12')"], "_record_hash": ["z"],
    })
    antiga.to_parquet(config.DIR_BRONZE / "bronze_selic", partition_cols=["_ingestion_date"], index=False)

    silver = construir_silver_selic(hoje=HOJE)

    assert list(silver["selic_pct"]) == [11.75]
    assert relatorio()["silver_selic"]["descartadas_outra_serie"] == 1
