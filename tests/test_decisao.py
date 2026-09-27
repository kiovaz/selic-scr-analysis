"""
Testes da etapa de decisão (spec recomendacao-decisao).

Entradas sintéticas escritas nos caminhos do config (isolados pelo conftest).
"""

import json

import numpy as np
import pandas as pd
import pytest

import src.config as config
from src.ml.decisao import executar_decisao, montar_recomendacao, tabela_sensibilidade, trimestre_recomendado

T0 = pd.Timestamp("2026-06-01")


def producao_sintetica(n=40):
    return pd.DataFrame({"uf": [f"U{i:02d}" for i in range(n)], "modalidade": "Imob",
                         "origem": T0, "prob_ganha_forca": np.linspace(0.99, 0.01, n)})


def gold_sintetica(n=40):
    return pd.DataFrame({"ano_mes": T0.date(), "uf": [f"U{i:02d}" for i in range(n)], "modalidade": "Imob",
                         "volume_rs": np.arange(n, dtype=float) + 1})


def previsoes_de_teste_sinteticas():
    """Um mês de teste com 30 combinações: as 20 de maior nota têm 13 acertos (65%)."""
    origem = pd.Timestamp("2025-06-01")
    prob = np.linspace(0.95, 0.05, 30)
    ganha = [1.0] * 13 + [0.0] * 7 + [1.0] * 2 + [0.0] * 8
    prev = pd.DataFrame({"uf": [f"U{i:02d}" for i in range(30)], "modalidade": "Imob", "origem": origem,
                         "ganha_forca": ganha, "prob_ganha_forca": prob})
    # Regra simples: -aceleracao como nota; ordem invertida -> as 20 "maiores" são as últimas 20.
    dataset = prev[["uf", "modalidade", "origem"]].assign(aceleracao_3m=np.linspace(-1, 1, 30)[::-1])
    return prev, dataset


def test_trimestre_recomendado():
    assert trimestre_recomendado(T0) == "set–nov/2026"


def test_lista_com_20_expandir_e_20_alerta_em_ordem():
    rec = montar_recomendacao(producao_sintetica(), gold_sintetica())
    expandir, alerta = rec[rec.grupo == "expandir"], rec[rec.grupo == "alerta"]
    assert len(expandir) == 20 and len(alerta) == 20
    assert expandir.iloc[0]["uf"] == "U00" and expandir["prob_ganha_forca"].is_monotonic_decreasing
    assert alerta.iloc[0]["uf"] == "U39"
    assert expandir.iloc[0]["volume_rs"] == 1.0                     # saldo da combinação no t0


def test_sensibilidade_precisao_das_20_maiores():
    prev, dataset = previsoes_de_teste_sinteticas()
    sens = tabela_sensibilidade(prev, dataset)
    linha20 = sens[(sens.regra == "maiores notas do mês") & (sens.parametro == 20)].iloc[0]
    assert linha20["precisao_modelo"] == pytest.approx(0.65)
    # Regra simples: as 20 maiores notas dela são as linhas 10 a 29, com 5 acertos (linhas 10–12 e 20–21).
    assert linha20["precisao_regra_simples"] == pytest.approx(0.25)
    assert set(sens[sens.regra == "nota mínima"].parametro) == set(config.LIMIARES_SENSIBILIDADE)


def gravar_entradas():
    prev, dataset = previsoes_de_teste_sinteticas()
    config.ARQUIVO_GOLD.parent.mkdir(parents=True, exist_ok=True)
    producao_sintetica().to_parquet(config.ARQUIVO_ML_PREVISAO_PRODUCAO, index=False)
    prev.to_parquet(config.ARQUIVO_ML_PREVISOES_TESTE, index=False)
    dataset.to_parquet(config.ARQUIVO_ML_DATASET, index=False)
    gold_sintetica().to_parquet(config.ARQUIVO_GOLD, index=False)
    pd.DataFrame({"modalidade": ["Imob", "Rural"], "defasagem_meses": [4, 5], "spearman": [0.42, 0.26],
                  "p_ajustado": [0.0001, 0.03], "significativo": [True, True]}
                 ).to_parquet(config.ARQUIVO_ANALISE_BRASIL, index=False)
    config.ARQUIVO_ML_RESULTADOS.write_text(json.dumps({"resumo": {
        "auc_modelo": 0.778, "auc_volta_ao_normal": 0.688, "auc_sem_selic": 0.796,
        "efeito_selic_auc_teste": -0.017}}), encoding="utf-8")


def test_numeros_da_frase_e_reprodutivel():
    gravar_entradas()
    n1 = executar_decisao()
    n2 = executar_decisao()
    n1.pop("gerado_em"); n2.pop("gerado_em")
    assert n1 == n2
    assert n1["acertos_esperados_modelo"] == pytest.approx(13.0)     # 65% de 20
    assert n1["erros_esperados_modelo"] == pytest.approx(7.0)
    assert n1["trimestre_recomendado"] == "set–nov/2026"
    assert n1["associacao_mais_forte_sprint4"]["modalidade"] == "Imob"
    assert config.ARQUIVO_RECOMENDACAO.exists() and config.ARQUIVO_SENSIBILIDADE.exists()


def test_sem_entradas_nao_quebra():
    assert executar_decisao() is None
