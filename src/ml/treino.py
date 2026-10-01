"""
Treino e avaliação do modelo "o crédito vai ganhar força?" (seção 6 do
docs/architecture.md).

Ordem (seção 8: baseline primeiro, modelo depois):
1. Baselines: classe majoritária e "volta ao normal" (se o crédito perdeu
   força nos últimos 3 meses, prevê que vai ganhar).
2. Janela móvel por ano (2020–2023): para cada ano, treina só com origens até
   julho do ano anterior (o rótulo olha até t+5) e avalia no ano. Serve para
   ESCOLHER o modelo e ver se o resultado se repete em anos diferentes.
   Candidatos: regressão logística e gradient boosting, cada um COM e SEM as
   variáveis da Selic.
3. Teste final (fev/2025–jan/2026), usado UMA vez: o modelo escolhido, a
   mesma arquitetura sem a Selic e os baselines.
4. Produção: treina com tudo o que tem rótulo e prevê set–nov/2026.

Anti-vazamento: pré-processamento e modelo ficam num único Pipeline, com
fit só nas linhas de treino de cada avaliação; o teste só recebe predict.
"""

import datetime
import json
import logging

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src import config
from src.ingestion.controle import gravar_controle
from src.ml.dataset import FEATURES_CATEGORICAS, FEATURES_NUMERICAS, FEATURES_SELIC, construir_gold_ml_dataset
from src.transformation.silver_scr import _gravar_parquet

logger = logging.getLogger(__name__)

ROTULO = "ganha_forca"
CANDIDATOS = ["regressao_logistica", "gradient_boosting"]
LIMITE_ALERTA = 0.95


# ---------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------

def features(com_selic):
    """Colunas numéricas usadas pelo modelo (sem as da Selic, se com_selic=False)."""
    return [f for f in FEATURES_NUMERICAS if com_selic or f not in FEATURES_SELIC]


def montar_pipeline(tipo, com_selic=True):
    """
    Padronização das numéricas + one-hot de UF e modalidade + modelo, num
    único Pipeline: o fit acontece só com os dados de treino passados a ele.
    """
    preparo = ColumnTransformer([
        ("numericas", StandardScaler(), features(com_selic)),
        ("categoricas", OneHotEncoder(handle_unknown="ignore", sparse_output=False), FEATURES_CATEGORICAS),
    ])
    if tipo == "regressao_logistica":
        modelo = LogisticRegression(C=1.0, max_iter=1000)
    elif tipo == "gradient_boosting":
        modelo = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, random_state=config.SEMENTE)
    else:
        raise ValueError(f"modelo desconhecido: {tipo}")
    return Pipeline([("preparo", preparo), ("modelo", modelo)])


def colunas_de_entrada():
    return FEATURES_NUMERICAS + FEATURES_CATEGORICAS


# ---------------------------------------------------------------------
# Baselines e métricas
# ---------------------------------------------------------------------

def baselines(treino, avaliacao):
    """
    Pontuação (para a AUC) e previsão (0/1) dos dois baselines:
    - classe majoritária do treino (pontuação constante: AUC 0,5);
    - volta ao normal: perdeu força (aceleracao_3m < 0) -> vai ganhar.
    """
    majoritaria = int(treino[ROTULO].mean() >= 0.5)
    return {
        "classe_majoritaria": (pd.Series(0.5, index=avaliacao.index),
                               pd.Series(majoritaria, index=avaliacao.index)),
        "volta_ao_normal": (-avaliacao["aceleracao_3m"],
                            (avaliacao["aceleracao_3m"] < 0).astype(int)),
    }


def _auc(y, pontuacao, peso=None):
    if y.nunique() < 2 or pd.Series(pontuacao).nunique() < 2:
        return 0.5 if y.nunique() == 2 else float("nan")
    return float(roc_auc_score(y, pontuacao, sample_weight=peso))


def precisao_melhores_apostas(avaliacao, pontuacao, top=None):
    """
    Para cada mês de origem, das `top` combinações com maior pontuação, a
    fração que de fato ganhou força. Devolve a média entre os meses.
    """
    top = top or config.TOP_APOSTAS
    d = avaliacao[["origem", ROTULO]].assign(pontuacao=np.asarray(pontuacao))
    por_mes = d.groupby("origem").apply(
        lambda g: g.nlargest(top, "pontuacao")[ROTULO].mean(), include_groups=False)
    return float(por_mes.mean())


