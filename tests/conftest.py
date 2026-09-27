"""
Proteções que valem para TODOS os testes (o pytest carrega este arquivo sozinho).

1. Pastas de dados isoladas: toda pasta e arquivo de dados do config.py passa
   a apontar para uma pasta temporária do teste. Nenhum teste consegue
   escrever em data/ — nem na Bronze, nem na quarentena, nem nas tabelas de
   controle.
2. Sem rede: requests.get e requests.head levantam erro se forem chamados
   sem simulação. Quem precisa de resposta da fonte usa unittest.mock.patch
   no próprio teste. Assim o CI nunca depende do BCB ou do Ipeadata.
3. Sem banco: o .env real não é lido e DATABASE_URL é apagada do ambiente,
   então nenhum teste publica no Neon.
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.config as config  # noqa: E402


@pytest.fixture(autouse=True)
def dados_isolados(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    monkeypatch.setattr(config, "DIR_BRONZE", raw)
    monkeypatch.setattr(config, "DIR_SILVER", tmp_path / "processed")
    monkeypatch.setattr(config, "DIR_GOLD", tmp_path / "final")
    monkeypatch.setattr(config, "DIR_QUARENTENA", raw / "_quarentena")
    monkeypatch.setattr(config, "DIR_AMOSTRAS", raw / "_amostras")
    monkeypatch.setattr(config, "DIR_DOWNLOADS_SCR", raw / "_downloads")
    monkeypatch.setattr(config, "DIR_CONTROLE", raw / "_controle")
    monkeypatch.setattr(config, "ARQUIVO_CONTROLE_SCR", raw / "_controle" / "controle_scr.json")
    monkeypatch.setattr(config, "ARQUIVO_CONTROLE_SELIC", raw / "_controle" / "controle_selic.json")
    processed = tmp_path / "processed"
    monkeypatch.setattr(config, "ARQUIVO_SILVER_SCR", processed / "silver_scr.parquet")
    monkeypatch.setattr(config, "ARQUIVO_SILVER_SELIC", processed / "silver_selic.parquet")
    monkeypatch.setattr(config, "ARQUIVO_RELATORIO_SILVER", processed / "_relatorio_silver.json")
    final = tmp_path / "final"
    monkeypatch.setattr(config, "ARQUIVO_GOLD", final / "gold_credito_selic.parquet")
    monkeypatch.setattr(config, "ARQUIVO_ANALISE_BRASIL", final / "analise_brasil_modalidade.parquet")
    monkeypatch.setattr(config, "ARQUIVO_ANALISE_UF", final / "analise_uf_modalidade.parquet")
    monkeypatch.setattr(config, "ARQUIVO_RELATORIO_GOLD", final / "_relatorio_gold.json")
    monkeypatch.setattr(config, "DIR_FIGURAS", tmp_path / "figuras")   # não sobrescreve as figuras reais
    monkeypatch.setattr(config, "ARQUIVO_ML_DATASET", final / "gold_ml_dataset.parquet")
    monkeypatch.setattr(config, "ARQUIVO_ML_RESULTADOS", final / "ml_resultados.json")
    monkeypatch.setattr(config, "ARQUIVO_ML_PREVISOES_TESTE", final / "ml_previsoes_teste.parquet")
    monkeypatch.setattr(config, "ARQUIVO_ML_PREVISAO_PRODUCAO", final / "ml_previsao_producao.parquet")
    monkeypatch.setattr(config, "ARQUIVO_RECOMENDACAO", final / "recomendacao_trimestre.parquet")
    monkeypatch.setattr(config, "ARQUIVO_SENSIBILIDADE", final / "sensibilidade_limiar.parquet")
    monkeypatch.setattr(config, "ARQUIVO_FRASE", final / "frase_fechamento.json")
    # Nenhum teste lê o .env real nem publica no Neon de verdade.
    monkeypatch.setattr(config, "ARQUIVO_ENV", tmp_path / ".env")
    monkeypatch.delenv(config.VARIAVEL_CONEXAO, raising=False)
    return tmp_path


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    def bloqueado(*args, **kwargs):
        raise requests.ConnectionError("Rede bloqueada nos testes: simule a resposta com unittest.mock.patch.")
    monkeypatch.setattr(requests, "get", bloqueado)
    monkeypatch.setattr(requests, "head", bloqueado)
