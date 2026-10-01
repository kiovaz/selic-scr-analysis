"""
Loader do SCR.data (Banco Central) para a camada Bronze.

O que este módulo faz, em ordem:
1. Consulta a versão publicada do ZIP anual (ETag, sem baixar) e só baixa se
   ela mudou desde a última execução.
2. Lê o índice do ZIP e, para cada CSV mensal, compara a versão (data dentro
   do ZIP + CRC32) com a tabela de controle. Só as versões novas são gravadas.
3. Lê cada CSV novo em blocos, sem extrair para disco, anexa os metadados
   técnicos (seção 3.1) e grava em data/raw/bronze_scr/.

Por isso a ingestão é IDEMPOTENTE (seção 3.2 do architecture.md): rodar duas
vezes seguidas não muda a contagem de linhas. E quando o BCB republica um mês,
a versão nova entra inteira, sem apagar a antiga.

O que este módulo NÃO faz, de propósito (seções 3.3 e 4.1 do architecture.md):
- Não converte tipos: toda coluna é gravada como TEXTO, exatamente como veio.
- Não descarta colunas: a Bronze guarda as 24 colunas do CSV. Só as 5 de
  config.SCR_COLUNAS_USADAS viram Silver, e esse corte é feito na Silver.
- Não valida regra de negócio (UF, data, valor negativo) nem usa a quarentena.
  Registro sujo entra intacto na Bronze e é barrado na Silver.

A única rejeição feita aqui é ESTRUTURAL: um CSV que não tem as 5 colunas
usadas não serve ao projeto e é recusado inteiro, com registro em log.

Referência: seções 2.1, 3, 3.2, 4.1 de docs/architecture.md.
"""

import codecs
import datetime
import logging
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds
import requests

from src import config
from src.ingestion.controle import ler_controle, gravar_controle
from src.ingestion.metadata import gerar_load_id, anexar_metadados

logger = logging.getLogger(__name__)

# Quantos bytes do começo do CSV usamos para descobrir o encoding.
# 1 MB é suficiente para pegar os acentos das primeiras linhas.
BYTES_PARA_DETECTAR_ENCODING = 1024 * 1024


class CSVRejeitado(Exception):
    """CSV que não serve ao projeto (rejeição estrutural, seção 3.3)."""


# ---------------------------------------------------------------------
# Download: só quando a versão publicada mudou
# ---------------------------------------------------------------------

def consultar_etag(url):
    """
    Pergunta ao servidor do BCB qual é a versão publicada do ZIP, SEM baixá-lo:
    uma requisição HEAD devolve só os cabeçalhos (alguns bytes). O cabeçalho
    ETag muda sempre que o conteúdo do arquivo muda.

    Devolve o ETag, ou None se a consulta falhar (rede fora, servidor sem ETag).
    """
    try:
        resposta = requests.head(url, timeout=config.TIMEOUT_DOWNLOAD_SCR, allow_redirects=True)
        resposta.raise_for_status()
        etag = resposta.headers.get("ETag")
        logger.info(f"Versão publicada de {url}: ETag={etag} "
                    f"Last-Modified={resposta.headers.get('Last-Modified')}")
        return etag
    except Exception as e:
        logger.warning(f"Não foi possível consultar a versão de {url}: {e}")
        return None


