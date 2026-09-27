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


# ---------------------------------------------------------------------
# Checagens aplicadas a uma COLUNA inteira (usadas pela Silver)
#
# Seguem exatamente as regras das funções checar_* acima, mas avaliam
# milhões de linhas de uma vez (validar linha a linha seria inviável na
# Silver). Cada uma devolve uma Series de True/False: True = a linha falhou.
# ---------------------------------------------------------------------

def mascara_uf_invalida(serie: pd.Series, config: Any) -> pd.Series:
    """True onde a UF não está em config.UFS_VALIDAS (mesma regra de checar_uf)."""
    return ~serie.isin(config.UFS_VALIDAS)


def converter_numero(serie: pd.Series, decimal: str = ".") -> pd.Series:
    """
    Converte texto em número. `decimal` é o separador decimal da fonte
    (o SCR usa vírgula: "1234,56"). O que não for número vira NaN.
    """
    texto = serie.astype("string")
    if decimal != ".":
        texto = texto.str.replace(decimal, ".", regex=False)
    return pd.to_numeric(texto, errors="coerce").astype("float64")


def converter_data(serie: pd.Series) -> pd.Series:
    """Converte texto AAAA-MM-DD (ou AAAA-MM) em data. O que não for data vira NaT."""
    texto = serie.astype("string")
    datas = pd.to_datetime(texto, format="%Y-%m-%d", errors="coerce")
    so_mes = pd.to_datetime(texto, format="%Y-%m", errors="coerce")
    return datas.fillna(so_mes)


def mascara_tipagem_invalida(serie: pd.Series, tipo: str, decimal: str = ".") -> pd.Series:
    """
    True onde o valor não pode ser convertido para `tipo` ("float", "int" ou
    "data") — mesma regra de checar_tipagem. Para "int", só texto inteiro
    vale ("10.0" é inválido, como em int("10.0")).
    """
    if tipo == "float":
        return converter_numero(serie, decimal).isna()
    if tipo == "int":
        return ~serie.astype("string").str.fullmatch(r"\s*[+-]?\d+\s*").fillna(False).astype(bool)
    if tipo == "data":
        return converter_data(serie).isna()
    raise ValueError(f"tipo desconhecido: {tipo}")


def mascara_valor_negativo(serie_numerica: pd.Series, coluna: str) -> pd.Series:
    """
    True onde o número é negativo — mesma regra de checar_valor_nao_negativo.
    Exceção: -1 em numero_de_operacoes é a máscara do BCB (quantidade não
    divulgada), não um valor negativo. NaN (não é número) não conta aqui: é
    papel da checagem de tipagem.
    """
    negativo = serie_numerica < 0
    if coluna == "numero_de_operacoes":
        negativo &= serie_numerica != -1
    return negativo.fillna(False).astype(bool)


def mascara_data_futura(serie_datas: pd.Series) -> pd.Series:
    """True onde a data é posterior a hoje — impossível para um dado já publicado."""
    return (serie_datas > pd.Timestamp(datetime.date.today())).fillna(False).astype(bool)


def gravar_quarentena_da_tabela(rejeitados: pd.DataFrame, motivos: pd.Series, tabela: str, load_id: str,
                                source_system: str, dir_quarentena) -> None:
    """
    Grava a quarentena de UMA tabela da Silver num único arquivo
    "<dir_quarentena>/<tabela>.parquet", SUBSTITUINDO o da execução anterior.

    A Silver é reconstruída inteira a cada execução (seção 4.1), então a sua
    quarentena também é: reprocessar não duplica registros rejeitados.
    O formato de cada linha é o mesmo de enviar_para_quarentena. Se
    `rejeitados` tiver a coluna _source_object, ela vai para a coluna de
    mesmo nome; o registro original inteiro vai para `payload` (JSON).

    Nunca levanta exceção: erro de gravação é registrado em log e o job segue.
    """
    try:
        agora = datetime.datetime.now()
        origem = rejeitados["_source_object"] if "_source_object" in rejeitados else pd.Series("", index=rejeitados.index)
        registros = rejeitados.astype(object).where(rejeitados.notna(), None).to_dict("records")
        df = pd.DataFrame({
            "_load_id": load_id,
            "_source_system": source_system,
            "_source_object": list(origem),
            "motivo": list(motivos),
            "payload": [json.dumps(r, ensure_ascii=False, default=str) for r in registros],
            "quarantined_at": agora,
        })
        pasta = Path(dir_quarentena)
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{tabela}.parquet"
        temporario = pasta / f"{tabela}.parquet.tmp"
        df.to_parquet(temporario, index=False)
        temporario.replace(destino)
        if len(df):
            logger.warning(f"Quarentena de {tabela}: {len(df)} registros ({df['motivo'].value_counts().to_dict()}).")
    except Exception as e:
        logger.error(f"Erro ao gravar a quarentena de {tabela}: {e}")
