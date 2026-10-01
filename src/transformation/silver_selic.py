"""
Constrói a silver_selic a partir da bronze_selic (seções 2.2, 3.2, 4.1 e 5.2
do docs/architecture.md).

Uma linha por mês (ano_mes), com a Selic META fixada pelo Copom, em % AO ANO:
- usa só as linhas da série configurada (config.SELIC_URL). Se a Bronze ainda
  tiver linhas de outra série (a antiga, % ao mês), elas são ignoradas —
  misturar % a.m. com % a.a. daria números sem sentido;
- a Bronze tem um valor por DIA. Para cada dia vale a leitura mais recente
  (maior _ingestion_timestamp);
- CORTE MENSAL: o valor do mês é a meta vigente no ÚLTIMO dia do mês com
  valor válido. Assim a variação de um mês para o outro é exatamente a
  decisão do Copom (ex.: mar/2026 = 14,75, -0,25 contra fevereiro);
- só o recorte jul/2016 a jun/2026, e NUNCA um mês ainda não fechado (o da
  execução ou posterior): a meta do fim do mês só é conhecida quando ele acaba.

Fora do recorte, mês não fechado e outra série são FILTRADOS e contados no
relatório. Inválidos vão para a QUARENTENA (e não entram no corte):
valor que não é número ou data (tipagem_invalida), valor negativo
(valor_negativo) e duas leituras diferentes do mesmo dia no mesmo instante
(duplicata_na_chave — ambíguo, não dá para escolher).

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
    Lê a bronze_selic (~11 mil leituras diárias), escolhe a leitura vigente de
    cada dia, valida, faz o corte mensal pelo último dia válido e aplica
    recorte e "só meses fechados". Grava a silver_selic, a quarentena da
    tabela e a parte do relatório. `hoje` existe para os testes (padrão: data
    atual). Devolve a silver_selic (DataFrame) ou None se a Bronze não existir.
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

    # 1. Só a série configurada (a URL identifica a série).
    da_serie = bronze["_source_object"] == config.SELIC_URL
    contagem["descartadas_outra_serie"] = int((~da_serie).sum())
    leituras = bronze[da_serie].copy()

    # Dia de cada leitura pelos 10 primeiros caracteres (o fuso da API alterna
    # entre -02:00 e -03:00; o texto completo não serve para comparar).
    leituras["_dia"] = leituras["VALDATA"].fillna("").str[:10]

    # 2. Leitura vigente: a mais recente de cada DIA.
    mais_recente = leituras.groupby("_dia")["_ingestion_timestamp"].transform("max")
    vigentes = leituras[leituras["_ingestion_timestamp"] == mais_recente]
    contagem["descartadas_leitura_antiga"] = len(leituras) - len(vigentes)

    # 3. Duas leituras diferentes do mesmo dia no mesmo instante: ambíguo.
    valores_por_dia = vigentes.groupby("_dia")["VALVALOR"].transform("nunique")
    quarentena(vigentes[valores_por_dia > 1], "duplicata_na_chave")
    vigentes = vigentes[valores_por_dia <= 1].drop_duplicates("_dia")

    # 4. Validação por dia: data e valor. Inválidos não entram no corte.
    dia = pd.to_datetime(vigentes["_dia"], format="%Y-%m-%d", errors="coerce")
    valor = converter_numero(vigentes["VALVALOR"])
    quarentena(vigentes[dia.isna()], "tipagem_invalida")
    quarentena(vigentes[dia.notna() & valor.isna()], "tipagem_invalida")
    quarentena(vigentes[dia.notna() & (valor < 0)], "valor_negativo")
    ok = dia.notna() & valor.notna() & (valor >= 0)
    diarios = pd.DataFrame({"dia": dia[ok], "selic_pct": valor[ok]})
    contagem["dias_validos"] = len(diarios)

    # 5. Corte mensal: a meta vigente no ÚLTIMO dia válido de cada mês.
    diarios["ano_mes"] = diarios["dia"].dt.to_period("M").dt.to_timestamp()
    mensal = diarios.sort_values("dia").groupby("ano_mes", as_index=False).last()

    # 6. Recorte e mês não fechado: filtrados e contados (não são inválidos).
    inicio, fim = inicio_e_fim_do_recorte()
    fora = (mensal["ano_mes"] < inicio) | (mensal["ano_mes"] > fim)
    contagem["meses_fora_do_recorte"] = int(fora.sum())
    mensal = mensal[~fora]
    mes_atual = pd.Timestamp(hoje.year, hoje.month, 1)
    nao_fechado = mensal["ano_mes"] >= mes_atual
    contagem["meses_nao_fechados"] = int(nao_fechado.sum())
    mensal = mensal[~nao_fechado]

    silver = pd.DataFrame({"ano_mes": mensal["ano_mes"].dt.date, "selic_pct": mensal["selic_pct"]})
    silver = silver.sort_values("ano_mes").reset_index(drop=True)
    silver["_load_id"] = load_id

    df_rejeitados = pd.concat(rejeitados).drop(columns="_dia") if rejeitados else pd.DataFrame()
    serie_motivos = pd.concat(motivos) if motivos else pd.Series(dtype="object")
    gravar_quarentena_da_tabela(df_rejeitados, serie_motivos, "silver_selic", load_id,
                                "ipeadata", config.DIR_QUARENTENA)
    _gravar_parquet(silver, config.ARQUIVO_SILVER_SELIC)

    relatorio = ler_controle(config.ARQUIVO_RELATORIO_SILVER)
    relatorio["silver_selic"] = {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "_load_id": load_id,
        "serie": config.SELIC_SERIE,
        "unidade": config.SELIC_UNIDADE,
        "recorte": f"{inicio:%Y-%m} a {fim:%Y-%m}",
        **{k: int(v) for k, v in contagem.items()},
        "quarentena_por_motivo": {k: int(v) for k, v in serie_motivos.value_counts().items()},
        "linhas_silver": len(silver),
    }
    gravar_controle(config.ARQUIVO_RELATORIO_SILVER, relatorio)

    logger.info(f"silver_selic: {len(silver)} meses ({config.SELIC_SERIE}, {config.SELIC_UNIDADE}), "
                f"quarentena {relatorio['silver_selic']['quarentena_por_motivo']}.")
    return silver