def metricas(avaliacao, pontuacao, previsao):
    """Todas as métricas de uma avaliação (classe positiva = ganha força = expandir)."""
    y = avaliacao[ROTULO].astype(int)
    pontuacao, previsao = pd.Series(np.asarray(pontuacao), index=y.index), pd.Series(np.asarray(previsao), index=y.index)
    resultado = {
        "auc": _auc(y, pontuacao),
        "auc_pesada_volume": _auc(y, pontuacao, avaliacao["volume_origem"]),
        "precisao_melhores_apostas": precisao_melhores_apostas(avaliacao, pontuacao),
        "precisao": float(precision_score(y, previsao, zero_division=0)),
        "recall": float(recall_score(y, previsao, zero_division=0)),
        "f1": float(f1_score(y, previsao, zero_division=0)),
        "acuracia": float(accuracy_score(y, previsao)),
        "linhas": int(len(y)),
    }
    resultado["auc_por_modalidade"] = {
        mod: _auc(y[idx], pontuacao[idx]) for mod, idx in avaliacao.groupby("modalidade").groups.items()}
    return resultado


def alertas(resultado_modelo):
    """Métrica acima de 0,95 é motivo de investigação, não de comemoração (seção 6.4)."""
    return [f"{nome} = {valor:.3f} (acima de {LIMITE_ALERTA}): possível vazamento — investigar"
            for nome, valor in resultado_modelo.items()
            if isinstance(valor, float) and valor > LIMITE_ALERTA]


def _treinar_e_pontuar(tipo, com_selic, treino, avaliacao):
    pipeline = montar_pipeline(tipo, com_selic)
    pipeline.fit(treino[colunas_de_entrada()], treino[ROTULO].astype(int))
    prob = pipeline.predict_proba(avaliacao[colunas_de_entrada()])[:, 1]
    return pipeline, prob


# ---------------------------------------------------------------------
# Janela móvel, teste final e produção
# ---------------------------------------------------------------------

def janela_movel(base):
    """
    AUC de cada candidato (com e sem Selic) e dos baselines em cada bloco
    anual. Treino de cada bloco: origens de desenvolvimento até julho do ano
    anterior, cujo rótulo (até t+5) termina antes do bloco começar.
    """
    dev = base[base["conjunto"] == "desenvolvimento"]
    blocos = {}
    for ano in config.BLOCOS_JANELA_MOVEL:
        treino = dev[dev["origem"] <= pd.Timestamp(ano - 1, 7, 1)]
        avaliacao = dev[dev["origem"].dt.year == ano]
        bloco = {"linhas_treino": len(treino), "linhas_avaliacao": len(avaliacao)}
        for tipo in CANDIDATOS:
            for com_selic in (True, False):
                _, prob = _treinar_e_pontuar(tipo, com_selic, treino, avaliacao)
                bloco[f"{tipo}{'' if com_selic else '_sem_selic'}"] = _auc(avaliacao[ROTULO].astype(int), prob)
        for nome, (pontuacao, _) in baselines(treino, avaliacao).items():
            bloco[nome] = _auc(avaliacao[ROTULO].astype(int), pontuacao)
        blocos[str(ano)] = bloco
    return blocos


def escolher_modelo(blocos):
    """
    Maior AUC média nos blocos entre as versões COM Selic. Se a diferença para
    a regressão logística for menor que 0,01, vence a logística (mais fácil de
    explicar).
    """
    medias = {tipo: float(np.mean([b[tipo] for b in blocos.values()])) for tipo in CANDIDATOS}
    melhor = max(medias, key=medias.get)
    if melhor != "regressao_logistica" and medias[melhor] - medias["regressao_logistica"] < 0.01:
        melhor = "regressao_logistica"
    return melhor, medias


def importancia_das_variaveis(pipeline, avaliacao):
    """Queda de AUC ao embaralhar cada variável original (inclusive UF e modalidade inteiras)."""
    colunas = colunas_de_entrada()
    r = permutation_importance(pipeline, avaliacao[colunas], avaliacao[ROTULO].astype(int),
                               scoring="roc_auc", n_repeats=10, random_state=config.SEMENTE)
    return dict(sorted(zip(colunas, map(float, r.importances_mean)), key=lambda kv: -kv[1]))


def coeficientes(pipeline):
    """Coeficientes padronizados da regressão logística (sinal = direção da relação)."""
    nomes = pipeline.named_steps["preparo"].get_feature_names_out()
    valores = pipeline.named_steps["modelo"].coef_[0]
    return dict(sorted(zip(map(str, nomes), map(float, valores)), key=lambda kv: -abs(kv[1])))


