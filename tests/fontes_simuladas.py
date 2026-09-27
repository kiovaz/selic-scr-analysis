"""
Fontes de dados de mentira para os testes de idempotência — nenhuma rede.

- BCBSimulado: guarda, por ano, um ZIP montado em memória e o seu ETag, e
  responde a requests.head (só cabeçalhos) e requests.get (o ZIP) como o
  servidor do BCB. "Republicar" um mês é trocar o ZIP e o ETag.
- ipeadata_simulado: devolve a resposta OData da Selic que o teste mandar.
"""

import io
import zipfile
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pandas as pd

import src.config as config


def linhas_scr(mes, quantidade, extra=""):
    """Linhas de um CSV do SCR (tudo texto, como o BCB publica)."""
    return [
        {"data_base": f"2024-{mes:02d}-28", "uf": "SP", "modalidade": "Financiamentos imobiliários",
         "numero_de_operacoes": str(i), "carteira_ativa": f"{i},50", "porte": f"PF{extra}"}
        for i in range(quantidade)
    ]


def montar_zip(csvs):
    """
    Monta um ZIP em memória. `csvs` = {nome: (linhas, data_do_arquivo)}, onde
    data_do_arquivo é a tupla (ano, mês, dia, hora, min, seg) gravada no
    índice do ZIP — é a "versão" que o loader lê.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, (linhas, data) in csvs.items():
            texto = pd.DataFrame(linhas).to_csv(sep=config.SCR_SEPARADOR, index=False)
            z.writestr(zipfile.ZipInfo(nome, date_time=data), texto.encode("utf-8-sig"))
    return buffer.getvalue()


class BCBSimulado:
    def __init__(self):
        self.publicados = {}       # url -> (etag, bytes do ZIP)
        self.downloads = 0         # quantos GETs de ZIP aconteceram

    def publicar(self, ano, etag, csvs):
        url = config.SCR_URL_TEMPLATE.format(ano=ano)
        self.publicados[url] = (etag, montar_zip(csvs))

    def head(self, url, **kwargs):
        etag, _ = self.publicados[url]
        resposta = Mock()
        resposta.headers = {"ETag": etag, "Last-Modified": "simulado"}
        resposta.raise_for_status.return_value = None
        return resposta

    def get(self, url, **kwargs):
        self.downloads += 1
        etag, conteudo = self.publicados[url]
        resposta = Mock()
        resposta.headers = {"ETag": etag}
        resposta.raise_for_status.return_value = None
        resposta.iter_content.return_value = [conteudo]
        return resposta

    @contextmanager
    def no_ar(self):
        """Durante o bloco, o loader do SCR conversa com este servidor simulado."""
        with patch("src.ingestion.scr_file_loader.requests.head", side_effect=self.head), \
             patch("src.ingestion.scr_file_loader.requests.get", side_effect=self.get):
            yield self


@contextmanager
def ipeadata_simulado(registros):
    """Durante o bloco, a API da Selic devolve exatamente `registros`."""
    resposta = Mock()
    resposta.json.return_value = {"value": registros}
    resposta.raise_for_status.return_value = None
    with patch("src.ingestion.selic_api_loader.requests.get", return_value=resposta):
        yield


def selic(*pares):
    """Registros OData da Selic a partir de pares (data AAAA-MM-DD, valor)."""
    return [{"SERCODIGO": "BM12_TJOVER12", "VALDATA": f"{d}T00:00:00-03:00", "VALVALOR": v,
             "NIVNOME": "", "TERCODIGO": ""} for d, v in pares]


def ler_bronze(nome):
    """Lê uma tabela da Bronze (ignore_prefixes: a partição começa com "_")."""
    caminho = config.DIR_BRONZE / nome
    if not caminho.exists():
        return pd.DataFrame(columns=["_source_object", "_record_hash"])
    return pd.read_parquet(caminho, ignore_prefixes=["."])
