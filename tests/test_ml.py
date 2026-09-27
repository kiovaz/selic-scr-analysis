"""
Testes do ML (specs gold-ml-dataset e modelo-ml).

A Gold sintética tem os 120 meses do recorte (jul/2016–jun/2026). O ponto
central é o anti-vazamento: mexer no futuro não pode mudar as features, e o
teste final não pode influenciar a escolha do modelo.
"""

import json

import numpy as np
import pandas as pd
import pytest

import src.config as config
from src.ml import treino
from src.ml.dataset import (
    FEATURES_NUMERICAS, calcular_rotulo, marcar_conjunto, montar_base,
)

MESES = pd.date_range("2016-07-01", "2026-06-01", freq="MS")
IMOB, RURAL = "Financiamentos imobiliários", "Financiamentos rurais"


def gold_sintetica(ufs=("SP", "RJ", "MG"), modalidades=(IMOB,), buraco=("AP", IMOB), seed=1):
    """Gold com passeio aleatório no volume; `buraco` = combinação com meses faltando."""
    rng = np.random.default_rng(seed)
    selic = np.round(10 + np.cumsum(rng.choice([-0.5, 0, 0, 0.5], len(MESES))), 2)
    linhas = []
    combinacoes = [(u, m) for u in ufs for m in modalidades] + ([buraco] if buraco else [])
    for uf, mod in combinacoes:
        volume = 1e6 * np.exp(np.cumsum(rng.normal(0.01, 0.03, len(MESES))))
        for i, mes in enumerate(MESES):
            if (uf, mod) == buraco and i % 5 == 0:
                continue                                        # mês sem operação
            linhas.append({"ano_mes": mes.date(), "uf": uf, "modalidade": mod,
                           "volume_rs": volume[i], "selic_pct": selic[i]})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------
# gold_ml_dataset
# ---------------------------------------------------------------------

def test_coorte_exclui_combinacao_com_buraco():
    base, excluidas = montar_base(gold_sintetica())
    assert set(base["uf"]) == {"SP", "RJ", "MG"}
    assert [e["uf"] for e in excluidas] == ["AP"]


def test_rotulo_ganha_e_perde_forca():
    idx = pd.date_range("2024-01-01", periods=9, freq="MS")      # t = índice 3
    def serie(v_tm3, v_t, v_t2, v_t5):
        v = pd.Series(100.0, index=idx)
        v.iloc[0], v.iloc[3], v.iloc[5], v.iloc[8] = v_tm3, v_t, v_t2, v_t5
        return v.to_frame("x")
    ganha = calcular_rotulo(serie(100, 102, 100, 104)).iloc[3, 0]   # 2% -> 4%
    perde = calcular_rotulo(serie(100, 106, 100, 102)).iloc[3, 0]   # 6% -> 2%, ainda crescendo
    assert ganha == 1 and perde == 0


def test_mexer_no_futuro_nao_muda_as_features():
    gold = gold_sintetica()
    origem = pd.Timestamp("2021-03-01")
    base_antes, _ = montar_base(gold)
    futuro = pd.to_datetime(gold["ano_mes"]) > origem
    alterada = gold.copy()
    alterada.loc[futuro, "volume_rs"] *= 3.7
    alterada.loc[futuro, "selic_pct"] += 5
    base_depois, _ = montar_base(alterada)

    antes = base_antes[base_antes["origem"] == origem].set_index("uf")[FEATURES_NUMERICAS]
    depois = base_depois[base_depois["origem"] == origem].set_index("uf")[FEATURES_NUMERICAS]
    pd.testing.assert_frame_equal(antes, depois)


def test_primeira_origem_tem_12_meses_de_historico():
    base, _ = montar_base(gold_sintetica())
    assert base["origem"].min() == pd.Timestamp("2017-07-01")


def test_conjuntos_sem_sobreposicao_e_chave_unica():
    base, _ = montar_base(gold_sintetica())
    dev = base[base["conjunto"] == "desenvolvimento"]
    teste = base[base["conjunto"] == "teste"]
    producao = base[base["conjunto"] == "producao"]

    ultimo_mes_de_rotulo_dev = dev["origem"].max() + pd.DateOffset(months=5)
    assert ultimo_mes_de_rotulo_dev < teste["origem"].min()
    assert set(producao["origem"]) == {pd.Timestamp("2026-06-01")}
    assert producao["ganha_forca"].isna().all()
    assert teste["origem"].max() == pd.Timestamp("2026-01-01")
    assert base.duplicated(["uf", "modalidade", "origem"]).sum() == 0


# ---------------------------------------------------------------------
# Treino e avaliação
# ---------------------------------------------------------------------

