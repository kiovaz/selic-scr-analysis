"""
Testes dos loaders da Bronze (SCR e Selic).

Regra que estes testes protegem (seções 3.3 e 4.1 do architecture.md):
a Bronze guarda o dado COMO VEIO — todas as colunas, como texto, inclusive
registros sujos. Validação de negócio e quarentena são da Silver. A Bronze só
rejeita o que não consegue ler (CSV sem as colunas usadas, resposta da API
sem a chave "value").

Nenhum teste acessa a rede: o SCR usa um ZIP sintético já colocado na pasta
de downloads (o loader o reaproveita), e a Selic usa requests.get simulado.
"""

import sys
import uuid
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pytest
import requests

import src.config as config
from src.ingestion.scr_file_loader import baixar_zips, carregar_scr, ler_blocos_do_zip
from src.ingestion.selic_api_loader import parsear_resposta_selic, carregar_selic
from src.ingestion.metadata import gerar_load_id

# Linhas de um CSV do SCR como o BCB publica: tudo texto, decimal com vírgula,
# -1 como máscara em numero_de_operacoes, e duas colunas "não usadas".
LINHAS_SCR = [
    {"data_base": "2024-01-31", "uf": "SP", "porte": "PF - Acima de 20 salários",
     "modalidade": "Financiamentos imobiliários", "numero_de_operacoes": "-1",
     "carteira_ativa": "1234,56", "origem": "Com destinação específica"},
    {"data_base": "2024-01-31", "uf": "XX", "porte": "PJ - Grande",
     "modalidade": "Financiamentos", "numero_de_operacoes": "10",
     "carteira_ativa": "abc", "origem": "Sem destinação específica"},
]


def _escrever_csv(caminho, linhas, encoding="utf-8-sig"):
    """Grava um CSV no formato do SCR (separador ';', tudo como texto)."""
    pd.DataFrame(linhas).to_csv(caminho, sep=config.SCR_SEPARADOR, index=False, encoding=encoding)


def _criar_zip_scr(dir_zips, ano, csvs):
    """
    Cria em `dir_zips` o ZIP do ano com o nome oficial (config.SCR_NOME_ZIP),
    para o loader reaproveitá-lo sem baixar. `csvs` é {nome_do_csv: linhas}.
    """
    dir_zips = Path(dir_zips)
    dir_zips.mkdir(parents=True, exist_ok=True)
    zip_path = dir_zips / config.SCR_NOME_ZIP.format(ano=ano)
    with zipfile.ZipFile(zip_path, "w") as z:
        for nome_csv, linhas in csvs.items():
            caminho_csv = dir_zips / nome_csv
            _escrever_csv(caminho_csv, linhas)
            z.write(caminho_csv, arcname=nome_csv)
            caminho_csv.unlink()
    return zip_path


@pytest.fixture
def pastas(tmp_path, monkeypatch):
    """Aponta Bronze e quarentena para uma pasta temporária do teste."""
    monkeypatch.setattr(config, "DIR_BRONZE", tmp_path / "raw")
    monkeypatch.setattr(config, "DIR_QUARENTENA", tmp_path / "raw" / "_quarentena")
    return tmp_path


def _ler_bronze(nome):
    """
    Lê uma tabela da Bronze. O ignore_prefixes=["."] é obrigatório: por
    padrão o pyarrow ignora pastas que começam com "_" ou ".", e a pasta da
    partição se chama "_ingestion_date=AAAA-MM-DD" — sem o parâmetro, a
    leitura volta vazia sem nenhum erro.
    """
    return pd.read_parquet(config.DIR_BRONZE / nome, ignore_prefixes=["."])


# ---------------------------------------------------------------------
# SCR — download
# ---------------------------------------------------------------------

def test_scr_timeout_pula_o_ano_sem_deixar_zip(tmp_path):
    """Download que estoura o tempo limite: o ano é pulado e não sobra arquivo."""
    def falso_get(url, **kwargs):
        assert kwargs["timeout"] == config.TIMEOUT_DOWNLOAD_SCR
        if "2023" in url:
            raise requests.Timeout("servidor parou de responder")
        resposta = Mock()
        resposta.raise_for_status.return_value = None
        resposta.iter_content.return_value = [b"conteudo"]
        return resposta

    with patch("src.ingestion.scr_file_loader.requests.get", side_effect=falso_get):
        caminhos = baixar_zips(tmp_path, anos=[2023, 2024])

    assert [(ano, p.name) for ano, p in caminhos] == [(2024, config.SCR_NOME_ZIP.format(ano=2024))]
    assert not (tmp_path / config.SCR_NOME_ZIP.format(ano=2023)).exists()
    assert list(tmp_path.glob("*.parcial")) == []


