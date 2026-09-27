"""
Módulo responsável por requisitar a série temporal da Selic do Ipeadata,
fazer o parse da resposta OData e salvar na camada Bronze, como veio.

A validação de negócio e a quarentena ficam na Silver (seção 3.3 do
docs/architecture.md).
"""

import logging
import time
import requests
import pandas as pd
from typing import Optional, Dict, Any

from src import config
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


def carregar_selic() -> Optional[str]:
    """
    Orquestra a ingestão da Selic na Bronze: requisita a API, monta o
    DataFrame como veio, anexa os metadados técnicos e grava em
    data/raw/bronze_selic/, particionado por _ingestion_date.

    Não valida regra de negócio nem usa a quarentena (isso é da Silver).
    Devolve o _load_id da execução.
    """
    load_id = gerar_load_id()

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

        df_metadata = anexar_metadados(
            df=df,
            source_system='ipeadata',
            source_object=config.SELIC_URL,
            load_id=load_id,
            ingestion_mode='full'
        )

        output_dir = config.DIR_BRONZE / 'bronze_selic'
        output_dir.mkdir(parents=True, exist_ok=True)

        df_metadata.to_parquet(
            output_dir,
            partition_cols=['_ingestion_date'],
            index=False
        )

        return load_id
    except Exception as e:
        logger.error(f"Erro inesperado em carregar_selic: {e}")
        return load_id
