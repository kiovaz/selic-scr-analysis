"""
Constrói a silver_scr a partir da bronze_scr (seções 3.3, 4.1 e 5.1 do
docs/architecture.md).

Uma linha por (ano_mes, uf, modalidade), só com:
- a VERSÃO MAIS RECENTE de cada CSV (o BCB republica meses; seção 3.2);
- as 8 modalidades de financiamento (PREFIXO_MODALIDADE);
- o recorte jul/2016 a jun/2026 (ANO_INICIO/MES_INICIO a ANO_FIM/MES_FIM).

O que está fora do escopo (versão antiga, outra modalidade, fora do recorte)
é FILTRADO e CONTADO no relatório — não é dado errado, é dado que o projeto
não usa. O que é INVÁLIDO (UF errada, número que não é número, valor
negativo, data futura) vai para a QUARENTENA com o motivo padronizado.

Agregação de cada grupo:
- volume_rs = soma do saldo (carteira_ativa) — completo, indicador principal;
- qtd_operacoes = soma SÓ das quantidades divulgadas. O BCB esconde a
  quantidade de algumas linhas com -1; elas não entram na soma, então
  qtd_operacoes é um LIMITE INFERIOR (decisão do grupo, seção 5.1);
- linhas_qtd_nao_divulgada = quantas linhas do grupo tinham -1.

Meses sem nenhuma linha numa combinação UF × modalidade NÃO são preenchidos:
o relatório lista essas combinações para a Gold.

A Silver é reconstruída inteira a cada execução, sem consultar a fonte.
Como rodar: faz parte de scripts/run_pipeline.py.
"""

import datetime
import logging
from collections import Counter
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds

from src import config
from src.ingestion.controle import ler_controle, gravar_controle
from src.ingestion.metadata import gerar_load_id
from src.validation.quality_checks import (
    converter_data,
    converter_numero,
    gravar_quarentena_da_tabela,
    mascara_data_futura,
    mascara_tipagem_invalida,
    mascara_uf_invalida,
    mascara_valor_negativo,
)

logger = logging.getLogger(__name__)

CHAVE = ["ano_mes", "uf", "modalidade"]
COLUNAS_LIDAS = ["_source_object"] + config.SCR_COLUNAS_USADAS


def inicio_e_fim_do_recorte():
    """Primeiro e último mês do recorte, como o primeiro dia de cada mês."""
    inicio = pd.Timestamp(config.ANO_INICIO, config.MES_INICIO, 1)
    fim = pd.Timestamp(config.ANO_FIM, config.MES_FIM, 1)
    return inicio, fim


def meses_do_recorte():
    """Quantos meses o recorte tem (hoje, 120)."""
    inicio, fim = inicio_e_fim_do_recorte()
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month) + 1


def abrir_bronze_scr():
    """Abre a bronze_scr (ignore_prefixes: a partição começa com "_")."""
    caminho = config.DIR_BRONZE / "bronze_scr"
    if not caminho.exists():
        return None
    return ds.dataset(caminho, format="parquet", partitioning="hive", ignore_prefixes=["."])


def versoes_vigentes(dataset):
    """
    Para cada arquivo do SCR (parte do _source_object antes do "@"), a versão
    mais recente presente na Bronze. A versão é "nome@AAAA-MM-DDTHH:MM:SS",
    então comparar o texto inteiro dá a ordem certa das datas.
    """
    todas = dataset.to_table(columns=["_source_object"]).column("_source_object").unique().to_pylist()
    mais_recente = {}
    for versao in todas:
        arquivo = versao.split("@")[0]
        if arquivo not in mais_recente or versao > mais_recente[arquivo]:
            mais_recente[arquivo] = versao
    return set(mais_recente.values())


def classificar_linhas(df):
    """
    Motivo de quarentena de cada linha (None = válida). Cada linha fica com o
    PRIMEIRO motivo, na ordem: uf_invalida, tipagem_invalida,
    data_fora_do_intervalo, valor_negativo. O -1 de numero_de_operacoes é a
    máscara do BCB e NÃO é valor negativo.
    """
    datas = converter_data(df["data_base"])
    saldo = converter_numero(df["carteira_ativa"], config.SCR_DECIMAL)
    quantidade = converter_numero(df["numero_de_operacoes"])

    tipagem = (
        datas.isna()
        | mascara_tipagem_invalida(df["carteira_ativa"], "float", config.SCR_DECIMAL)
        | mascara_tipagem_invalida(df["numero_de_operacoes"], "int")
    )
    regras = [
        ("uf_invalida", mascara_uf_invalida(df["uf"], config)),
        ("tipagem_invalida", tipagem),
        ("data_fora_do_intervalo", mascara_data_futura(datas)),
        ("valor_negativo", mascara_valor_negativo(saldo, "carteira_ativa")
                           | mascara_valor_negativo(quantidade, "numero_de_operacoes")),
    ]
    motivo = pd.Series(None, index=df.index, dtype="object")
    for nome, mascara in regras:
        motivo = motivo.mask(motivo.isna() & mascara, nome)
    return motivo


def agregar(df):
    """
    Soma cada grupo (ano_mes, uf, modalidade). Linhas com quantidade -1 (não
    divulgada) entram no volume, mas não na quantidade: qtd_operacoes é o
    total divulgado (limite inferior) e linhas_qtd_nao_divulgada conta quantas
    linhas estavam escondidas.
    """
    quantidade = converter_numero(df["numero_de_operacoes"]).astype("int64")
    tabela = pd.DataFrame({
        "ano_mes": converter_data(df["data_base"]).dt.to_period("M").dt.to_timestamp(),
        "uf": df["uf"],
        "modalidade": df["modalidade"],
        "qtd_operacoes": quantidade.where(quantidade >= 0, 0),
        "linhas_qtd_nao_divulgada": (quantidade == -1).astype("int64"),
        "volume_rs": converter_numero(df["carteira_ativa"], config.SCR_DECIMAL),
    })
    return tabela.groupby(CHAVE, as_index=False)[
        ["qtd_operacoes", "linhas_qtd_nao_divulgada", "volume_rs"]].sum()