def baixar_zips(dir_download=None, anos=None, forcar_redownload=False, controle=None):
    """
    Garante o ZIP do SCR de cada ano em disco e devolve a lista de pares
    (ano, caminho_do_zip).

    Para não baixar ~170 MB à toa, antes consulta a versão publicada (ETag,
    via HEAD) e compara com a registrada na tabela de controle:
    - mesma versão e ZIP em disco -> reaproveita, sem baixar;
    - versão diferente, desconhecida ou ZIP ausente -> baixa de novo;
    - consulta falhou e ZIP em disco -> reaproveita, com aviso no log.
    `forcar_redownload=True` baixa sempre.

    O ETag do ZIP baixado é anotado em `controle` (quem chama grava o arquivo).
    Erro de rede ou HTTP em um ano é registrado em log e não impede os outros.

    O download é gravado primeiro em "<nome>.parcial" e só é renomeado para
    ".zip" quando termina. Se a conexão cair no meio, não fica no disco um
    ZIP pela metade que seria "reaproveitado" na próxima execução.
    """
    if dir_download is None:
        dir_download = config.DIR_DOWNLOADS_SCR
    if anos is None:
        anos = range(config.ANO_INICIO, config.ANO_FIM + 1)
    if controle is None:
        controle = {}

    dir_download = Path(dir_download)
    dir_download.mkdir(parents=True, exist_ok=True)

    zip_paths = []

    for ano in anos:
        url = config.SCR_URL_TEMPLATE.format(ano=ano)
        zip_path = dir_download / config.SCR_NOME_ZIP.format(ano=ano)
        caminho_parcial = zip_path.with_name(zip_path.name + ".parcial")
        controle_ano = controle.setdefault(str(ano), {"etag": None, "csvs": {}})

        if not forcar_redownload and zip_path.exists():
            etag = consultar_etag(url)
            if etag is None:
                logger.warning(f"ZIP de {ano}: usando o arquivo local ({zip_path}) sem confirmar a versão.")
                zip_paths.append((ano, zip_path))
                continue
            if etag == controle_ano.get("etag"):
                logger.info(f"ZIP de {ano} não mudou desde a última execução. "
                            f"Reaproveitando {zip_path}, sem baixar.")
                zip_paths.append((ano, zip_path))
                continue
            logger.info(f"ZIP de {ano} mudou ou ainda não tem versão registrada. Baixando de novo.")

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
            # A versão baixada é a que veio no cabeçalho da própria resposta.
            controle_ano["etag"] = response.headers.get("ETag")
            zip_paths.append((ano, zip_path))
            logger.info(f"Download de {ano} concluído: {zip_path}")
        except Exception as e:
            logger.error(f"Falha ao baixar o ZIP de {ano} ({url}): {e}")
            # Apaga o pedaço baixado, se houver, para não deixar lixo.
            caminho_parcial.unlink(missing_ok=True)

    return zip_paths


# ---------------------------------------------------------------------
# Versão de cada CSV
# ---------------------------------------------------------------------

def versao_do_csv(info):
    """
    Versão de um CSV, lida do índice do ZIP (sem descompactar nada):
    a data do arquivo dentro do ZIP (ISO 8601) e o CRC32 do conteúdo (hexa).
    """
    data = datetime.datetime(*info.date_time).isoformat()
    return data, f"{info.CRC:08x}"


def montar_source_object(nome_csv, data, crc32, registro_anterior=None):
    """
    Monta o _source_object com a VERSÃO do arquivo: "<nome>@<data>".

    A versão é o que faz uma republicação do BCB entrar completa na Bronze:
    sem ela, as linhas que não mudaram teriam o mesmo _record_hash da versão
    antiga e seriam tratadas como "já gravadas" (seção 3.2 do architecture.md).

    Caso teórico: o CRC mudou mas a data não. Para não colidir com a versão
    anterior, acrescenta o CRC: "<nome>@<data>#crc<hex>".
    """
    source_object = f"{nome_csv}@{data}"
    if (registro_anterior
            and registro_anterior.get("data") == data
            and registro_anterior.get("crc32") not in (None, crc32)):
        logger.error(f"{nome_csv}: o conteúdo mudou (CRC {registro_anterior.get('crc32')} -> {crc32}) "
                     f"mas a data dentro do ZIP é a mesma. Gravando como {source_object}#crc{crc32}.")
        source_object = f"{source_object}#crc{crc32}"
    return source_object


def versao_ja_tratada(registro, data, crc32):
    """True se a tabela de controle diz que ESTA versão do CSV já foi tratada por completo."""
    if not registro or registro.get("status") not in ("completo", "rejeitado"):
        return False
    # crc32 None = controle reconstruído a partir da Bronze, que só guarda a data.
    return registro.get("data") == data and registro.get("crc32") in (None, crc32)


# ---------------------------------------------------------------------
# Leitura dos CSVs
# ---------------------------------------------------------------------

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


def ler_blocos_do_csv(zip_ref, nome_csv):
    """
    Lê um CSV de dentro do ZIP, bloco a bloco (gerador).

    Devolve blocos de no máximo config.SCR_TAMANHO_BLOCO linhas, sem carregar
    o CSV inteiro na memória e sem extrair nada para pasta temporária.

    Um CSV ilegível (nenhum encoding funciona) ou sem alguma das colunas de
    config.SCR_COLUNAS_USADAS é rejeitado inteiro: levanta CSVRejeitado.
    """
    encoding = detectar_encoding(zip_ref, nome_csv)
    if encoding is None:
        raise CSVRejeitado(f"CSV {nome_csv} rejeitado: nenhum encoding candidato conseguiu ler o arquivo.")

    # Confere o cabeçalho antes de ler os dados (nrows=0 lê só o cabeçalho).
    with zip_ref.open(nome_csv) as arquivo:
        cabecalho = _ler_csv(arquivo, encoding, nrows=0).columns
    faltando = [c for c in config.SCR_COLUNAS_USADAS if c not in cabecalho]
    if faltando:
        raise CSVRejeitado(f"CSV {nome_csv} rejeitado: faltam as colunas {faltando}.")

    logger.info(f"Lendo {nome_csv} com encoding {encoding}.")
    with zip_ref.open(nome_csv) as arquivo:
        for bloco in _ler_csv(arquivo, encoding, chunksize=config.SCR_TAMANHO_BLOCO):
            yield bloco


