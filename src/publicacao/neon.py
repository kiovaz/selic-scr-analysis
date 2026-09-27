"""
Publicação no Neon (decisões 12 e 16 do docs/architecture.md).

Envia as tabelas prontas de data/final/ — Gold, análise e decisão — para um
banco Postgres no Neon, de onde o site em web/ lê os dados.

Regras:
- OPCIONAL: só roda se a string de conexão (DATABASE_URL) estiver no ambiente
  ou no arquivo .env da raiz. Sem ela, avisa e o pipeline segue normalmente.
- IDEMPOTENTE: cada tabela é apagada e criada de novo com o conteúdo do
  arquivo. Publicar duas vezes deixa o banco igual ao arquivo, sem duplicar.
- TUDO OU NADA: todas as tabelas são trocadas numa única transação. Se algo
  falha no meio, o banco volta ao estado anterior e o site continua mostrando
  a publicação antiga.

Nada aqui calcula indicador: o banco é uma cópia do que o pipeline gerou.
"""

import datetime
import json
import logging
import os

import pandas as pd
from dotenv import load_dotenv

from src import config
from src.ingestion.metadata import gerar_load_id

logger = logging.getLogger(__name__)

# Tabela que registra cada publicação: quando, qual execução e quantas linhas.
TABELA_CONTROLE = "publicacao_controle"


def ler_string_conexao():
    """
    A string de conexão do Neon, ou None se não estiver configurada.
    Uma variável de ambiente já definida vale mais que o .env (override=False).
    """
    load_dotenv(config.ARQUIVO_ENV, override=False)
    return os.environ.get(config.VARIAVEL_CONEXAO) or None


def tipo_postgres(serie):
    """Tipo da coluna no Postgres, a partir do tipo da coluna no pandas."""
    if pd.api.types.is_bool_dtype(serie):
        return "boolean"
    if pd.api.types.is_integer_dtype(serie):
        return "bigint"
    if pd.api.types.is_float_dtype(serie):
        return "double precision"
    if pd.api.types.is_datetime64_any_dtype(serie):
        return "date"
    # Colunas "object" com datas do Python (ex.: ano_mes da Gold) também são date.
    valores = serie.dropna()
    if len(valores) and all(isinstance(v, datetime.date) for v in valores):
        return "date"
    return "text"


def preparar_linhas(df):
    """
    Linhas prontas para o banco: datas viram date, números viram números do
    Python e valor ausente (NaN) vira None — que o Postgres grava como NULL.
    """
    df = df.copy()
    for coluna in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[coluna]):
            df[coluna] = df[coluna].dt.date
    df = df.astype(object).where(df.notna(), None)
    return [tuple(linha) for linha in df.itertuples(index=False, name=None)]


def ler_tabelas():
    """
    Lê os arquivos de data/final/ que viram tabelas. A frase de fechamento é
    um JSON: vira uma tabela de uma linha, com o JSON inteiro numa coluna.
    """
    tabelas = {}
    for nome, arquivo in config.tabelas_publicadas().items():
        if arquivo.suffix == ".json":
            conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
            tabelas[nome] = pd.DataFrame({"dados": [json.dumps(conteudo, ensure_ascii=False)]})
        else:
            tabelas[nome] = pd.read_parquet(arquivo)
    return tabelas


def _recriar_tabela(cursor, nome, df):
    """Apaga a tabela, cria de novo com as colunas do arquivo e envia as linhas com COPY."""
    from psycopg import sql

    if nome == "frase_fechamento":
        colunas = [("dados", "jsonb")]
    else:
        colunas = [(c, tipo_postgres(df[c])) for c in df.columns]

    cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(nome)))
    cursor.execute(sql.SQL("CREATE TABLE {} ({})").format(
        sql.Identifier(nome),
        sql.SQL(", ").join(sql.SQL("{} {}").format(sql.Identifier(c), sql.SQL(t)) for c, t in colunas),
    ))
    comando_copy = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(nome), sql.SQL(", ").join(sql.Identifier(c) for c, _ in colunas))
    with cursor.copy(comando_copy) as copy:
        for linha in preparar_linhas(df):
            copy.write_row(linha)


def publicar(tabelas, string_conexao, conectar=None):
    """
    Troca todas as tabelas no banco numa única transação e registra a
    publicação em publicacao_controle. Devolve o número de linhas por tabela.

    `conectar` existe para os testes trocarem o banco por um falso.
    """
    if conectar is None:
        import psycopg
        conectar = psycopg.connect

    load_id = gerar_load_id()
    linhas = {nome: len(df) for nome, df in tabelas.items()}

    # O "with" da conexão faz o COMMIT no fim; se der erro, faz ROLLBACK.
    with conectar(string_conexao) as conexao:
        with conexao.cursor() as cursor:
            for nome, df in tabelas.items():
                _recriar_tabela(cursor, nome, df)
            # Índice para o site filtrar a Gold por estado e modalidade.
            cursor.execute("CREATE INDEX ON gold_credito_selic (uf, modalidade)")
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {TABELA_CONTROLE} "
                "(load_id text, publicado_em timestamptz, linhas jsonb)")
            cursor.execute(
                f"INSERT INTO {TABELA_CONTROLE} (load_id, publicado_em, linhas) VALUES (%s, now(), %s)",
                (load_id, json.dumps(linhas)))
    logger.info(f"Publicação {load_id} concluída: {linhas}")
    return linhas


def executar_publicacao(conectar=None):
    """
    Etapa do pipeline. Devolve o número de linhas por tabela, ou None se a
    publicação foi pulada (sem string de conexão ou com saídas faltando).
    """
    string_conexao = ler_string_conexao()
    if not string_conexao:
        logger.warning(f"Publicação pulada: {config.VARIAVEL_CONEXAO} não configurada (.env).")
        return None

    faltando = [str(a) for a in config.tabelas_publicadas().values() if not a.exists()]
    if faltando:
        logger.error(f"Publicação: faltam as saídas {faltando}. Rode o pipeline completo antes.")
        return None

    return publicar(ler_tabelas(), string_conexao, conectar=conectar)
