import sys
from pathlib import Path
import pytest
import pandas as pd
import uuid

# Setup import path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.metadata import gerar_load_id, calcular_record_hash, anexar_metadados

def test_hash_different_source_object():
    record = {"a": 1, "b": 2}
    hash1 = calcular_record_hash(record, "file1.csv")
    hash2 = calcular_record_hash(record, "file2.csv")
    assert hash1 != hash2

def test_hash_same_source_object():
    record1 = {"a": 1, "b": 2}
    record2 = {"a": 1, "b": 2}
    hash1 = calcular_record_hash(record1, "file1.csv")
    hash2 = calcular_record_hash(record2, "file1.csv")
    assert hash1 == hash2
    
def test_anexar_metadados():
    df = pd.DataFrame([{"col1": "A", "col2": 10}, {"col1": "B", "col2": 20}])
    load_id = gerar_load_id()
    df_meta = anexar_metadados(
        df,
        source_system="test_sys",
        source_object="test_obj.csv",
        load_id=load_id,
        ingestion_mode="delta"
    )
    
    expected_cols = [
        "_ingestion_timestamp", "_ingestion_date", "_source_system",
        "_source_object", "_load_id", "_ingestion_mode", "_record_hash"
    ]
    for col in expected_cols:
        assert col in df_meta.columns
        
    # Check _record_hash is 64-char hex string
    for hash_val in df_meta["_record_hash"]:
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
        int(hash_val, 16)
        
    assert df_meta["_load_id"].iloc[0] == load_id
    
def test_gerar_load_id():
    load_id = gerar_load_id()
    assert isinstance(load_id, str)
    # Validate UUID4
    val = uuid.UUID(load_id, version=4)
    assert str(val) == load_id
