import logging
import uuid
import json
import datetime
from typing import Optional, Any
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

def checar_uf(valor: Any, config: Any) -> Optional[str]:
    """Check if valor is in config.UFS_VALIDAS."""
    if valor not in config.UFS_VALIDAS:
        return 'uf_invalida'
    return None

def checar_data_no_intervalo(valor: Any, config: Any) -> Optional[str]:
    """Check if date valor is >= ANO_INICIO-MES_INICIO and <= today."""
    try:
        if isinstance(valor, str):
            try:
                data_obj = datetime.datetime.strptime(valor, '%Y-%m-%d').date()
            except ValueError:
                data_obj = datetime.datetime.strptime(valor, '%Y-%m').date()
        elif isinstance(valor, datetime.datetime):
            data_obj = valor.date()
        elif isinstance(valor, datetime.date):
            data_obj = valor
        else:
            return 'data_fora_do_intervalo'

        data_inicio = datetime.date(config.ANO_INICIO, config.MES_INICIO, 1)
        data_fim = datetime.date.today()

        if data_inicio <= data_obj <= data_fim:
            return None
        else:
            return 'data_fora_do_intervalo'
    except Exception:
        return 'data_fora_do_intervalo'

def checar_valor_nao_negativo(valor: Any, coluna: str) -> Optional[str]:
    """Check if numeric valor >= 0. Returns 'valor_negativo' or None."""
    try:
        v = float(valor)
        if coluna == 'numero_de_operacoes' and v == -1:
            return None
        if v < 0:
            return 'valor_negativo'
        return None
    except (ValueError, TypeError):
        return 'valor_negativo'

def checar_tipagem(valor: Any, tipo_esperado: str) -> Optional[str]:
    """Check if valor can be converted to tipo_esperado (int, float, or date)."""
    try:
        if tipo_esperado == 'int':
            int(valor)
        elif tipo_esperado == 'float':
            float(valor)
        elif tipo_esperado == 'date':
            if isinstance(valor, (datetime.date, datetime.datetime)):
                pass
            elif isinstance(valor, str):
                try:
                    datetime.datetime.strptime(valor, '%Y-%m-%d')
                except ValueError:
                    try:
                        datetime.datetime.strptime(valor, '%Y-%m')
                    except ValueError:
                        return 'tipagem_invalida'
            else:
                return 'tipagem_invalida'
        else:
            return 'tipagem_invalida'
        return None
    except (ValueError, TypeError):
        return 'tipagem_invalida'

def enviar_para_quarentena(registro: dict, motivo: str, load_id: str, source_system: str, source_object: str, dir_quarentena: str) -> None:
    """Writes rejected record to Parquet in dir_quarentena."""
    try:
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (datetime.datetime, datetime.date)):
                    return obj.isoformat()
                return super().default(obj)
                
        payload = json.dumps(registro, cls=DateTimeEncoder)
        quarantined_at = datetime.datetime.now()
        
        df = pd.DataFrame([{
            '_load_id': load_id,
            '_source_system': source_system,
            '_source_object': source_object,
            'motivo': motivo,
            'payload': payload,
            'quarantined_at': quarantined_at
        }])
        
        path = Path(dir_quarentena)
        path.mkdir(parents=True, exist_ok=True)
        
        filename = f"{uuid.uuid4()}.parquet"
        filepath = path / filename
        
        df.to_parquet(filepath, index=False)
    except Exception as e:
        logger.error(f"Erro ao enviar para quarentena: {e}")
