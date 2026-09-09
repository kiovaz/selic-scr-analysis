import sys
import os
import uuid
import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import zipfile
import pytest
from unittest.mock import patch, Mock

import src.config as config
from src.ingestion.scr_file_loader import ler_csvs_do_zip, validar_registro
from src.ingestion.selic_api_loader import parsear_resposta_selic, carregar_selic
from src.ingestion.metadata import gerar_load_id, anexar_metadados
from src.validation.quality_checks import enviar_para_quarentena

def _criar_csv_teste(tmp_path, rows, filename='scrdata_202401.csv'):
    csv_path = tmp_path / filename
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, sep=config.SCR_SEPARADOR, index=False, decimal=',')
    return csv_path

def _criar_zip_teste(tmp_path, rows, zip_name='dados_202401.zip'):
    csv_path = _criar_csv_teste(tmp_path, rows)
    zip_path = tmp_path / zip_name
    with zipfile.ZipFile(zip_path, 'w') as z:
        z.write(csv_path, arcname=csv_path.name)
    return zip_path

# Task 5.1 - 1. SCR loader test with synthetic data
def test_scr_loader_synthetic(tmp_path):
    rows = [
        {'data_base': '2024-01-31', 'uf': 'SP', 'modalidade': 'VCO', 'numero_de_operacoes': 100, 'carteira_ativa': '1000.50'},
        {'data_base': '2024-01-31', 'uf': 'RJ', 'modalidade': 'VCO', 'numero_de_operacoes': 50, 'carteira_ativa': '500.00'}
    ]
    zip_path = _criar_zip_teste(tmp_path, rows)
    
    # test ler_csvs_do_zip
    dfs = ler_csvs_do_zip(zip_path)
    assert len(dfs) == 1
    df = dfs[0][1] # Extract the DataFrame part from the (csv_name, DataFrame) tuple
    assert len(df) == 2
    
    # manual validation
    valid_rows = []
    for idx, row in df.iterrows():
        motivo = validar_registro(row, config)
        if not motivo:
            valid_rows.append(row)
            
    df_valid = pd.DataFrame(valid_rows)
    assert len(df_valid) == 2
    
    # metadata
    load_id = gerar_load_id()
    df_meta = anexar_metadados(df_valid, source_system='SCR', source_object=zip_path.name, load_id=load_id)
    
    # verify 7 metadata columns are present
    meta_cols = ['_load_id', '_ingestion_timestamp', '_ingestion_date', '_source_system', '_source_object', '_ingestion_mode', '_record_hash']
    for col in meta_cols:
        assert col in df_meta.columns