def ler_blocos_do_zip(zip_path):
    """
    Lê todos os CSVs de um ZIP, bloco a bloco: devolve (nome_do_csv, bloco).
    CSVs rejeitados são registrados em log e pulados.
    """
    try:
        with zipfile.ZipFile(zip_path) as zip_ref:
            csvs = [nome for nome in zip_ref.namelist() if nome.lower().endswith(".csv")]
            logger.info(f"{Path(zip_path).name}: {len(csvs)} CSVs encontrados.")
            for nome_csv in csvs:
                try:
                    for bloco in ler_blocos_do_csv(zip_ref, nome_csv):
                        yield nome_csv, bloco
                except CSVRejeitado as e:
                    logger.warning(str(e))
    except zipfile.BadZipFile as e:
        logger.error(f"Arquivo {zip_path} não é um ZIP válido: {e}")


# ---------------------------------------------------------------------
# Consultas à Bronze já gravada
# ---------------------------------------------------------------------

def _abrir_bronze(saida):
    """
    Abre a Bronze como dataset do pyarrow. O ignore_prefixes=["."] é
    obrigatório: por padrão o pyarrow ignora pastas que começam com "_", e a
    partição se chama "_ingestion_date=...".
    """
    return ds.dataset(saida, format="parquet", partitioning="hive", ignore_prefixes=["."])


def ler_hashes_da_versao(saida, source_object):
    """
    Lê da Bronze só os _record_hash de UMA versão de arquivo (_source_object).
    Usado para completar uma gravação interrompida sem duplicar linhas.
    Lê uma única coluna, com filtro, para não carregar a Bronze inteira.
    """
    if not Path(saida).exists():
        return set()
    tabela = _abrir_bronze(saida).to_table(
        columns=["_record_hash"], filter=ds.field("_source_object") == source_object)
    return set(tabela.column("_record_hash").to_pylist())


def reconstruir_controle_da_bronze(saida):
    """
    Se a tabela de controle se perdeu mas a Bronze existe, remonta o controle
    a partir das versões (_source_object) já gravadas. Sem isso, o pipeline
    acharia que nada foi ingerido e gravaria tudo de novo, duplicando a Bronze.

    O CRC32 não fica na Bronze, então é registrado como None: a comparação
    usa só a data, e o CRC é preenchido na próxima vez que o CSV for visto.
    """
    controle = {}
    if not Path(saida).exists():
        return controle
    coluna = _abrir_bronze(saida).to_table(columns=["_source_object"]).column("_source_object")
    versoes = set(coluna.unique().to_pylist())
    for source_object in sorted(versoes):
        nome_csv, _, resto = source_object.partition("@")
        data = resto.split("#")[0]
        ano = nome_csv[len("scrdata_"):len("scrdata_") + 4]
        csvs = controle.setdefault(ano, {"etag": None, "csvs": {}})["csvs"]
        # Se houver mais de uma versão do mesmo mês, vale a mais recente.
        if nome_csv not in csvs or data > csvs[nome_csv]["data"]:
            csvs[nome_csv] = {"data": data, "crc32": None,
                              "source_object": source_object, "status": "completo"}
    if versoes:
        logger.warning(f"Tabela de controle do SCR reconstruída a partir da Bronze: "
                       f"{len(versoes)} versões de CSV.")
    return controle


# ---------------------------------------------------------------------
# Ingestão
# ---------------------------------------------------------------------

