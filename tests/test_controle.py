"""Testes da tabela de controle da ingestão (src/ingestion/controle.py)."""

from src.ingestion.controle import ler_controle, gravar_controle


def test_controle_inexistente_vira_dicionario_vazio(tmp_path):
    assert ler_controle(tmp_path / "nao_existe.json") == {}


def test_controle_ida_e_volta_sem_sobrar_tmp(tmp_path):
    caminho = tmp_path / "_controle" / "controle_scr.json"
    dados = {"2024": {"etag": '"abc"', "csvs": {"scrdata_202408.csv": {"status": "completo"}}}}

    gravar_controle(caminho, dados)

    assert ler_controle(caminho) == dados
    assert list(caminho.parent.glob("*.tmp")) == []
