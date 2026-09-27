"""
Etapa de decisão (Sprint 6 — seções 1 e 10 do docs/architecture.md).

Transforma as previsões do modelo em uma recomendação para o decisor — a
diretoria de crédito de uma instituição financeira de atuação nacional:

- LISTA DO TRIMESTRE: as 20 combinações estado × modalidade com maior
  probabilidade de o crédito ganhar força (expandir) e as 20 com menor
  (alerta: tendem a perder força). Regra adotada pelo grupo: lista fixa de
  20, não nota mínima — o erro de expandir onde o crédito perde força tem
  custo imediato, então vale ser seletivo.
- TABELA DE SENSIBILIDADE: com as previsões do TESTE, quanto cada regra
  alternativa (notas mínimas 0,5 a 0,9; listas de 10, 20 e 40) teria
  recomendado e acertado — a justificativa do limiar.
- NÚMEROS DA FRASE DE FECHAMENTO: tudo o que a frase final e a seção 10
  citam, gerado aqui para nenhum número da entrega ser digitado à mão.

Só lê arquivos de data/final/ (sem rede) e é determinística.
"""

import datetime
import logging

import pandas as pd

from src import config
from src.ingestion.controle import ler_controle, gravar_controle
from src.transformation.silver_scr import _gravar_parquet

logger = logging.getLogger(__name__)

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def trimestre_recomendado(t0):
    """Meses cobertos pela previsão da origem t0: t0+3 a t0+5 (o crescimento de t+2 a t+5)."""
    inicio = pd.Timestamp(t0) + pd.DateOffset(months=config.FOLGA_PUBLICACAO_MESES + 1)
    fim = pd.Timestamp(t0) + pd.DateOffset(months=config.FOLGA_PUBLICACAO_MESES + config.HORIZONTE_MESES)
    return f"{MESES[inicio.month - 1]}–{MESES[fim.month - 1]}/{fim.year}"


def montar_recomendacao(producao, gold, top=None):
    """
    As `top` combinações de maior probabilidade (expandir) e as `top` de menor
    (alerta), com a posição no ranking e o saldo da combinação no t0.
    """
    top = top or config.TOP_RECOMENDACAO
    t0 = pd.to_datetime(producao["origem"]).max()
    gold = gold.assign(ano_mes=pd.to_datetime(gold["ano_mes"]))
    saldo = gold[gold["ano_mes"] == t0][["uf", "modalidade", "volume_rs"]]
    base = producao[["uf", "modalidade", "prob_ganha_forca"]].merge(saldo, on=["uf", "modalidade"], how="left")

    expandir = base.sort_values(["prob_ganha_forca", "uf", "modalidade"], ascending=[False, True, True]).head(top)
    alerta = base.sort_values(["prob_ganha_forca", "uf", "modalidade"], ascending=[True, True, True]).head(top)
    return pd.concat([
        expandir.assign(grupo="expandir", posicao=range(1, len(expandir) + 1)),
        alerta.assign(grupo="alerta", posicao=range(1, len(alerta) + 1)),
    ], ignore_index=True)[["grupo", "posicao", "uf", "modalidade", "prob_ganha_forca", "volume_rs"]]


def _precisao_das_maiores(df, pontuacao, n):
    """Média, entre os meses, da fração que ganhou força entre as n maiores pontuações do mês."""
    d = df.assign(_p=pontuacao.to_numpy())
    return float(d.groupby("origem").apply(lambda g: g.nlargest(n, "_p")["ganha_forca"].mean(),
                                           include_groups=False).mean())


def tabela_sensibilidade(previsoes_teste, dataset):
    """
    Com as previsões do teste: para cada nota mínima e cada tamanho de lista,
    quantas combinações seriam recomendadas por mês e quantas acertariam —
    modelo e regra simples ("volta ao normal": se perdeu força, ganha).
    """
    df = previsoes_teste.merge(dataset[["uf", "modalidade", "origem", "aceleracao_3m"]],
                               on=["uf", "modalidade", "origem"], how="left")
    meses = df["origem"].nunique()
    total_positivos = df["ganha_forca"].sum()
    linhas = []
    for limiar in config.LIMIARES_SENSIBILIDADE:
        rec = df[df["prob_ganha_forca"] >= limiar]
        linhas.append({"regra": "nota mínima", "parametro": limiar,
                       "recomendadas_por_mes": len(rec) / meses,
                       "precisao_modelo": float(rec["ganha_forca"].mean()) if len(rec) else float("nan"),
                       "recall_modelo": float(rec["ganha_forca"].sum() / total_positivos),
                       "precisao_regra_simples": float("nan")})
    for n in config.TAMANHOS_LISTA:
        linhas.append({"regra": "maiores notas do mês", "parametro": n,
                       "recomendadas_por_mes": float(n),
                       "precisao_modelo": _precisao_das_maiores(df, df["prob_ganha_forca"], n),
                       "recall_modelo": float("nan"),
                       "precisao_regra_simples": _precisao_das_maiores(df, -df["aceleracao_3m"], n)})
    return pd.DataFrame(linhas)


