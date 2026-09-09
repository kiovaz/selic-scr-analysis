import os
import zipfile
import logging
import tempfile
import pandas as pd
import requests
from pathlib import Path

from src import config
from src.validation.quality_checks import (
    checar_uf,
    checar_data_no_intervalo,
    checar_valor_nao_negativo,
    checar_tipagem,
    enviar_para_quarentena
)
from src.ingestion.metadata import gerar_load_id, anexar_metadados

logger = logging.getLogger(__name__)

def baixar_zips(dir_download, anos=None, forcar_redownload=False):
    """
    Downloads ZIP for each year from ANO_INICIO to ANO_FIM (or anos list if provided).
    Saves to dir_download directory.
    If ZIP already exists locally, reuses it (unless forcar_redownload=True).
    HTTP errors for one year are logged and don't prevent others.
    Returns list of downloaded/existing ZIP paths.
    """
    if anos is None:
        anos = range(config.ANO_INICIO, config.ANO_FIM + 1)
        
    dir_download = Path(dir_download)
    dir_download.mkdir(parents=True, exist_ok=True)
    
    zip_paths = []
    
    for ano in anos:
        url = config.SCR_URL_TEMPLATE.format(ano=ano)
        zip_filename = f"scr_{ano}.zip"
        zip_path = dir_download / zip_filename
        
        if zip_path.exists() and not forcar_redownload:
            logger.info(f"O arquivo {zip_path} já existe. Utilizando o arquivo local.")
            zip_paths.append(zip_path)
            continue
            
        logger.info(f"Baixando ZIP para o ano {ano} de {url}...")
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            zip_paths.append(zip_path)
            logger.info(f"Download concluído: {zip_path}")
        except Exception as e:
            logger.error(f"Erro ao baixar os dados do ano {ano} ({url}): {e}")
            
    return zip_paths

def ler_csvs_do_zip(zip_path):
    """
    Extracts CSV files from ZIP.
    For each CSV, tries encodings from SCR_ENCODINGS_CANDIDATOS in order.
    Uses SCR_SEPARADOR as separator.
    Checks header of each CSV against SCR_COLUNAS_USADAS - if any expected column is missing, rejects the CSV with log and continues to next.
    Returns list of (csv_name, DataFrame) tuples.
    """
    resultados = []
    temp_dir = tempfile.mkdtemp()
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
            
            for csv_file in csv_files:
                extracted_path = zip_ref.extract(csv_file, temp_dir)
                df = None
                
                for enc in config.SCR_ENCODINGS_CANDIDATOS:
                    try:
                        temp_df = pd.read_csv(
                            extracted_path, 
                            sep=config.SCR_SEPARADOR, 
                            encoding=enc, 
                            decimal=',', 
                            low_memory=False
                        )
                        df = temp_df
                        logger.info(f"Arquivo {csv_file} lido com sucesso usando o encoding {enc}.")
                        break
                    except Exception as e:
                        logger.debug(f"Falha ao ler {csv_file} com encoding {enc}: {e}")
                
                if df is None:
                    logger.error(f"Não foi possível ler {csv_file} com nenhum dos encodings candidatos.")
                    continue
                
                colunas_csv = set(df.columns)
                colunas_esperadas = set(config.SCR_COLUNAS_USADAS)
                
                if not colunas_esperadas.issubset(colunas_csv):
                    colunas_faltantes = colunas_esperadas - colunas_csv
                    logger.warning(f"O CSV {csv_file} foi rejeitado por faltar as colunas: {colunas_faltantes}")
                    continue
                
                df_filtrado = df[config.SCR_COLUNAS_USADAS].copy()
                resultados.append((csv_file, df_filtrado))
                
    except Exception as e:
        logger.error(f"Erro ao processar o arquivo ZIP {zip_path}: {e}")
        
    return resultados

def validar_registro(row, config):
    """Validates a single record using rules from quality_checks.
    Returns the standardized motivo string on failure, or None if valid."""
    motivo = checar_uf(row['uf'], config)
    if motivo:
        return motivo
    motivo = checar_data_no_intervalo(row['data_base'], config)
    if motivo:
        return motivo
    motivo = checar_tipagem(row['carteira_ativa'], 'float')
    if motivo:
        return motivo
    motivo = checar_valor_nao_negativo(row['carteira_ativa'], 'carteira_ativa')
    if motivo:
        return motivo
    return None

def carregar_scr(dir_download=None, forcar_redownload=False):
    """
    Main entry point for SCR data ingestion.
    """
    load_id = gerar_load_id()
    
    if dir_download is None:
        dir_download = config.RAIZ / 'data' / 'downloads'
        
    zip_paths = baixar_zips(dir_download, forcar_redownload=forcar_redownload)
    
    for zip_path in zip_paths:
        csv_dfs = ler_csvs_do_zip(zip_path)
        
        for csv_name, df in csv_dfs:
            valid_indices = []
            
            try:
                # Row-by-row check for quarantine routing
                for index, row in df.iterrows():
                    motivo = validar_registro(row, config)
                    
                    if motivo:
                        enviar_para_quarentena(
                            registro=row.to_dict(),
                            motivo=motivo,
                            load_id=load_id,
                            source_system='scr_data',
                            source_object=csv_name,
                            dir_quarentena=config.DIR_QUARENTENA
                        )
                    else:
                        valid_indices.append(index)
                        
                df_validos = df.loc[valid_indices].copy()
                
                if not df_validos.empty:
                    df_validos_com_metadados = anexar_metadados(
                        df_validos, 
                        source_system='scr_data', 
                        source_object=csv_name, 
                        load_id=load_id
                    )
                    
                    output_path = config.DIR_BRONZE / 'bronze_scr'
                    
                    df_validos_com_metadados.to_parquet(
                        output_path, 
                        partition_cols=['_ingestion_date'],
                        engine='pyarrow',
                        index=False
                    )
                    logger.info(f"Dados do arquivo {csv_name} gravados na tabela bronze com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao processar dados do arquivo {csv_name}: {e}")
                
    return load_id
