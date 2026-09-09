import hashlib
import json
import uuid
import datetime
import pandas as pd

def gerar_load_id() -> str:
    """Gera um UUID4 para identificar uma execução do pipeline."""
    return str(uuid.uuid4())

def calcular_record_hash(registro: dict, source_object: str) -> str:
    """
    Calcula o hash SHA-256 do conteúdo do registro concatenado com o source_object.
    """
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, (datetime.datetime, datetime.date)):
                return obj.isoformat()
            return super().default(obj)

    registro_str = json.dumps(registro, sort_keys=True, separators=(',', ':'), cls=DateTimeEncoder)
    content = registro_str + source_object
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def anexar_metadados(df: pd.DataFrame, source_system: str, source_object: str, load_id: str, ingestion_mode: str = 'full') -> pd.DataFrame:
    """
    Adiciona colunas de metadados padrão da camada Bronze.
    """
    df_out = df.copy()
    
    now = datetime.datetime.now()
    today = datetime.date.today()
    
    df_out['_ingestion_timestamp'] = now
    df_out['_ingestion_date'] = today
    df_out['_source_system'] = source_system
    df_out['_source_object'] = source_object
    df_out['_load_id'] = load_id
    df_out['_ingestion_mode'] = ingestion_mode
    
    original_columns = df.columns
    hashes = []
    
    for _, row in df[original_columns].iterrows():
        row_dict = row.to_dict()
        hashes.append(calcular_record_hash(row_dict, source_object))
        
    df_out['_record_hash'] = hashes
    return df_out