def base_com_sinal(ruido=1.0, n_ufs=4, seed=3):
    """
    Base pronta com um sinal plantado: ganha_forca = (rel_3m + ruído > 0).
    Com ruido=0 o rótulo é perfeitamente previsível (deve disparar o alerta).
    """
    rng = np.random.default_rng(seed)
    origens = pd.date_range("2017-07-01", "2026-06-01", freq="MS")
    linhas = []
    for uf in [f"U{i}" for i in range(n_ufs)]:
        for mod in (IMOB, RURAL):
            for o in origens:
                linha = {c: rng.normal() for c in FEATURES_NUMERICAS}
                linha.update(uf=uf, modalidade=mod, origem=o, volume_origem=rng.uniform(1, 100))
                linha["ganha_forca"] = float(linha["rel_3m"] + ruido * rng.normal() > 0)
                linhas.append(linha)
    base = pd.DataFrame(linhas)
    t0 = pd.Timestamp("2026-06-01")
    tem_rotulo = base["origem"] <= t0 - pd.DateOffset(months=5)
    base.loc[~tem_rotulo, "ganha_forca"] = np.nan
    base["conjunto"] = marcar_conjunto(base["origem"], tem_rotulo, t0)
    return base.dropna(subset=["conjunto"]).reset_index(drop=True)


def test_baseline_volta_ao_normal():
    avaliacao = pd.DataFrame({"aceleracao_3m": [-1.5, 2.0], "ganha_forca": [1.0, 0.0]})
    _, previsao = treino.baselines(avaliacao, avaliacao)["volta_ao_normal"]
    assert list(previsao) == [1, 0]


def test_precisao_nas_melhores_apostas():
    avaliacao = pd.DataFrame({"origem": [pd.Timestamp("2025-02-01")] * 30,
                              "ganha_forca": [1.0] * 13 + [0.0] * 17})
    pontuacao = list(range(30, 10, -1)) + list(range(10))          # as 20 maiores são as 20 primeiras
    assert treino.precisao_melhores_apostas(avaliacao, pontuacao, top=20) == pytest.approx(0.65)


def test_padronizacao_ajustada_so_no_treino():
    base = base_com_sinal()
    treino_df = base[base["conjunto"] == "desenvolvimento"]
    pipeline = treino.montar_pipeline("regressao_logistica")
    pipeline.fit(treino_df[treino.colunas_de_entrada()], treino_df["ganha_forca"].astype(int))
    escala = pipeline.named_steps["preparo"].named_transformers_["numericas"]
    np.testing.assert_allclose(escala.mean_, treino_df[FEATURES_NUMERICAS].mean().to_numpy())


def test_rotulos_do_teste_nao_mudam_a_escolha():
    base = base_com_sinal()
    escolha_1 = treino.escolher_modelo(treino.janela_movel(base))
    embaralhada = base.copy()
    no_teste = embaralhada["conjunto"] == "teste"
    embaralhada.loc[no_teste, "ganha_forca"] = 1 - embaralhada.loc[no_teste, "ganha_forca"]
    assert treino.escolher_modelo(treino.janela_movel(embaralhada)) == escolha_1


def test_sinal_plantado_supera_classe_majoritaria():
    base = base_com_sinal(ruido=1.0)
    resultado, _ = treino.teste_final(base, "regressao_logistica")
    assert resultado["modelo"]["auc"] > 0.65
    assert resultado["classe_majoritaria"]["auc"] == 0.5
    assert "rel_3m" == next(iter(resultado["importancia_variaveis"]))   # a variável plantada é a mais importante


def test_base_perfeita_dispara_alerta():
    resultados = treino.executar_ml(base_com_sinal(ruido=0.0), [])
    assert resultados["alertas"], "uma base perfeitamente previsível tem que gerar alerta"


def test_saidas_reprodutiveis_e_producao():
    base = base_com_sinal()
    r1 = treino.executar_ml(base, [])
    prod_1 = pd.read_parquet(config.ARQUIVO_ML_PREVISAO_PRODUCAO)
    r2 = treino.executar_ml(base, [])
    prod_2 = pd.read_parquet(config.ARQUIVO_ML_PREVISAO_PRODUCAO)

    r1.pop("gerado_em"); r2.pop("gerado_em")
    assert json.dumps(r1, sort_keys=True, default=str) == json.dumps(r2, sort_keys=True, default=str)
    pd.testing.assert_frame_equal(prod_1, prod_2)
    assert len(prod_1) == base[base["conjunto"] == "producao"].shape[0]
    assert prod_1["prob_ganha_forca"].between(0, 1).all()
    assert set(r1["resumo"]["efeito_selic_auc_por_bloco"]) == {str(a) for a in config.BLOCOS_JANELA_MOVEL}