def numeros_da_frase(recomendacao, sensibilidade, previsoes_teste, ml_resultados, analise_brasil, t0):
    """Todos os números que a frase de fechamento e a seção 10 citam."""
    n = config.TOP_RECOMENDACAO
    lista = sensibilidade[(sensibilidade["regra"] == "maiores notas do mês") & (sensibilidade["parametro"] == n)].iloc[0]
    acaso = float(previsoes_teste["ganha_forca"].mean())
    significativas = analise_brasil[analise_brasil["significativo"]]
    mais_forte = (significativas if len(significativas) else analise_brasil) \
        .assign(abs_rho=lambda d: d["spearman"].abs()).sort_values("abs_rho", ascending=False).iloc[0]
    expandir = recomendacao[recomendacao["grupo"] == "expandir"]
    resumo = ml_resultados["resumo"]
    return {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "trimestre_recomendado": trimestre_recomendado(t0),
        "tamanho_lista": n,
        "precisao_lista_modelo": float(lista["precisao_modelo"]),
        "precisao_lista_regra_simples": float(lista["precisao_regra_simples"]),
        "precisao_acaso": acaso,
        "acertos_esperados_modelo": float(lista["precisao_modelo"]) * n,
        "erros_esperados_modelo": (1 - float(lista["precisao_modelo"])) * n,
        "acertos_esperados_regra_simples": float(lista["precisao_regra_simples"]) * n,
        "acertos_esperados_acaso": acaso * n,
        "auc_modelo": resumo["auc_modelo"],
        "auc_regra_simples": resumo["auc_volta_ao_normal"],
        "auc_sem_selic": resumo["auc_sem_selic"],
        "efeito_selic_auc_teste": resumo["efeito_selic_auc_teste"],
        "saldo_total_lista_expandir_rs": float(expandir["volume_rs"].sum()),
        "associacao_mais_forte_sprint4": {
            "modalidade": mais_forte["modalidade"],
            "defasagem_meses": int(mais_forte["defasagem_meses"]),
            "spearman": float(mais_forte["spearman"]),
            "p_ajustado": float(mais_forte["p_ajustado"]),
        },
        "top3_expandir": expandir.head(3)[["uf", "modalidade", "prob_ganha_forca"]].to_dict("records"),
    }


def executar_decisao():
    """Lê as saídas do ML e da análise, grava a lista, a tabela e os números da frase."""
    necessarios = [config.ARQUIVO_ML_PREVISAO_PRODUCAO, config.ARQUIVO_ML_PREVISOES_TESTE,
                   config.ARQUIVO_ML_RESULTADOS, config.ARQUIVO_ML_DATASET, config.ARQUIVO_GOLD,
                   config.ARQUIVO_ANALISE_BRASIL]
    faltando = [str(c) for c in necessarios if not c.exists()]
    if faltando:
        logger.error(f"Decisão: faltam as saídas {faltando}. Rode o pipeline antes.")
        return None

    producao = pd.read_parquet(config.ARQUIVO_ML_PREVISAO_PRODUCAO)
    previsoes_teste = pd.read_parquet(config.ARQUIVO_ML_PREVISOES_TESTE)
    dataset = pd.read_parquet(config.ARQUIVO_ML_DATASET)
    gold = pd.read_parquet(config.ARQUIVO_GOLD)

    recomendacao = montar_recomendacao(producao, gold)
    sensibilidade = tabela_sensibilidade(previsoes_teste, dataset)
    numeros = numeros_da_frase(recomendacao, sensibilidade, previsoes_teste,
                               ler_controle(config.ARQUIVO_ML_RESULTADOS),
                               pd.read_parquet(config.ARQUIVO_ANALISE_BRASIL),
                               pd.to_datetime(producao["origem"]).max())

    _gravar_parquet(recomendacao, config.ARQUIVO_RECOMENDACAO)
    _gravar_parquet(sensibilidade, config.ARQUIVO_SENSIBILIDADE)
    gravar_controle(config.ARQUIVO_FRASE, numeros)
    return numeros
