"""
Loader do SCR.data (Banco Central) para a camada Bronze.

O que este módulo faz, em ordem:
1. Baixa o ZIP anual do SCR (ou reaproveita o que já está em disco).
2. Lê cada CSV mensal de dentro do ZIP, em blocos, sem extrair para disco.
3. Anexa os metadados técnicos (seção 3.1) e grava em data/raw/bronze_scr/.

O que este módulo NÃO faz, de propósito (seções 3.3 e 4.1 do architecture.md):
- Não converte tipos: toda coluna é gravada como TEXTO, exatamente como veio.
- Não descarta colunas: a Bronze guarda as 24 colunas do CSV. Só as 5 de
  config.SCR_COLUNAS_USADAS viram Silver, e esse corte é feito na Silver.
- Não valida regra de negócio (UF, data, valor negativo) nem usa a quarentena.
  Registro sujo entra intacto na Bronze e é barrado na Silver. Assim, se uma
  regra de validação tiver bug, o dado não se perde: basta corrigir a regra e
  reprocessar a partir da Bronze.

A única rejeição feita aqui é ESTRUTURAL: um CSV que não tem as 5 colunas
usadas não serve ao projeto e é recusado inteiro, com registro em log.

Referência: seções 2.1, 3, 4.1 de docs/architecture.md.
"""

import codecs
import logging
import zipfile
from pathlib import Path

import pandas as pd
import requests

from src import config
from src.ingestion.metadata import gerar_load_id, anexar_metadados

logger = logging.getLogger(__name__)

# Quantos bytes do começo do CSV usamos para descobrir o encoding.
# 1 MB é suficiente para pegar os acentos das primeiras linhas.
BYTES_PARA_DETECTAR_ENCODING = 1024 * 1024


def baixar_zips(dir_download=None, anos=None, forcar_redownload=False):
    """
    Baixa o ZIP do SCR de cada ano e devolve a lista de caminhos em disco.

    - `anos`: lista de anos a processar. Sem ela, usa ANO_INICIO a ANO_FIM.
    - Se o ZIP do ano já existe em disco, é reaproveitado (a não ser que
      `forcar_redownload=True`). Cada ZIP tem ~170 MB.
    - Erro de rede ou HTTP em um ano é registrado em log e não impede os
      outros anos.

    O download é gravado primeiro em "<nome>.parcial" e só é renomeado para
    ".zip" quando termina. Se a conexão cair no meio, não fica no disco um
    ZIP pela metade que seria "reaproveitado" na próxima execução.
    """
    if dir_download is None:
        dir_download = config.DIR_DOWNLOADS_SCR
    if anos is None:
        anos = range(config.ANO_INICIO, config.ANO_FIM + 1)

    dir_download = Path(dir_download)
    dir_download.mkdir(parents=True, exist_ok=True)

    zip_paths = []

    for ano in anos:
        url = config.SCR_URL_TEMPLATE.format(ano=ano)
        zip_path = dir_download / config.SCR_NOME_ZIP.format(ano=ano)
        caminho_parcial = zip_path.with_name(zip_path.name + ".parcial")

        if zip_path.exists() and not forcar_redownload:
            logger.info(f"ZIP de {ano} já está em disco ({zip_path}). Reaproveitando, sem baixar.")
            zip_paths.append(zip_path)
            continue

        logger.info(f"Baixando o ZIP de {ano}: {url}")
        try:
            # timeout = (conectar, ler). Sem ele, uma conexão que para de
            # mandar dados deixaria o pipeline travado para sempre.
            response = requests.get(url, stream=True, timeout=config.TIMEOUT_DOWNLOAD_SCR)
            response.raise_for_status()

            with open(caminho_parcial, "wb") as f:
                for pedaco in response.iter_content(chunk_size=1024 * 1024):
                    f.write(pedaco)

            # Só agora, com o download completo, o arquivo ganha o nome final.
            caminho_parcial.replace(zip_path)
            zip_paths.append(zip_path)
            logger.info(f"Download de {ano} concluído: {zip_path}")
        except Exception as e:
            logger.error(f"Falha ao baixar o ZIP de {ano} ({url}): {e}")
            # Apaga o pedaço baixado, se houver, para não deixar lixo.
            caminho_parcial.unlink(missing_ok=True)

    return zip_paths


