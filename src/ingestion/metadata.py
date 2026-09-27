import hashlib
import json
import uuid
import datetime
import pandas as pd

def gerar_load_id() -> str:
    """Gera um UUID4 para identificar uma execução do pipeline."""
    return str(uuid.uuid4())

class _DateTimeEncoder(json.JSONEncoder):
    """Converte date/datetime para texto ISO na hora de gerar o JSON do hash."""
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)


# Um único codificador, criado uma vez só. Os parâmetros são os mesmos de
# json.dumps(registro, sort_keys=True, separators=(',', ':')), então o texto
# gerado — e portanto o hash — é idêntico ao de antes. Criar o codificador a
# cada linha custava segundos a mais por CSV.
_CODIFICADOR_JSON = _DateTimeEncoder(sort_keys=True, separators=(',', ':'))


def calcular_record_hash(registro: dict, source_object: str) -> str:
    """
    Calcula o hash SHA-256 do conteúdo do registro concatenado com o source_object.
    """
    registro_str = _CODIFICADOR_JSON.encode(registro)
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
    
    # O hash usa só as colunas que vieram da fonte (as de `df`, antes dos
    # metadados). Montamos o dicionário de cada linha a partir das colunas
    # convertidas em listas (Series.tolist() já devolve tipos nativos do
    # Python). É bem mais rápido que iterrows ou to_dict("records"), e o
    # dicionário — portanto o hash — é o mesmo.
    colunas = list(df.columns)
    valores_por_coluna = [df[coluna].tolist() for coluna in colunas]
    df_out['_record_hash'] = [
        calcular_record_hash(dict(zip(colunas, valores)), source_object)
        for valores in zip(*valores_por_coluna)
    ]
    return df_out
