"""
Módulo responsável por requisitar a série temporal da Selic do Ipeadata,
fazer o parse da resposta OData, validar os registros e salvar na camada Bronze.
"""

import datetime
import logging
import time
import requests
import pandas as pd
from typing import Optional, Tuple, List, Dict, Any

from src import config
from src.validation.quality_checks import (
    checar_data_no_intervalo,
    checar_valor_nao_negativo,
    checar_tipagem,
    enviar_para_quarentena
)
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

def parsear_resposta_selic(resposta_json: Dict[str, Any], config_module: Any) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Extrai VALDATA e VALVALOR do JSON retornado pela API.
    Aplica filtro de data e separa os registros malformados.
    """
    validos = []
    invalidos = []
    
    if "value" not in resposta_json:
        return pd.DataFrame(columns=['VALDATA', 'VALVALOR']), []
        
    cutoff_date = datetime.date(config_module.ANO_INICIO, config_module.MES_INICIO, 1)
    
    for record in resposta_json["value"]:
        valdata_raw = record.get("VALDATA")
        valvalor_raw = record.get("VALVALOR")
        
        malformed = False
        
        # Tentar converter VALVALOR
        try:
            valvalor_float = float(valvalor_raw)
        except (ValueError, TypeError):
            malformed = True
            
        # Tentar converter VALDATA
        try:
            valdata_dt = pd.to_datetime(valdata_raw).date()
        except Exception:
            malformed = True
            
        if malformed:
            invalidos.append(record)
            continue
            
        # Aplicar corte temporal
        if valdata_dt >= cutoff_date:
            validos.append({
                'VALDATA': valdata_dt,
                'VALVALOR': valvalor_float
            })
            
    df_validos = pd.DataFrame(validos)
    if not df_validos.empty:
        df_validos = df_validos[['VALDATA', 'VALVALOR']]
    else:
        df_validos = pd.DataFrame(columns=['VALDATA', 'VALVALOR'])
        
    return df_validos, invalidos

def carregar_selic() -> Optional[str]:
    """
    Orquestra a extração, validação e gravação da carga Bronze da Selic.
    """
    load_id = gerar_load_id()
    
    try:
        resposta = requisitar_selic()
        if resposta is None:
            logger.error("Não foi possível obter dados da API.")
            return load_id
            
        df_validos, invalidos = parsear_resposta_selic(resposta, config)
        
        # Enviar registros malformados no parse para quarentena
        for reg in invalidos:
            enviar_para_quarentena(
                registro=reg,
                motivo='tipagem_invalida',
                load_id=load_id,
                source_system='ipeadata',
                source_object=config.SELIC_URL,
                dir_quarentena=str(config.DIR_QUARENTENA)
            )
            
        # Validações sobre os registros tipados
        linhas_validas = []
        
        for _, row in df_validos.iterrows():
            reg_dict = row.to_dict()
            motivo = None
            
            # Checar tipagem VALVALOR (já garantido pelo parse, mas a task exige)
            erro_tipo = checar_tipagem(row['VALVALOR'], 'float')
            if erro_tipo:
                motivo = erro_tipo
            
            # Checar não negativo VALVALOR
            if not motivo:
                erro_neg = checar_valor_nao_negativo(row['VALVALOR'], 'VALVALOR')
                if erro_neg:
                    motivo = erro_neg
                    
            # Checar data no intervalo VALDATA
            if not motivo:
                erro_data = checar_data_no_intervalo(row['VALDATA'], config)
                if erro_data:
                    motivo = erro_data
                    
            if motivo:
                # Converter data para string para não quebrar o json.dumps na quarentena
                if isinstance(reg_dict.get('VALDATA'), datetime.date):
                    reg_dict['VALDATA'] = reg_dict['VALDATA'].isoformat()
                    
                enviar_para_quarentena(
                    registro=reg_dict,
                    motivo=motivo,
                    load_id=load_id,
                    source_system='ipeadata',
                    source_object=config.SELIC_URL,
                    dir_quarentena=str(config.DIR_QUARENTENA)
                )
            else:
                linhas_validas.append(reg_dict)
                
        df_final = pd.DataFrame(linhas_validas)
        
        if not df_final.empty:
            df_metadata = anexar_metadados(
                df=df_final,
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