def teste_final(base, escolhido):
    """Avalia UMA vez no teste: o escolhido com e sem Selic e os baselines."""
    treino = base[base["conjunto"] == "desenvolvimento"]
    teste = base[base["conjunto"] == "teste"].copy()
    resultado = {}
    pipeline, prob = _treinar_e_pontuar(escolhido, True, treino, teste)
    resultado["modelo"] = metricas(teste, prob, (prob >= 0.5).astype(int))
    _, prob_sem = _treinar_e_pontuar(escolhido, False, treino, teste)
    resultado["modelo_sem_selic"] = metricas(teste, prob_sem, (prob_sem >= 0.5).astype(int))
    for nome, (pontuacao, previsao) in baselines(treino, teste).items():
        resultado[nome] = metricas(teste, pontuacao, previsao)
    resultado["importancia_variaveis"] = importancia_das_variaveis(pipeline, teste)
    if escolhido == "regressao_logistica":
        resultado["coeficientes"] = coeficientes(pipeline)
    previsoes = teste[["uf", "modalidade", "origem", ROTULO]].assign(prob_ganha_forca=prob,
                                                                    prob_sem_selic=prob_sem)
    return resultado, previsoes


def prever_producao(base, escolhido):
    """Treina com tudo o que tem rótulo e prevê a origem t0 (trimestre set–nov/2026)."""
    rotuladas = base[base["conjunto"].isin(["desenvolvimento", "embargo", "teste"])]
    producao = base[base["conjunto"] == "producao"]
    _, prob = _treinar_e_pontuar(escolhido, True, rotuladas, producao)
    return (producao[["uf", "modalidade", "origem"]].assign(prob_ganha_forca=prob)
            .sort_values("prob_ganha_forca", ascending=False).reset_index(drop=True))


def executar_ml(base=None, excluidas=None):
    """Roda tudo, grava as saídas e devolve o dicionário de resultados."""
    if base is None:
        base, excluidas = construir_gold_ml_dataset()
        if base is None:
            return None

    # Com poucos anos de dados (ex.: run_pipeline.py --anos 2024) nenhuma
    # combinação tem os 120 meses da coorte: não há o que treinar. O ML é
    # pulado com um aviso, em vez de quebrar o pipeline.
    contagem = base["conjunto"].value_counts()
    if contagem.get("desenvolvimento", 0) == 0 or contagem.get("teste", 0) == 0:
        logger.warning("ML pulado: dados insuficientes (a coorte exige os 120 meses do recorte; "
                       "rode o pipeline completo, sem --anos).")
        return None

    blocos = janela_movel(base)
    escolhido, medias = escolher_modelo(blocos)
    resultado_teste, previsoes_teste = teste_final(base, escolhido)
    producao = prever_producao(base, escolhido)

    modelo, sem_selic, volta = (resultado_teste[k] for k in ("modelo", "modelo_sem_selic", "volta_ao_normal"))
    resultados = {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "pergunta": "o crédito da combinação vai ganhar força de t+2 a t+5 (mais que de t−3 a t)?",
        "linhas_por_conjunto": {k: int(v) for k, v in base["conjunto"].value_counts().items()},
        "combinacoes_excluidas": excluidas or [],
        "janela_movel": blocos,
        "auc_media_janela_movel": medias,
        "modelo_escolhido": escolhido,
        "teste": resultado_teste,
        "resumo": {
            "auc_modelo": modelo["auc"],
            "auc_sem_selic": sem_selic["auc"],
            "efeito_selic_auc_teste": modelo["auc"] - sem_selic["auc"],
            "efeito_selic_auc_por_bloco": {ano: b[escolhido] - b[f"{escolhido}_sem_selic"] for ano, b in blocos.items()},
            "auc_volta_ao_normal": volta["auc"],
            "supera_volta_ao_normal": modelo["auc"] > volta["auc"],
            "melhores_apostas_modelo": modelo["precisao_melhores_apostas"],
            "melhores_apostas_volta_ao_normal": volta["precisao_melhores_apostas"],
        },
        "alertas": alertas(modelo),
    }
    gravar_controle(config.ARQUIVO_ML_RESULTADOS, resultados)
    _gravar_parquet(previsoes_teste, config.ARQUIVO_ML_PREVISOES_TESTE)
    _gravar_parquet(producao, config.ARQUIVO_ML_PREVISAO_PRODUCAO)
    logger.info(f"ML: escolhido {escolhido}; AUC teste {modelo['auc']:.3f} "
                f"(sem Selic {sem_selic['auc']:.3f}, volta ao normal {volta['auc']:.3f}).")
    return resultados
