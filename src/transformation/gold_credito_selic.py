"""
Constrói a gold_credito_selic a partir da Silver (seções 2.4, 4.1 e 5.3 do
docs/architecture.md).

Uma linha por (ano_mes, uf, modalidade): o crédito da silver_scr com a Selic do
mesmo mês, mais as variações e as defasagens usadas na análise.

Regras (decisões do grupo registradas na seção 5.3):
- VARIAÇÃO SÓ ENTRE MESES CONSECUTIVOS: a variação de uma combinação só é
  calculada quando ela tem linha no mês imediatamente anterior pelo
  calendário (coluna tem_mes_anterior). Se o mês anterior não existe (buraco
  na série), a variação fica vazia — nunca se compara com um mês mais antigo
  e nunca se preenche o buraco.
- var_qtd_pct fica vazia também quando a quantidade anterior é 0 (toda a
  quantidade estava escondida pelo BCB): não existe variação % a partir de 0.
- A Selic é nacional e não tem buracos: a variação e as defasagens dela são
  calculadas UMA vez na série da Selic, pelo calendário, e entram na Gold pelo
  join. Assim uma combinação com buraco recebe a Selic certa de k meses antes.
- ÓRFÃOS: meses do SCR sem Selic e meses da Selic sem SCR são contados e vão
  para o relatório (seção 2.4).

A Gold não limpa nada (seção 4.1): se precisasse limpar aqui, a Silver falhou.
É reconstruída inteira a cada execução.
"""

import datetime
import logging

import pandas as pd

from src import config
from src.ingestion.controle import ler_controle, gravar_controle
from src.transformation.silver_scr import _gravar_parquet

logger = logging.getLogger(__name__)

CHAVE = ["ano_mes", "uf", "modalidade"]
COLUNAS_GOLD = (
    CHAVE
    + ["qtd_operacoes", "linhas_qtd_nao_divulgada", "volume_rs", "tem_mes_anterior",
       "var_qtd_pct", "var_volume_pct", "selic_pct", "var_selic_pp"]
    + [f"selic_lag_{k}" for k in range(1, config.DEFASAGEM_MAXIMA + 1)]
)


def serie_da_selic(silver_selic):
    """
    Série mensal da Selic com a variação (pontos percentuais) e as defasagens
    de 1 a DEFASAGEM_MAXIMA meses. asfreq("MS") garante um mês por linha, em
    sequência — então shift(k) é exatamente "k meses antes" no calendário.
    """
    selic = silver_selic.assign(ano_mes=pd.to_datetime(silver_selic["ano_mes"]))
    selic = selic.set_index("ano_mes")[["selic_pct"]].sort_index().asfreq("MS")
    selic["var_selic_pp"] = selic["selic_pct"].diff()
    for k in range(1, config.DEFASAGEM_MAXIMA + 1):
        selic[f"selic_lag_{k}"] = selic["selic_pct"].shift(k)
    return selic.dropna(subset=["selic_pct"]).reset_index()


def variacoes_por_combinacao(scr):
    """
    tem_mes_anterior, var_volume_pct e var_qtd_pct, calculados separadamente
    para cada (uf, modalidade) e ordenados por mês — nunca misturando
    combinações diferentes (seção 5.3).
    """
    scr = scr.sort_values(["uf", "modalidade", "ano_mes"]).reset_index(drop=True)
    # Linha anterior DA MESMA combinação (pode estar vários meses para trás, se houver buraco).
    anterior = scr.groupby(["uf", "modalidade"])[["ano_mes", "volume_rs", "qtd_operacoes"]].shift(1)
    # Ela só vale como "mês anterior" se for mesmo o mês imediatamente anterior.
    mes_esperado = scr["ano_mes"] - pd.DateOffset(months=1)
    scr["tem_mes_anterior"] = anterior["ano_mes"] == mes_esperado

    scr["var_volume_pct"] = ((scr["volume_rs"] / anterior["volume_rs"] - 1) * 100) \
        .where(scr["tem_mes_anterior"])
    scr["var_qtd_pct"] = ((scr["qtd_operacoes"] / anterior["qtd_operacoes"] - 1) * 100) \
        .where(scr["tem_mes_anterior"] & (anterior["qtd_operacoes"] > 0))
    return scr


def construir_gold():
    """
    Lê a silver_scr e a silver_selic, cruza por ano_mes, calcula variações e
    defasagens e grava a gold_credito_selic e o relatório. Devolve a Gold
    (DataFrame) ou None se a Silver não existir.
    """
    if not config.ARQUIVO_SILVER_SCR.exists() or not config.ARQUIVO_SILVER_SELIC.exists():
        logger.error("Silver não encontrada. Rode a Silver antes da Gold.")
        return None

    scr = pd.read_parquet(config.ARQUIVO_SILVER_SCR).drop(columns="_load_id", errors="ignore")
    scr["ano_mes"] = pd.to_datetime(scr["ano_mes"])
    selic = serie_da_selic(pd.read_parquet(config.ARQUIVO_SILVER_SELIC))

    # Órfãos dos dois lados: junção completa só para CONTAR (seção 2.4).
    meses_scr = pd.DataFrame({"ano_mes": scr["ano_mes"].drop_duplicates()})
    cruzamento = meses_scr.merge(selic[["ano_mes"]], on="ano_mes", how="outer", indicator=True)
    orfaos_scr = sorted(cruzamento.loc[cruzamento["_merge"] == "left_only", "ano_mes"].dt.strftime("%Y-%m"))
    orfaos_selic = sorted(cruzamento.loc[cruzamento["_merge"] == "right_only", "ano_mes"].dt.strftime("%Y-%m"))

    # Variações do crédito (por combinação) e depois o join com a Selic do mês.
    gold = variacoes_por_combinacao(scr).merge(selic, on="ano_mes", how="inner")
    gold = gold[COLUNAS_GOLD].sort_values(CHAVE).reset_index(drop=True)
    gold["ano_mes"] = gold["ano_mes"].dt.date

    _gravar_parquet(gold, config.ARQUIVO_GOLD)

    relatorio = {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "linhas_gold": len(gold),
        "linhas_silver_scr": len(scr),
        "meses": int(gold["ano_mes"].nunique()),
        "orfaos_meses_scr_sem_selic": orfaos_scr,
        "orfaos_meses_selic_sem_scr": orfaos_selic,
        "linhas_sem_mes_anterior": int((~gold["tem_mes_anterior"]).sum()),
        "linhas_var_qtd_vazia": int(gold["var_qtd_pct"].isna().sum()),
    }
    gravar_controle(config.ARQUIVO_RELATORIO_GOLD, relatorio)
    logger.info(f"gold_credito_selic: {len(gold)} linhas; órfãos SCR {len(orfaos_scr)}, "
                f"Selic {len(orfaos_selic)}.")
    return gold
