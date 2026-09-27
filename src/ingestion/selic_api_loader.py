"""
Módulo responsável por requisitar a série temporal da Selic do Ipeadata,
fazer o parse da resposta OData e salvar na camada Bronze, como veio.

A validação de negócio e a quarentena ficam na Silver (seção 3.3 do
docs/architecture.md).
"""

import logging
import time
from pathlib import Path
import requests
import pandas as pd
from typing import Optional, Dict, Any

from src import config
from src.ingestion.controle import ler_controle, gravar_controle
from src.ingestion.metadata import gerar_load_id, anexar_metadados

logger = logging.getLogger(__name__)

def requisitar_selic(url: Optional[str] = None, timeout: int = 30, max_tentativas: int = 3, base_espera: int = 2) -> Optional[Dict[str, Any]]:
    """
    Requisição resiliente à API do Ipeadata com tentativas (exponential backoff).
    """
    if url is None:
        url = config.SELIC_URL
        
    for tentativa in range(max_tentativas):
        try:
            logger.info(f"Requisitando URL: {url} - Tentativa {tentativa + 1}/{max_tentativas}")
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            logger.info("Requisição bem sucedida.")
            return response.json()
        except requests.RequestException as e:
            espera = base_espera * (2 ** tentativa)
            logger.error(f"Erro na requisição: {e}. Aguardando {espera}s para tentar novamente.")
            if tentativa < max_tentativas - 1:
                time.sleep(espera)
            else:
                logger.error("Todas as tentativas falharam.")
                return None
    return None

def parsear_resposta_selic(resposta_json: Any) -> Optional[pd.DataFrame]:
    """
    Transforma a resposta OData do Ipeadata em DataFrame para a Bronze.

    Regra da Bronze (seções 3.3 e 4.1 do architecture.md): o dado entra
    COMO VEIO.
    - Todos os campos de cada registro são mantidos (SERCODIGO, VALDATA,
      VALVALOR, NIVNOME, TERCODIGO...), convertidos para TEXTO. Tudo como
      texto evita que um valor nulo ou fora do formato misture tipos na mesma
      coluna e faça a gravação do Parquet falhar. str() de um número em Python
      é reversível: nenhuma casa decimal se perde.
    - Nulo do JSON continua nulo (não vira o texto "None").
    - Sem recorte de período: a série inteira é gravada. O recorte a partir
      de jul/2016, a conversão de tipos e as checagens de negócio (valor
      negativo, mês incompleto) são feitos na Silver.

    A única rejeição é ESTRUTURAL: se a resposta não tem a chave "value" do
    OData, não há o que ler. Nesse caso devolve None e registra em log.
    """
    if not isinstance(resposta_json, dict) or "value" not in resposta_json:
        logger.error("Resposta da API sem a chave 'value' do OData: não foi possível ler a série.")
        return None

    registros = [
        {campo: (None if valor is None else str(valor)) for campo, valor in registro.items()}
        for registro in resposta_json["value"]
    ]
    return pd.DataFrame(registros)


def _hashes_ja_gravados(saida):
    """
    Lê da bronze_selic só a coluna _record_hash (a tabela é pequena: ~600 linhas).
    O ignore_prefixes=["."] é obrigatório: a partição se chama "_ingestion_date=...".
    """
    if not Path(saida).exists():
        return set(), None
    bronze = pd.read_parquet(saida, columns=["_record_hash", "VALDATA"], ignore_prefixes=["."])
    datas = bronze["VALDATA"].dropna().str[:10]
    return set(bronze["_record_hash"]), (datas.max() if not datas.empty else None)


def carregar_selic() -> Optional[str]:
    """
    Ingestão INCREMENTAL da Selic na Bronze, por watermark (seção 3 do
    architecture.md).

    O watermark é a maior VALDATA já gravada (tabela de controle
    controle_selic.json). A API do Ipeadata ignora filtros ($filter, $top,
    $orderby — conferido em 2026-09-27), então a série inteira (~60 KB) é
    sempre baixada, mas só entra na Bronze o que falta:
    - registros com VALDATA >= watermark (o mês do watermark é reavaliado,
      porque o mês corrente muda de valor até fechar);
    - cujo _record_hash ainda não está na Bronze (mesmo valor = mesmo hash =
      nada a gravar; valor novo = hash novo = uma linha nova, e a antiga fica).

    A comparação de datas usa só "AAAA-MM-DD": o fuso da API alterna entre
    -02:00 e -03:00, e comparar o texto completo daria resultado errado.

    _ingestion_mode é "full" na primeira carga e "incremental" depois.
    Não valida regra de negócio nem usa a quarentena (isso é da Silver).
    Devolve o _load_id da execução.
    """
    load_id = gerar_load_id()
    saida = config.DIR_BRONZE / 'bronze_selic'

    try:
        resposta = requisitar_selic()
        if resposta is None:
            logger.error("Não foi possível obter dados da API.")
            return load_id

        df = parsear_resposta_selic(resposta)
        if df is None:
            return load_id
        if df.empty:
            logger.warning("A API respondeu, mas a série veio vazia. Nada foi gravado.")
            return load_id
        logger.info(f"{len(df)} registros recebidos da API.")

        controle = ler_controle(config.ARQUIVO_CONTROLE_SELIC)
        hashes_existentes, maior_data_na_bronze = _hashes_ja_gravados(saida)
        watermark = controle.get("watermark")
        if watermark is None and maior_data_na_bronze is not None:
            # Controle perdido, mas a Bronze existe: reconstrói o watermark.
            watermark = maior_data_na_bronze
            logger.warning(f"Watermark da Selic reconstruído a partir da Bronze: {watermark}.")

        modo = "full" if watermark is None else "incremental"
        datas = df["VALDATA"].fillna("").str[:10]
        candidatos = df if watermark is None else df[datas >= watermark]

        df_metadata = anexar_metadados(
            df=candidatos,
            source_system='ipeadata',
            source_object=config.SELIC_URL,
            load_id=load_id,
            ingestion_mode=modo
        )
        novos = df_metadata[~df_metadata["_record_hash"].isin(hashes_existentes)]

        if novos.empty:
            logger.info(f"Selic: nada novo (watermark {watermark}). Nenhuma linha gravada.")
        else:
            saida.mkdir(parents=True, exist_ok=True)
            novos.to_parquet(saida, partition_cols=['_ingestion_date'], index=False)
            logger.info(f"Selic: {len(novos)} linhas novas gravadas (modo {modo}).")

        # Watermark só avança DEPOIS que a gravação terminou.
        maior_data = datas[datas != ""].max()
        if maior_data:
            gravar_controle(config.ARQUIVO_CONTROLE_SELIC, {"watermark": maior_data})

        return load_id
    except Exception as e:
        logger.error(f"Erro inesperado em carregar_selic: {e}")
        return load_id
