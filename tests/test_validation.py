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


# ---------------------------------------------------------------------
# Checagens por coluna (Silver): mesmo resultado das checagens registro a registro
# ---------------------------------------------------------------------

from src.validation.quality_checks import (  # noqa: E402
    checar_uf, checar_tipagem, checar_valor_nao_negativo, checar_data_no_intervalo,
    mascara_uf_invalida, mascara_tipagem_invalida, mascara_valor_negativo, mascara_data_futura,
    converter_numero, converter_data, gravar_quarentena_da_tabela,
)
from src import config as _config  # noqa: E402

CASOS = ["", "abc", "-5", "-1", "10", "10.0", "1234.56", "sp", "XX", "SP", " 7 "]


def test_mascara_uf_igual_a_checar_uf():
    mascara = mascara_uf_invalida(pd.Series(CASOS), _config)
    assert list(mascara) == [checar_uf(v, _config) is not None for v in CASOS]


def test_mascara_tipagem_igual_a_checar_tipagem():
    for tipo in ["float", "int"]:
        mascara = mascara_tipagem_invalida(pd.Series(CASOS), tipo)
        assert list(mascara) == [checar_tipagem(v, tipo) is not None for v in CASOS], tipo
    datas = ["2024-08-31", "2024-08", "31/08/2024", "", "abc"]
    mascara = mascara_tipagem_invalida(pd.Series(datas), "data")
    assert list(mascara) == [checar_tipagem(v, "date") is not None for v in datas]


def test_mascara_negativo_igual_a_checar_valor_nao_negativo():
    numericos = ["-5", "-1", "0", "10", "1234.56"]
    serie = converter_numero(pd.Series(numericos))
    for coluna in ["numero_de_operacoes", "carteira_ativa"]:
        mascara = mascara_valor_negativo(serie, coluna)
        assert list(mascara) == [checar_valor_nao_negativo(v, coluna) is not None for v in numericos], coluna


def test_decimal_com_virgula():
    serie = pd.Series(["1234,56", "abc", "-3,5"])
    assert list(mascara_tipagem_invalida(serie, "float", decimal=",")) == [False, True, False]
    assert list(converter_numero(serie, ",").round(2).fillna(-999)) == [1234.56, -999, -3.5]


def test_mascara_data_futura():
    import datetime
    hoje = datetime.date.today()
    textos = ["2024-08-31", (hoje + datetime.timedelta(days=40)).isoformat()]
    mascara = mascara_data_futura(converter_data(pd.Series(textos)))
    assert list(mascara) == [False, True]
    # coerente com checar_data_no_intervalo para datas depois do início do recorte
    assert [checar_data_no_intervalo(t, _config) is not None for t in textos] == [False, True]


def test_quarentena_da_tabela_substitui_a_anterior(tmp_path):
    rejeitados = pd.DataFrame({"uf": ["XX", "YY", "ZZ"], "_source_object": ["a@1", "a@1", "b@2"]})
    motivos = pd.Series(["uf_invalida"] * 3)
    for _ in range(2):
        gravar_quarentena_da_tabela(rejeitados, motivos, "silver_scr", "load", "scr_data", tmp_path)

    df = pd.read_parquet(tmp_path / "silver_scr.parquet")
    assert len(df) == 3                                  # 3, não 6
    assert list(df["_source_object"]) == ["a@1", "a@1", "b@2"]
    assert '"uf": "XX"' in df.iloc[0]["payload"]
    assert list(tmp_path.glob("*.tmp")) == []


def test_quarentena_da_tabela_nao_derruba_o_job(tmp_path, caplog):
    arquivo_no_lugar_da_pasta = tmp_path / "ocupado"
    arquivo_no_lugar_da_pasta.write_text("x")
    gravar_quarentena_da_tabela(pd.DataFrame({"uf": ["XX"]}), pd.Series(["uf_invalida"]),
                                "silver_scr", "load", "scr_data", arquivo_no_lugar_da_pasta)
    assert "Erro ao gravar a quarentena" in caplog.text
