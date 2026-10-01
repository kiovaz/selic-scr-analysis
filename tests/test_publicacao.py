"""
Testes da publicação no Neon (src/publicacao/neon.py).

Nenhum teste abre conexão de verdade: o banco é trocado por um FALSO que só
anota os comandos recebidos, as linhas enviadas e se houve COMMIT ou ROLLBACK.
"""

import datetime
import json

import numpy as np
import pandas as pd
import pytest

from src import config
from src.publicacao import neon


class CopyFalso:
    def __init__(self, banco, comando):
        self.banco, self.comando = banco, comando

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False

    def write_row(self, linha):
        if self.banco.falhar_no_copy:
            raise RuntimeError("falha simulada no envio")
        self.banco.linhas_enviadas.append((self.comando, linha))


class CursorFalso:
    def __init__(self, banco):
        self.banco = banco

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        return False

    def execute(self, comando, parametros=None):
        texto = comando.as_string(None) if hasattr(comando, "as_string") else comando
        self.banco.comandos.append((texto, parametros))

    def copy(self, comando):
        return CopyFalso(self.banco, comando.as_string(None))


class BancoFalso:
    """Imita o `with psycopg.connect(...) as conexao`: commit no fim, rollback se der erro."""

    def __init__(self, falhar_no_copy=False):
        self.comandos, self.linhas_enviadas = [], []
        self.falhar_no_copy = falhar_no_copy
        self.commit = self.rollback = False
        self.conexoes = 0

    def conectar(self, string_conexao):
        self.conexoes += 1
        return self

    def __enter__(self):
        return self

    def __exit__(self, tipo_erro, *resto):
        if tipo_erro is None:
            self.commit = True
        else:
            self.rollback = True
        return False

    def cursor(self):
        return CursorFalso(self)


def _gravar_saidas():
    """Arquivos mínimos de data/final/, com as colunas e tipos reais."""
    config.DIR_GOLD.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "ano_mes": [datetime.date(2026, 5, 1), datetime.date(2026, 6, 1)],
        "uf": ["SP", "SP"], "modalidade": ["Financiamentos imobiliários"] * 2,
        "qtd_operacoes": [10, 12], "volume_rs": [1000.0, 1100.0],
        "tem_mes_anterior": [False, True], "var_volume_pct": [np.nan, 10.0],
    }).to_parquet(config.ARQUIVO_GOLD)
    pd.DataFrame({"grupo": ["expandir"], "posicao": [1], "uf": ["SP"],
                  "modalidade": ["Financiamentos imobiliários"], "prob_ganha_forca": [0.9],
                  "volume_rs": [1100.0]}).to_parquet(config.ARQUIVO_RECOMENDACAO)
    pd.DataFrame({"uf": ["SP"], "modalidade": ["Financiamentos imobiliários"],
                  "origem": pd.to_datetime(["2026-06-01"]), "prob_ganha_forca": [0.9]}).to_parquet(
        config.ARQUIVO_ML_PREVISAO_PRODUCAO)
    pd.DataFrame({"regra": ["nota mínima"], "parametro": [0.5], "precisao_modelo": [0.7],
                  "precisao_regra_simples": [np.nan]}).to_parquet(config.ARQUIVO_SENSIBILIDADE)
    pd.DataFrame({"modalidade": ["Financiamentos"], "defasagem_meses": [4], "spearman": [0.4],
                  "significativo": [True]}).to_parquet(config.ARQUIVO_ANALISE_BRASIL)
    pd.DataFrame({"uf": ["SP"], "modalidade": ["Financiamentos"], "defasagem_meses": [2],
                  "spearman": [0.1]}).to_parquet(config.ARQUIVO_ANALISE_UF)
    config.ARQUIVO_FRASE.write_text(json.dumps({"tamanho_lista": 20, "trimestre_recomendado": "set–nov/2026"}),
                                    encoding="utf-8")


def test_sem_string_de_conexao_pula_sem_conectar():
    banco = BancoFalso()
    assert neon.executar_publicacao(conectar=banco.conectar) is None
    assert banco.conexoes == 0


def test_string_lida_do_arquivo_env(monkeypatch):
    config.ARQUIVO_ENV.write_text("DATABASE_URL=postgresql://teste\n", encoding="utf-8")
    assert neon.ler_string_conexao() == "postgresql://teste"
    monkeypatch.delenv(config.VARIAVEL_CONEXAO, raising=False)  # load_dotenv gravou no ambiente


def test_saida_faltando_nao_envia_nada(monkeypatch, caplog):
    monkeypatch.setenv(config.VARIAVEL_CONEXAO, "postgresql://teste")
    _gravar_saidas()
    config.ARQUIVO_RECOMENDACAO.unlink()
    banco = BancoFalso()
    assert neon.executar_publicacao(conectar=banco.conectar) is None
    assert banco.conexoes == 0
    assert "recomendacao_trimestre.parquet" in caplog.text


def test_tipos_das_colunas():
    df = pd.DataFrame({
        "b": [True], "i": [1], "f": [1.5], "t": ["SP"],
        "d": [datetime.date(2026, 6, 1)], "ts": pd.to_datetime(["2026-06-01"]),
    })
    assert {c: neon.tipo_postgres(df[c]) for c in df} == {
        "b": "boolean", "i": "bigint", "f": "double precision", "t": "text", "d": "date", "ts": "date"}


def test_nan_vira_null_e_numeros_viram_python():
    linhas = neon.preparar_linhas(pd.DataFrame({"x": [1.5, np.nan], "n": [1, 2]}))
    assert linhas == [(1.5, 1), (None, 2)]
    assert type(linhas[1][1]) is int


def test_publica_todas_as_tabelas_numa_transacao(monkeypatch):
    monkeypatch.setenv(config.VARIAVEL_CONEXAO, "postgresql://teste")
    _gravar_saidas()
    banco = BancoFalso()
    linhas = neon.executar_publicacao(conectar=banco.conectar)

    assert linhas == {"gold_credito_selic": 2, "recomendacao_trimestre": 1, "ml_previsao_producao": 1,
                      "sensibilidade_limiar": 1,
                      "analise_brasil_modalidade": 1, "analise_uf_modalidade": 1, "frase_fechamento": 1}
    assert banco.conexoes == 1 and banco.commit and not banco.rollback
    textos = [c for c, _ in banco.comandos]
    for tabela in linhas:
        assert f'DROP TABLE IF EXISTS "{tabela}"' in textos
    # A frase vai inteira numa coluna jsonb.
    assert any('CREATE TABLE "frase_fechamento" ("dados" jsonb)' == t for t in textos)
    # O controle registra as contagens.
    insert = [p for c, p in banco.comandos if c.startswith("INSERT INTO publicacao_controle")]
    assert len(insert) == 1 and json.loads(insert[0][1]) == linhas
    # A linha da Gold com NaN chega como NULL.
    gold = [l for c, l in banco.linhas_enviadas if '"gold_credito_selic"' in c]
    assert gold[0][-1] is None and gold[1][-1] == 10.0


def test_falha_no_meio_desfaz_tudo(monkeypatch):
    monkeypatch.setenv(config.VARIAVEL_CONEXAO, "postgresql://teste")
    _gravar_saidas()
    banco = BancoFalso(falhar_no_copy=True)
    with pytest.raises(RuntimeError):
        neon.executar_publicacao(conectar=banco.conectar)
    assert banco.rollback and not banco.commit
