"""
Testes da análise estatística (spec analise-estatistica).

A Gold de teste é montada com uma relação CONHECIDA: a variação do volume é
exatamente o oposto (×10) da variação da Selic de 2 meses antes. A análise
precisa recuperar isso: Spearman = −1 em k = 2.
"""

import numpy as np
import pandas as pd

import src.config as config
from src.analise.correlacao import (
    analise_brasil,
    analise_uf,
    grafico_por_modalidade,
    mapa_de_calor,
    nome_curto,
)

IMOB = "Financiamentos imobiliários"
RURAL = "Financiamentos rurais  (ex-financiamentos rurais e agroindustriais)"


def gold_sintetica(meses=60, seed=7):
    """Gold com duas modalidades em SP; var_volume(t) = −10 × var_selic(t − 2)."""
    rng = np.random.default_rng(seed)
    datas = pd.date_range("2018-01-01", periods=meses, freq="MS")
    var_selic = pd.Series(rng.normal(0, 0.1, meses), index=datas)
    var_selic.iloc[0] = np.nan
    alvo = -10 * var_selic.shift(2)
    linhas = []
    for modalidade, ruido in [(IMOB, 0.0), (RURAL, 5.0)]:
        volume = 1000.0
        for i, data in enumerate(datas):
            var = alvo.iloc[i] if not np.isnan(alvo.iloc[i]) else 0.0
            var += rng.normal(0, ruido) if ruido else 0.0
            if i:
                volume *= 1 + var / 100
            linhas.append({"ano_mes": data.date(), "uf": "SP", "modalidade": modalidade,
                           "volume_rs": volume, "tem_mes_anterior": i > 0,
                           "var_volume_pct": var if i else np.nan, "var_selic_pp": var_selic.iloc[i]})
    # Uma combinação pequena: AP com só 5 meses válidos.
    for i in range(6):
        linhas.append({"ano_mes": datas[i].date(), "uf": "AP", "modalidade": IMOB, "volume_rs": 10.0 + i,
                       "tem_mes_anterior": i > 0, "var_volume_pct": 5.0 * i if i else np.nan,
                       "var_selic_pp": var_selic.iloc[i]})
    return pd.DataFrame(linhas)


def test_nivel_brasil_recupera_a_relacao_conhecida():
    brasil = analise_brasil(gold_sintetica())
    imob = brasil[brasil["modalidade"] == IMOB].set_index("defasagem_meses")

    assert len(brasil) == 2 * (config.DEFASAGEM_MAXIMA + 1)
    assert imob.loc[2, "spearman"] < -0.95                     # quase −1 (o AP pequeno entra na soma)
    assert imob["spearman"].abs().idxmax() == 2
    assert (brasil["p_ajustado"] >= brasil["p_valor"] - 1e-12).all()
    assert imob.loc[2, "significativo"]


def test_nivel_uf_usa_a_defasagem_do_brasil_e_a_amostra_minima():
    gold = gold_sintetica()
    brasil = analise_brasil(gold)
    uf = analise_uf(gold, brasil).set_index(["uf", "modalidade"])

    assert uf.loc[("SP", IMOB), "defasagem_meses"] == 2
    assert uf.loc[("AP", IMOB), "defasagem_meses"] == 2          # mesma k* da modalidade
    assert uf.loc[("AP", IMOB), "amostra_insuficiente"]
    assert pd.isna(uf.loc[("AP", IMOB), "spearman"])
    assert uf.loc[("SP", IMOB), "spearman"] == -1.0


def test_graficos_sao_gerados(tmp_path):
    gold = gold_sintetica()
    brasil = analise_brasil(gold)
    uf = analise_uf(gold, brasil)

    grafico_por_modalidade(brasil, tmp_path / "a.png")
    mapa_de_calor(uf, tmp_path / "b.png")

    assert (tmp_path / "a.png").stat().st_size > 10_000
    assert (tmp_path / "b.png").stat().st_size > 10_000


def test_nome_curto_das_modalidades():
    assert nome_curto("Financiamentos") == "Financiamentos (geral)"
    assert nome_curto(IMOB) == "Imobiliários"
    assert nome_curto(RURAL) == "Rurais"