def _gravar_parquet(df, destino):
    """Grava de forma atômica: .tmp primeiro, depois renomeia."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".tmp")
    df.to_parquet(temporario, index=False)
    temporario.replace(destino)


def combinacoes_incompletas(silver):
    """Combinações UF × modalidade que não têm todos os meses do recorte."""
    total = meses_do_recorte()
    meses = silver.groupby(["uf", "modalidade"]).size()
    incompletas = meses[meses < total].sort_values()
    return [{"uf": uf, "modalidade": mod, "meses_presentes": int(n)}
            for (uf, mod), n in incompletas.items()]


def construir_silver_scr():
    """
    Lê a bronze_scr arquivo por arquivo (sem carregar os 34 milhões de linhas
    de uma vez), aplica versão vigente, escopo, validação e agregação, e grava
    a silver_scr, a quarentena da tabela e a parte do relatório.
    Devolve a silver_scr (DataFrame) ou None se a Bronze não existir.
    """
    load_id = gerar_load_id()
    dataset = abrir_bronze_scr()
    if dataset is None:
        logger.error("bronze_scr não existe. Rode a ingestão antes da Silver.")
        return None

    contagem = Counter()
    vigentes = pa.array(sorted(versoes_vigentes(dataset)))
    inicio, fim = inicio_e_fim_do_recorte()
    partes, rejeitados, motivos = [], [], []

    for fragmento in dataset.get_fragments():
        tabela = fragmento.to_table(columns=COLUNAS_LIDAS)
        contagem["lidas_da_bronze"] += tabela.num_rows

        # 1. Só a versão mais recente de cada CSV.
        vigente = pc.is_in(tabela.column("_source_object"), value_set=vigentes)
        manter = tabela.filter(vigente)
        contagem["descartadas_versao_antiga"] += tabela.num_rows - manter.num_rows

        # 2. Só as modalidades de financiamento (filtro no pyarrow, antes do pandas).
        financiamento = pc.starts_with(manter.column("modalidade"), config.PREFIXO_MODALIDADE)
        tabela_fin = manter.filter(financiamento)
        contagem["descartadas_modalidade_fora_do_escopo"] += manter.num_rows - tabela_fin.num_rows
        if tabela_fin.num_rows == 0:
            continue
        df = tabela_fin.to_pandas()

        # 3. Só o recorte. Data inválida não é "fora do recorte": segue para a validação.
        mes = converter_data(df["data_base"]).dt.to_period("M").dt.to_timestamp()
        fora = mes.notna() & ((mes < inicio) | (mes > fim))
        contagem["descartadas_fora_do_recorte"] += int(fora.sum())
        df = df[~fora]

        # 4. Validação: inválidos vão para a quarentena e não entram na soma.
        motivo = classificar_linhas(df)
        invalidos = motivo.notna()
        if invalidos.any():
            rejeitados.append(df[invalidos])
            motivos.append(motivo[invalidos])
        validos = df[~invalidos]
        contagem["linhas_validas_agregadas"] += len(validos)

        # 5. Agregação parcial deste arquivo (somada de novo no final).
        if len(validos):
            partes.append(agregar(validos))

    if partes:
        silver = pd.concat(partes).groupby(CHAVE, as_index=False)[
            ["qtd_operacoes", "linhas_qtd_nao_divulgada", "volume_rs"]].sum()
    else:
        silver = pd.DataFrame(columns=CHAVE + ["qtd_operacoes", "linhas_qtd_nao_divulgada", "volume_rs"])
    silver["ano_mes"] = pd.to_datetime(silver["ano_mes"]).dt.date
    silver = silver.sort_values(CHAVE).reset_index(drop=True)
    silver["_load_id"] = load_id

    # Quarentena da tabela: substitui a da execução anterior (mesmo vazia).
    df_rejeitados = pd.concat(rejeitados) if rejeitados else pd.DataFrame(columns=COLUNAS_LIDAS)
    serie_motivos = pd.concat(motivos) if motivos else pd.Series(dtype="object")
    gravar_quarentena_da_tabela(df_rejeitados, serie_motivos, "silver_scr", load_id,
                                "scr_data", config.DIR_QUARENTENA)

    _gravar_parquet(silver, config.ARQUIVO_SILVER_SCR)

    relatorio = ler_controle(config.ARQUIVO_RELATORIO_SILVER)
    relatorio["silver_scr"] = {
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "_load_id": load_id,
        "recorte": f"{inicio:%Y-%m} a {fim:%Y-%m}",
        **{k: int(v) for k, v in contagem.items()},
        "quarentena_por_motivo": {k: int(v) for k, v in serie_motivos.value_counts().items()},
        "linhas_silver": len(silver),
        "meses": int(silver["ano_mes"].nunique()),
        "modalidades": sorted(silver["modalidade"].unique().tolist()),
        "combinacoes_incompletas": combinacoes_incompletas(silver),
    }
    gravar_controle(config.ARQUIVO_RELATORIO_SILVER, relatorio)

    logger.info(f"silver_scr: {len(silver)} linhas, {relatorio['silver_scr']['meses']} meses, "
                f"quarentena {relatorio['silver_scr']['quarentena_por_motivo']}.")
    return silver