def test_scr_reaproveita_zip_local_sem_acessar_a_rede(pastas):
    _criar_zip_scr(pastas / "zips", 2024, {"scrdata_202401.csv": LINHAS_SCR})

    with patch("src.ingestion.scr_file_loader.requests.get") as falso_get:
        carregar_scr(dir_download=pastas / "zips", anos=[2024])

    falso_get.assert_not_called()


# ---------------------------------------------------------------------
# SCR — leitura e Bronze "como veio"
# ---------------------------------------------------------------------

def test_scr_bronze_guarda_todas_as_colunas_como_texto(pastas):
    _criar_zip_scr(pastas / "zips", 2024, {"scrdata_202401.csv": LINHAS_SCR})
    carregar_scr(dir_download=pastas / "zips", anos=[2024])

    bronze = _ler_bronze("bronze_scr")
    # As 7 colunas do CSV estão lá, não só as 5 usadas.
    for coluna in LINHAS_SCR[0]:
        assert coluna in bronze.columns
    linha_sp = bronze[bronze["uf"] == "SP"].iloc[0]
    assert linha_sp["carteira_ativa"] == "1234,56"
    assert linha_sp["numero_de_operacoes"] == "-1"
    # Os 7 metadados técnicos estão presentes.
    for meta in ["_ingestion_timestamp", "_ingestion_date", "_source_system",
                 "_source_object", "_load_id", "_ingestion_mode", "_record_hash"]:
        assert meta in bronze.columns
    # _source_object = nome do CSV + versão (data do arquivo dentro do ZIP)
    assert bronze["_source_object"].str.fullmatch(r"scrdata_202401\.csv@\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}").all()


def test_scr_registro_sujo_entra_intacto_e_sem_quarentena(pastas):
    _criar_zip_scr(pastas / "zips", 2024, {"scrdata_202401.csv": LINHAS_SCR})
    carregar_scr(dir_download=pastas / "zips", anos=[2024])

    bronze = _ler_bronze("bronze_scr")
    linha_suja = bronze[bronze["uf"] == "XX"]
    assert len(linha_suja) == 1
    assert linha_suja.iloc[0]["carteira_ativa"] == "abc"
    assert not config.DIR_QUARENTENA.exists()


def test_scr_csv_sem_coluna_usada_e_rejeitado_inteiro(tmp_path, caplog):
    sem_uf = [{k: v for k, v in linha.items() if k != "uf"} for linha in LINHAS_SCR]
    zip_path = _criar_zip_scr(tmp_path, 2024, {
        "scrdata_202401.csv": LINHAS_SCR,
        "scrdata_202402.csv": sem_uf,
    })

    blocos = list(ler_blocos_do_zip(zip_path))

    assert {nome for nome, _ in blocos} == {"scrdata_202401.csv"}
    assert "scrdata_202402.csv" in caplog.text


def test_scr_le_em_blocos(tmp_path, monkeypatch):
    """Com bloco de 1 linha, um CSV de 2 linhas vira 2 blocos."""
    monkeypatch.setattr(config, "SCR_TAMANHO_BLOCO", 1)
    zip_path = _criar_zip_scr(tmp_path, 2024, {"scrdata_202401.csv": LINHAS_SCR})

    blocos = list(ler_blocos_do_zip(zip_path))

    assert len(blocos) == 2
    assert all(len(bloco) == 1 for _, bloco in blocos)


def test_scr_nao_deixa_arquivo_temporario(pastas, monkeypatch):
    pasta_temp = pastas / "temp_do_sistema"
    pasta_temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(pasta_temp))
    _criar_zip_scr(pastas / "zips", 2024, {"scrdata_202401.csv": LINHAS_SCR})

    carregar_scr(dir_download=pastas / "zips", anos=[2024])

    assert list(pasta_temp.iterdir()) == []


# ---------------------------------------------------------------------
# Selic
# ---------------------------------------------------------------------

def _resposta_api(json_da_api):
    resposta = Mock()
    resposta.json.return_value = json_da_api
    resposta.raise_for_status.return_value = None
    return resposta