# Task 5.1 - 2. Selic API test
def test_selic_api_loader():
    fake_json = {
        'value': [
            {'VALDATA': '2024-01-01T00:00:00Z', 'VALVALOR': 10.5},
            {'VALDATA': '2024-01-02T00:00:00Z', 'VALVALOR': 10.5}
        ]
    }
    
    with patch('src.ingestion.selic_api_loader.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = fake_json
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test parsear_resposta_selic
        df_validos, invalidos = parsear_resposta_selic(fake_json, config)
        
        assert len(df_validos) == 2
        assert len(invalidos) == 0
        assert isinstance(df_validos, pd.DataFrame)
        assert len(df_validos.columns) >= 2

# Task 5.1 - 3. Dirty record quarantine test (SCR)
def test_scr_dirty_quarantine(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DIR_QUARENTENA', tmp_path / '_quarentena')
    config.DIR_QUARENTENA.mkdir(parents=True, exist_ok=True)
    
    rows = [
        {'data_base': '2024-01-31', 'uf': 'SP', 'modalidade': 'VCO', 'numero_de_operacoes': 100, 'carteira_ativa': '1000.50'},
        {'data_base': '2024-01-31', 'uf': 'XX', 'modalidade': 'VCO', 'numero_de_operacoes': 50, 'carteira_ativa': '500.00'} # invalid UF
    ]
    df = pd.DataFrame(rows)
    
    valid_rows = []
    invalid_rows = []
    for idx, row in df.iterrows():
        motivo = validar_registro(row, config)
        if motivo:
            invalid_rows.append((row, motivo))
        else:
            valid_rows.append(row)
            
    assert len(valid_rows) == 1
    assert len(invalid_rows) == 1
    
    load_id = gerar_load_id()
    for row, motivo in invalid_rows:
        enviar_para_quarentena(row.to_dict(), motivo, load_id, 'SCR', 'test.csv', str(config.DIR_QUARENTENA))
    
    # check quarantine dir
    q_files = list(config.DIR_QUARENTENA.glob('*.parquet'))
    assert len(q_files) == 1

# Task 5.1 - 4. Dirty record quarantine test (Selic)
def test_selic_dirty_quarantine(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DIR_QUARENTENA', tmp_path / '_quarentena')
    config.DIR_QUARENTENA.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, 'DIR_BRONZE', tmp_path / 'bronze')
    
    # We will mock requests.get to return a negative VALVALOR.
    fake_json = {
        'value': [
            {'VALDATA': '2024-01-01T00:00:00Z', 'VALVALOR': 10.5},
            {'VALDATA': '2024-01-02T00:00:00Z', 'VALVALOR': -5.0} # invalid valor (negative)
        ]
    }
    
    with patch('src.ingestion.selic_api_loader.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = fake_json
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Test carregar_selic which handles the quarantine writing for Selic
        carregar_selic()
    
    # check quarantine dir
    q_files = list(config.DIR_QUARENTENA.glob('*.parquet'))
    assert len(q_files) >= 1
    
    # And we should have 1 file in bronze
    b_files = list((config.DIR_BRONZE / 'bronze_selic').glob('**/*.parquet'))
    assert len(b_files) >= 1

# Task 5.1 - 5. load_id consistency test
def test_load_id_consistency():
    load_id_1 = gerar_load_id()
    load_id_2 = gerar_load_id()
    
    assert isinstance(load_id_1, str)
    assert len(load_id_1) > 0
    # Must be valid UUID
    uuid_obj = uuid.UUID(load_id_1)
    assert str(uuid_obj) == load_id_1
    
    assert load_id_1 != load_id_2

# Task 5.2 - Definition of done test
def test_definicao_de_pronto_sprint2(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DIR_BRONZE', tmp_path / 'raw')
    monkeypatch.setattr(config, 'DIR_QUARENTENA', tmp_path / 'raw' / '_quarentena')
    
    dir_scr = config.DIR_BRONZE / 'bronze_scr'
    dir_selic = config.DIR_BRONZE / 'bronze_selic'
    dir_scr.mkdir(parents=True, exist_ok=True)
    dir_selic.mkdir(parents=True, exist_ok=True)
    config.DIR_QUARENTENA.mkdir(parents=True, exist_ok=True)
    
    # SCR data
    rows_scr = [
        {'data_base': '2024-01-31', 'uf': 'SP', 'modalidade': 'VCO', 'numero_de_operacoes': 10, 'carteira_ativa': '100'},
        {'data_base': '2024-01-31', 'uf': 'XX', 'modalidade': 'VCO', 'numero_de_operacoes': 5, 'carteira_ativa': '50'}
    ]
    zip_path = _criar_zip_teste(tmp_path, rows_scr)
    
    dfs_scr = ler_csvs_do_zip(zip_path)
    df_scr = dfs_scr[0][1]
    
    load_id_scr = gerar_load_id()
    
    valid_rows = []
    for idx, row in df_scr.iterrows():
        motivo = validar_registro(row, config)
        if motivo:
            enviar_para_quarentena(row.to_dict(), motivo, load_id_scr, 'SCR', zip_path.name, str(config.DIR_QUARENTENA))
        else:
            valid_rows.append(row)
            
    df_scr_v = pd.DataFrame(valid_rows)
    df_scr_v = anexar_metadados(df_scr_v, 'SCR', zip_path.name, load_id_scr)
    df_scr_v.to_parquet(dir_scr / f"scr_{load_id_scr}.parquet", index=False)
    
    # Selic data via mock
    fake_json = {
        'value': [
            {'VALDATA': '2024-01-01T00:00:00Z', 'VALVALOR': 10.5},
            {'VALDATA': '2024-01-02T00:00:00Z', 'VALVALOR': -5.0} # will go to quarantine
        ]
    }
    
    with patch('src.ingestion.selic_api_loader.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = fake_json
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        carregar_selic()
    
    # Verify
    assert len(list(dir_scr.glob('*.parquet'))) == 1
    # Note: carregar_selic uses partition_cols=['_ingestion_date'] so it's a directory structure
    assert len(list(dir_selic.glob('**/*.parquet'))) >= 1 
    
    # One invalid SCR + one invalid Selic = 2 files in quarantine
    assert len(list(config.DIR_QUARENTENA.glob('*.parquet'))) == 2
    
    # Valid output should have metadata
    scr_out = pd.read_parquet(list(dir_scr.glob('*.parquet'))[0])
    assert '_load_id' in scr_out.columns
    assert len(scr_out) == 1
    
    selic_out = pd.read_parquet(list(dir_selic.glob('**/*.parquet'))[0])
    assert '_load_id' in selic_out.columns
    assert len(selic_out) == 1
