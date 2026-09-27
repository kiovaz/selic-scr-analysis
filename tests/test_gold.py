"""
Testes da gold_credito_selic (spec gold-credito-selic).

A Silver de cada teste é escrita direto nos caminhos do config (isolados em
pasta temporária pelo conftest), com poucos meses escolhidos a dedo.
"""

import datetime

import pandas as pd
import pytest

import src.config as config
from src.transformation.gold_credito_selic import construir_gold

IMOB = "Financiamentos imobiliários"
TIT = "Financiamentos de títulos e valores mobiliários"


def gravar_silver(linhas_scr, selic):
    """linhas_scr: (AAAA-MM, uf, modalidade, qtd, volume); selic: {AAAA-MM: valor}."""
    scr = pd.DataFrame([{
        "ano_mes": datetime.date(int(m[:4]), int(m[5:]), 1), "uf": uf, "modalidade": mod,
        "qtd_operacoes": qtd, "linhas_qtd_nao_divulgada": 0, "volume_rs": float(vol), "_load_id": "x",
    } for m, uf, mod, qtd, vol in linhas_scr])
    sel = pd.DataFrame([{"ano_mes": datetime.date(int(m[:4]), int(m[5:]), 1), "selic_pct": v, "_load_id": "x"}
                        for m, v in selic.items()])
    config.ARQUIVO_SILVER_SCR.parent.mkdir(parents=True, exist_ok=True)
    scr.to_parquet(config.ARQUIVO_SILVER_SCR, index=False)
    sel.to_parquet(config.ARQUIVO_SILVER_SELIC, index=False)


def linha(gold, mes, uf, mod=IMOB):
    return gold[(gold["ano_mes"] == datetime.date(int(mes[:4]), int(mes[5:]), 1))
                & (gold["uf"] == uf) & (gold["modalidade"] == mod)].iloc[0]


def relatorio():
    return pd.read_json(config.ARQUIVO_RELATORIO_GOLD, typ="series")


def test_orfaos_dos_dois_lados():
    gravar_silver([("2024-01", "SP", IMOB, 10, 100), ("2024-02", "SP", IMOB, 10, 100),
                   ("2024-03", "SP", IMOB, 10, 100)],
                  {"2024-01": 0.9, "2024-02": 0.8, "2024-04": 0.7})

    gold = construir_gold()

    assert relatorio()["orfaos_meses_scr_sem_selic"] == ["2024-03"]
    assert relatorio()["orfaos_meses_selic_sem_scr"] == ["2024-04"]
    assert datetime.date(2024, 3, 1) not in set(gold["ano_mes"])


def test_mesma_selic_para_todas_as_ufs_do_mes():
    gravar_silver([("2024-01", uf, IMOB, 1, 1) for uf in ["SP", "RJ", "MG"]], {"2024-01": 0.97})
    gold = construir_gold()
    assert set(gold["selic_pct"]) == {0.97}


def test_buraco_na_serie_e_valor_conhecido():
    gravar_silver([("2016-09", "AP", TIT, 1, 100), ("2016-10", "AP", TIT, 1, 150),
                   ("2017-02", "AP", TIT, 1, 300)],
                  {m: 1.0 for m in ["2016-09", "2016-10", "2016-11", "2016-12", "2017-01", "2017-02"]})

    gold = construir_gold()
    setembro, outubro, fevereiro = (linha(gold, m, "AP", TIT) for m in ["2016-09", "2016-10", "2017-02"])

    assert not setembro["tem_mes_anterior"] and pd.isna(setembro["var_volume_pct"])
    assert outubro["tem_mes_anterior"] and outubro["var_volume_pct"] == pytest.approx(50.0)
    assert not fevereiro["tem_mes_anterior"] and pd.isna(fevereiro["var_volume_pct"])   # não compara com outubro
    assert relatorio()["linhas_sem_mes_anterior"] == 2


def test_quantidade_anterior_zero_deixa_so_a_var_qtd_vazia():
    gravar_silver([("2024-01", "SP", IMOB, 0, 100), ("2024-02", "SP", IMOB, 8, 120)],
                  {"2024-01": 0.9, "2024-02": 0.8})

    fevereiro = linha(construir_gold(), "2024-02", "SP")

    assert pd.isna(fevereiro["var_qtd_pct"])
    assert fevereiro["var_volume_pct"] == pytest.approx(20.0)


def test_selic_variacao_e_defasagens_pelo_calendario():
    meses = pd.date_range("2016-07-01", "2017-02-01", freq="MS").strftime("%Y-%m")
    selic = {m: round(1.0 + i / 10, 1) for i, m in enumerate(meses)}      # 1.0, 1.1, ..., 1.7
    scr = [(m, "SP", IMOB, 1, 1) for m in meses] + [
        (m, "AP", TIT, 1, 1) for m in meses if m != "2017-01"]             # AP sem janeiro/2017
    gravar_silver(scr, selic)

    gold = construir_gold()
    janeiro, julho = linha(gold, "2017-01", "SP"), linha(gold, "2016-07", "SP")
    fevereiro_ap = linha(gold, "2017-02", "AP", TIT)

    assert [janeiro[f"selic_lag_{k}"] for k in range(1, 7)] == [1.5, 1.4, 1.3, 1.2, 1.1, 1.0]
    assert janeiro["var_selic_pp"] == pytest.approx(0.1)
    assert pd.isna(julho["var_selic_pp"]) and all(pd.isna(julho[f"selic_lag_{k}"]) for k in range(1, 7))
    assert fevereiro_ap["selic_lag_1"] == 1.6                              # Selic de jan/2017, mesmo sem a linha do AP
    assert not fevereiro_ap["tem_mes_anterior"]


def test_gold_reconstruida_e_idempotente():
    gravar_silver([("2024-01", "SP", IMOB, 5, 100), ("2024-02", "SP", IMOB, 6, 110)],
                  {"2024-01": 0.9, "2024-02": 0.8})
    pd.testing.assert_frame_equal(construir_gold(), construir_gold())