def test_selic_parse_mantem_tudo_como_veio():
    json_da_api = {"value": [
        {"SERCODIGO": "BM12_TJOVER12", "VALDATA": "2024-01-01T00:00:00-02:00", "VALVALOR": 0.97},
        {"SERCODIGO": "BM12_TJOVER12", "VALDATA": "2010-05-01T00:00:00-03:00", "VALVALOR": 0.75},
        {"SERCODIGO": "BM12_TJOVER12", "VALDATA": "2024-02-01T00:00:00-02:00", "VALVALOR": None},
    ]}

    df = parsear_resposta_selic(json_da_api)

    assert len(df) == 3                                      # sem recorte de período
    assert list(df["VALVALOR"][:2]) == ["0.97", "0.75"]     # texto, sem conversão
    assert df["VALVALOR"].iloc[2] is None                    # nulo continua nulo
    assert df["VALDATA"].iloc[0] == "2024-01-01T00:00:00-02:00"
    assert "SERCODIGO" in df.columns


def test_selic_resposta_sem_value_e_rejeitada():
    assert parsear_resposta_selic({"erro": "manutenção"}) is None


def test_selic_resposta_que_nao_e_json_nao_derruba_o_job(pastas):
    resposta = Mock()
    resposta.raise_for_status.return_value = None
    resposta.json.side_effect = requests.JSONDecodeError("não é JSON", "<html>", 0)

    with patch("src.ingestion.selic_api_loader.requests.get", return_value=resposta), \
         patch("src.ingestion.selic_api_loader.time.sleep"):
        load_id = carregar_selic()

    assert load_id
    assert not (config.DIR_BRONZE / "bronze_selic").exists()


def test_selic_valor_negativo_entra_intacto_e_sem_quarentena(pastas):
    json_da_api = {"value": [
        {"VALDATA": "2024-01-01T00:00:00-02:00", "VALVALOR": 0.97},
        {"VALDATA": "2024-02-01T00:00:00-02:00", "VALVALOR": -5.0},
    ]}

    with patch("src.ingestion.selic_api_loader.requests.get", return_value=_resposta_api(json_da_api)):
        carregar_selic()

    bronze = _ler_bronze("bronze_selic")
    assert "-5.0" in set(bronze["VALVALOR"])
    assert set(bronze["_source_system"]) == {"ipeadata"}
    assert not config.DIR_QUARENTENA.exists()


def test_load_id_e_uuid_e_unico_por_execucao():
    load_id_1 = gerar_load_id()
    load_id_2 = gerar_load_id()
    assert str(uuid.UUID(load_id_1)) == load_id_1
    assert load_id_1 != load_id_2


# ---------------------------------------------------------------------
# Definição de pronto da Sprint 2 (seção 8, revisada em 2026-09-26)
# ---------------------------------------------------------------------

def test_definicao_de_pronto_sprint2(pastas, caplog):
    """
    Os dois loaders REAIS rodam do zero e produzem bronze_scr e bronze_selic
    em disco; o registro sujo injetado entra intacto na Bronze sem derrubar o
    job; e o arquivo ilegível (CSV sem a coluna uf) é rejeitado com log.
    """
    sem_uf = [{k: v for k, v in linha.items() if k != "uf"} for linha in LINHAS_SCR]
    _criar_zip_scr(pastas / "zips", 2024, {
        "scrdata_202401.csv": LINHAS_SCR,
        "scrdata_202402.csv": sem_uf,
    })

    # SCR: loader real, sobre o ZIP local.
    load_id_scr = carregar_scr(dir_download=pastas / "zips", anos=[2024])

    # Selic: loader real, com a API simulada.
    json_da_api = {"value": [
        {"VALDATA": "2024-01-01T00:00:00-02:00", "VALVALOR": 0.97},
        {"VALDATA": "2024-02-01T00:00:00-02:00", "VALVALOR": -5.0},
    ]}
    with patch("src.ingestion.selic_api_loader.requests.get", return_value=_resposta_api(json_da_api)):
        carregar_selic()

    bronze_scr = _ler_bronze("bronze_scr")
    assert len(bronze_scr) == len(LINHAS_SCR)          # nada do CSV válido foi descartado
    assert "XX" in set(bronze_scr["uf"])               # registro sujo entra intacto
    assert set(bronze_scr["_load_id"]) == {load_id_scr}
    assert set(bronze_scr["_source_object"].str.split("@").str[0]) == {"scrdata_202401.csv"}
    assert "scrdata_202402.csv" in caplog.text         # ilegível rejeitado com log

    bronze_selic = _ler_bronze("bronze_selic")
    assert len(bronze_selic) == 2

    assert not config.DIR_QUARENTENA.exists()          # loaders não usam quarentena
