"""
Constrói a silver_selic a partir da bronze_selic (seções 2.2, 3.2, 4.1 e 5.2
do docs/architecture.md).

Uma linha por mês (ano_mes), com a Selic acumulada no mês em % a.m.:
- usa a LEITURA MAIS RECENTE de cada mês (maior _ingestion_timestamp): o mês
  corrente muda de valor até fechar, e cada valor novo entrou na Bronze como
  uma linha nova;
- só o recorte jul/2016 a jun/2026;
- NUNCA um mês ainda não fechado (o da execução ou posterior): a Selic
  acumulada de um mês só é definitiva quando o mês termina.

Fora do recorte e mês não fechado são FILTRADOS e contados no relatório.
Inválidos vão para a QUARENTENA: valor que não é número ou data
(tipagem_invalida), valor negativo (valor_negativo) e duas leituras
diferentes do mesmo mês no mesmo instante (duplicata_na_chave — ambíguo,
não dá para escolher).

A Silver é reconstruída inteira a cada execução, sem consultar a fonte.
"""

import datetime
import logging
from collections import Counter

import pandas as pd

from src import config
from src.ingestion.controle import ler_controle, gravar_controle
from src.ingestion.metadata import gerar_load_id
from src.transformation.silver_scr import _gravar_parquet, inicio_e_fim_do_recorte
from src.validation.quality_checks import converter_numero, gravar_quarentena_da_tabela

logger = logging.getLogger(__name__)


def construir_silver_selic(hoje=None):
    """
    Lê a bronze_selic (~600 linhas), escolhe a leitura vigente de cada mês,
    aplica recorte e validação e grava a silver_selic, a quarentena da tabela
    e a parte do relatório. `hoje` existe para os testes (padrão: data atual).
    Devolve a silver_selic (DataFrame) ou None se a Bronze não existir.
    """
    load_id = gerar_load_id()
    hoje = hoje or datetime.date.today()
    caminho = config.DIR_BRONZE / "bronze_selic"
    if not caminho.exists():
        logger.error("bronze_selic não existe. Rode a ingestão antes da Silver.")
        return None

    bronze = pd.read_parquet(caminho, ignore_prefixes=["."])
    contagem = Counter(lidas_da_bronze=len(bronze))
    rejeitados, motivos = [], []

    def quarentena(linhas, motivo):
        if len(linhas):
            rejeitados.append(linhas)
            motivos.append(pd.Series(motivo, index=linhas.index))

    # Mês de cada leitura pelos 10 primeiros caracteres (o fuso da API alterna
    # entre -02:00 e -03:00; o texto completo não serve para comparar).
    bronze["_mes"] = bronze["VALDATA"].fillna("").str[:10]

    # 1. Leitura vigente: a mais recente de cada mês.
    mais_recente = bronze.groupby("_mes")["_ingestion_timestamp"].transform("max")
    vigentes = bronze[bronze["_ingestion_timestamp"] == mais_recente]
    contagem["descartadas_leitura_antiga"] = len(bronze) - len(vigentes)

    # 2. Duas leituras diferentes do mesmo mês no mesmo instante: ambíguo.
    valores_por_mes = vigentes.groupby("_mes")["VALVALOR"].transform("nunique")
    ambiguas = vigentes[valores_por_mes > 1]
    quarentena(ambiguas, "duplicata_na_chave")
    vigentes = vigentes[valores_por_mes <= 1].drop_duplicates("_mes")

    # 3. Data que não é data vai para a quarentena.
    ano_mes = pd.to_datetime(vigentes["_mes"], format="%Y-%m-%d", errors="coerce").dt.to_period("M").dt.to_timestamp()
    quarentena(vigentes[ano_mes.isna()], "tipagem_invalida")
    vigentes, ano_mes = vigentes[ano_mes.notna()], ano_mes[ano_mes.notna()]

    # 4. Recorte e mês não fechado: filtrados e contados (não são inválidos).
    inicio, fim = inicio_e_fim_do_recorte()
    fora = (ano_mes < inicio) | (ano_mes > fim)
    contagem["descartadas_fora_do_recorte"] = int(fora.sum())
    vigentes, ano_mes = vigentes[~fora], ano_mes[~fora]
    mes_atual = pd.Timestamp(hoje.year, hoje.month, 1)
    nao_fechado = ano_mes >= mes_atual
    contagem["descartadas_mes_nao_fechado"] = int(nao_fechado.sum())
    vigentes, ano_mes = vigentes[~nao_fechado], ano_mes[~nao_fechado]

    # 5. Valor: não número -> tipagem_invalida; negativo -> valor_negativo.
    valor = converter_numero(vigentes["VALVALOR"])
    quarentena(vigentes[valor.isna()], "tipagem_invalida")
    quarentena(vigentes[valor < 0], "valor_negativo")
    ok = valor.notna() & (valor >= 0)

    silver = pd.DataFrame({"ano_mes": ano_mes[ok].dt.date, "selic_pct": valor[ok]})
    silver = silver.sort_values("ano_mes").reset_index(drop=True)
    silver["_load_id"] = load_id

    df_rejeitados = pd.concat(rejeitados).drop(columns="_mes") if rejeitados else pd.DataFrame()
    serie_motivos = pd.concat(motivos) if motivos else pd.Series(dtype="object")
    gravar_quarentena_da_tabela(df_rejeitados, serie_motivos, "silver_selic", load_id,
                                "ipeadata", config.DIR_QUARENTENA)
    _gravar_parquet(silver, config.ARQUIVO_SILVER_SELIC)

    relatorio = ler_controle(config.ARQUIVO_RELATORIO_SILVER)
    relatorio["silver_selic"] = {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "_load_id": load_id,
        "recorte": f"{inicio:%Y-%m} a {fim:%Y-%m}",
        **{k: int(v) for k, v in contagem.items()},
        "quarentena_por_motivo": {k: int(v) for k, v in serie_motivos.value_counts().items()},
        "linhas_silver": len(silver),
    }
    gravar_controle(config.ARQUIVO_RELATORIO_SILVER, relatorio)

    logger.info(f"silver_selic: {len(silver)} meses, quarentena {relatorio['silver_selic']['quarentena_por_motivo']}.")
    return silver
