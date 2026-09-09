import sys
from pathlib import Path
import datetime
import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.quality_checks import (
    checar_uf,
    checar_data_no_intervalo,
    checar_valor_nao_negativo,
    checar_tipagem,
    enviar_para_quarentena
)

class DummyConfig:
    UFS_VALIDAS = ['SP', 'RJ', 'MG']
    ANO_INICIO = 2020
    MES_INICIO = 1

def test_checar_uf():
    config = DummyConfig()
    assert checar_uf('SP', config) is None
    assert checar_uf('BA', config) == 'uf_invalida'

def test_checar_data_no_intervalo():
    config = DummyConfig()
    assert checar_data_no_intervalo('2021-05-01', config) is None
    assert checar_data_no_intervalo('2019-12-31', config) == 'data_fora_do_intervalo'
    assert checar_data_no_intervalo('2099-01-01', config) == 'data_fora_do_intervalo'

def test_checar_valor_nao_negativo():
    assert checar_valor_nao_negativo(10, 'valor') is None
    assert checar_valor_nao_negativo(-5, 'valor') == 'valor_negativo'
    assert checar_valor_nao_negativo(-1, 'numero_de_operacoes') is None
    assert checar_valor_nao_negativo(-5, 'numero_de_operacoes') == 'valor_negativo'

def test_checar_tipagem():
    assert checar_tipagem('123', 'int') is None
    assert checar_tipagem('abc', 'int') == 'tipagem_invalida'
    assert checar_tipagem('12.3', 'float') is None
    assert checar_tipagem('abc', 'float') == 'tipagem_invalida'
    assert checar_tipagem('2021-01-01', 'date') is None
    assert checar_tipagem('nao-data', 'date') == 'tipagem_invalida'

def test_enviar_para_quarentena(tmp_path):
    registro = {'id': 1, 'valor': 100}
    motivo = 'uf_invalida'
    
    enviar_para_quarentena(
        registro=registro,
        motivo=motivo,
        load_id='load_123',
        source_system='SYS',
        source_object='OBJ',
        dir_quarentena=str(tmp_path)
    )
    
    arquivos = list(tmp_path.glob("*.parquet"))
    assert len(arquivos) == 1
    
    df = pd.read_parquet(arquivos[0])
    assert len(df) == 1
    assert df.iloc[0]['_load_id'] == 'load_123'
    assert df.iloc[0]['motivo'] == motivo
    assert '{"id": 1, "valor": 100}' in df.iloc[0]['payload']