def detectar_encoding(zip_ref, nome_csv):
    """
    Descobre o encoding do CSV testando os candidatos de
    config.SCR_ENCODINGS_CANDIDATOS NA ORDEM declarada.

    Só o começo do arquivo é lido. O decodificador "incremental" com
    final=False aceita que o último caractere do trecho esteja cortado ao
    meio (acento partido na fronteira de 1 MB), sem acusar erro falso.

    Devolve None se nenhum candidato funcionar.
    """
    with zip_ref.open(nome_csv) as arquivo:
        amostra = arquivo.read(BYTES_PARA_DETECTAR_ENCODING)

    for encoding in config.SCR_ENCODINGS_CANDIDATOS:
        try:
            codecs.getincrementaldecoder(encoding)().decode(amostra, final=False)
            return encoding
        except UnicodeDecodeError:
            logger.debug(f"{nome_csv} não decodifica como {encoding}.")
    return None


def _ler_csv(arquivo, encoding, **opcoes):
    """
    Lê o CSV (já aberto de dentro do ZIP) com o contrato de leitura da Bronze:
    - dtype=str: toda coluna vira texto, nada é convertido;
    - keep_default_na=False: "NA" e "" continuam sendo o texto que vieram
      (sem isso o pandas trocaria esses valores por nulo em silêncio).
    """
    return pd.read_csv(
        arquivo,
        sep=config.SCR_SEPARADOR,
        encoding=encoding,
        dtype=str,
        keep_default_na=False,
        **opcoes,
    )


def ler_blocos_do_zip(zip_path):
    """
    Lê os CSVs de um ZIP do SCR, bloco a bloco.

    É um gerador: devolve um par (nome_do_csv, bloco) de cada vez, com
    config.SCR_TAMANHO_BLOCO linhas no máximo. Assim o CSV nunca é carregado
    inteiro na memória, e nada é extraído para pasta temporária.

    CSV ilegível (nenhum encoding funciona) ou sem alguma das colunas de
    config.SCR_COLUNAS_USADAS é rejeitado inteiro, com log, e os demais seguem.
    """
    try:
        with zipfile.ZipFile(zip_path) as zip_ref:
            csvs = [nome for nome in zip_ref.namelist() if nome.lower().endswith(".csv")]
            logger.info(f"{zip_path.name}: {len(csvs)} CSVs encontrados.")

            for nome_csv in csvs:
                encoding = detectar_encoding(zip_ref, nome_csv)
                if encoding is None:
                    logger.error(f"CSV {nome_csv} rejeitado: nenhum encoding candidato conseguiu ler o arquivo.")
                    continue

                # Confere o cabeçalho antes de ler os dados (nrows=0 lê só o cabeçalho).
                with zip_ref.open(nome_csv) as arquivo:
                    cabecalho = _ler_csv(arquivo, encoding, nrows=0).columns
                faltando = [c for c in config.SCR_COLUNAS_USADAS if c not in cabecalho]
                if faltando:
                    logger.warning(f"CSV {nome_csv} rejeitado: faltam as colunas {faltando}.")
                    continue

                logger.info(f"Lendo {nome_csv} com encoding {encoding}.")
                try:
                    with zip_ref.open(nome_csv) as arquivo:
                        for bloco in _ler_csv(arquivo, encoding,
                                              chunksize=config.SCR_TAMANHO_BLOCO):
                            yield nome_csv, bloco
                except (UnicodeDecodeError, pd.errors.ParserError) as e:
                    # Erro no meio do arquivo: os blocos anteriores já foram
                    # gravados. Registramos para que fique visível no log.
                    logger.error(f"Erro ao ler {nome_csv} (leitura interrompida; blocos anteriores já gravados): {e}")
    except zipfile.BadZipFile as e:
        logger.error(f"Arquivo {zip_path} não é um ZIP válido: {e}")


def carregar_scr(dir_download=None, forcar_redownload=False, anos=None):
    """
    Ponto de entrada da ingestão do SCR na Bronze.

    Baixa (ou reaproveita) os ZIPs, lê cada CSV em blocos e grava cada bloco
    com os metadados técnicos em data/raw/bronze_scr/, particionado por
    _ingestion_date. Devolve o _load_id da execução.
    """
    load_id = gerar_load_id()
    saida = config.DIR_BRONZE / "bronze_scr"

    zip_paths = baixar_zips(dir_download, anos=anos, forcar_redownload=forcar_redownload)

    for zip_path in zip_paths:
        linhas_gravadas = 0
        for nome_csv, bloco in ler_blocos_do_zip(zip_path):
            try:
                bloco_com_metadados = anexar_metadados(
                    bloco,
                    source_system="scr_data",
                    source_object=nome_csv,
                    load_id=load_id,
                )
                bloco_com_metadados.to_parquet(
                    saida,
                    partition_cols=["_ingestion_date"],
                    engine="pyarrow",
                    index=False,
                )
                linhas_gravadas += len(bloco)
            except Exception as e:
                logger.error(f"Erro ao gravar um bloco de {nome_csv} na Bronze: {e}")
        logger.info(f"{zip_path.name}: {linhas_gravadas} linhas gravadas na bronze_scr.")

    return load_id