def _gravar_versao(zip_ref, nome_csv, source_object, load_id, saida, hashes_ja_gravados):
    """
    Lê um CSV em blocos e grava na Bronze com os metadados técnicos.
    Linhas cujo _record_hash está em `hashes_ja_gravados` são puladas
    (só acontece ao retomar uma gravação interrompida). Devolve quantas
    linhas foram gravadas.
    """
    linhas = 0
    for bloco in ler_blocos_do_csv(zip_ref, nome_csv):
        bloco_com_metadados = anexar_metadados(
            bloco,
            source_system="scr_data",
            source_object=source_object,
            load_id=load_id,
        )
        if hashes_ja_gravados:
            bloco_com_metadados = bloco_com_metadados[
                ~bloco_com_metadados["_record_hash"].isin(hashes_ja_gravados)]
        if bloco_com_metadados.empty:
            continue
        bloco_com_metadados.to_parquet(
            saida,
            partition_cols=["_ingestion_date"],
            engine="pyarrow",
            index=False,
        )
        linhas += len(bloco_com_metadados)
    return linhas


def carregar_scr(dir_download=None, forcar_redownload=False, anos=None):
    """
    Ponto de entrada da ingestão do SCR na Bronze.

    Idempotente (seção 3.2): consulta a tabela de controle e só baixa os ZIPs
    que mudaram e só grava as versões de CSV que ainda não estão na Bronze.
    Rodar duas vezes seguidas não muda a contagem de linhas.

    Cada versão de CSV passa por dois estados no controle: "em_andamento"
    (antes do primeiro bloco) e "completo" (depois do último). Se o processo
    morrer no meio, a próxima execução encontra "em_andamento" e grava só as
    linhas que faltam daquela versão. Devolve o _load_id da execução.
    """
    load_id = gerar_load_id()
    saida = config.DIR_BRONZE / "bronze_scr"
    caminho_controle = config.ARQUIVO_CONTROLE_SCR

    controle = ler_controle(caminho_controle)
    if not controle:
        controle = reconstruir_controle_da_bronze(saida)

    zip_paths = baixar_zips(dir_download, anos=anos, forcar_redownload=forcar_redownload,
                            controle=controle)
    gravar_controle(caminho_controle, controle)  # guarda os ETags dos ZIPs baixados

    for ano, zip_path in zip_paths:
        csvs_ctrl = controle[str(ano)]["csvs"]
        linhas_gravadas = 0
        versoes_novas = 0
        try:
            with zipfile.ZipFile(zip_path) as zip_ref:
                infos = [i for i in zip_ref.infolist() if i.filename.lower().endswith(".csv")]
                for info in infos:
                    nome_csv = info.filename
                    data, crc32 = versao_do_csv(info)
                    registro = csvs_ctrl.get(nome_csv)

                    if versao_ja_tratada(registro, data, crc32):
                        if registro.get("crc32") is None:
                            registro["crc32"] = crc32  # completa um controle reconstruído
                        continue

                    source_object = montar_source_object(nome_csv, data, crc32, registro)

                    # Gravação interrompida desta mesma versão: descobre o que já foi gravado.
                    hashes_ja_gravados = set()
                    if (registro and registro.get("status") == "em_andamento"
                            and registro.get("source_object") == source_object):
                        hashes_ja_gravados = ler_hashes_da_versao(saida, source_object)
                        logger.warning(f"{nome_csv}: retomando gravação interrompida "
                                       f"({len(hashes_ja_gravados)} linhas já estavam na Bronze).")

                    # Marca ANTES de gravar: se o processo morrer, a próxima execução sabe.
                    csvs_ctrl[nome_csv] = {"data": data, "crc32": crc32,
                                           "source_object": source_object, "status": "em_andamento"}
                    gravar_controle(caminho_controle, controle)

                    try:
                        linhas_gravadas += _gravar_versao(zip_ref, nome_csv, source_object,
                                                          load_id, saida, hashes_ja_gravados)
                    except CSVRejeitado as e:
                        logger.warning(str(e))
                        csvs_ctrl[nome_csv]["status"] = "rejeitado"
                        gravar_controle(caminho_controle, controle)
                        continue
                    except Exception as e:
                        # Fica "em_andamento": a próxima execução completa o que falta.
                        logger.error(f"Erro ao gravar {source_object} na Bronze "
                                     f"(será retomado na próxima execução): {e}")
                        continue

                    # Marca DEPOIS de gravar a última linha.
                    csvs_ctrl[nome_csv]["status"] = "completo"
                    gravar_controle(caminho_controle, controle)
                    versoes_novas += 1
        except zipfile.BadZipFile as e:
            logger.error(f"Arquivo {zip_path} não é um ZIP válido: {e}")

        gravar_controle(caminho_controle, controle)
        logger.info(f"{zip_path.name}: {versoes_novas} versões de CSV novas, "
                    f"{linhas_gravadas} linhas gravadas na bronze_scr.")

    return load_id
