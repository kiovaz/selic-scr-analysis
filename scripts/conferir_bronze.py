"""
Confere a camada Bronze — usado na demonstração de idempotência da defesa
(seção 3.2 do docs/architecture.md):

    python scripts/conferir_bronze.py      # anota as contagens
    python scripts/run_pipeline.py         # roda a ingestão de novo
    python scripts/conferir_bronze.py      # as contagens têm que ser as mesmas

Mostra, para cada fonte: total de linhas, linhas por ano, meses com mais de
uma versão guardada (republicações do BCB) e a quantidade de duplicatas na
chave (_source_object, _record_hash) — que tem que ser zero.

Para não carregar 34 milhões de hashes de uma vez, lê cada arquivo Parquet
uma única vez e confere as duplicatas versão por versão.

Como rodar (da raiz do projeto):
    python scripts/conferir_bronze.py
"""

import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pyarrow.dataset as ds  # noqa: E402

from src import config  # noqa: E402


def abrir(nome):
    """Abre uma tabela da Bronze (ignore_prefixes: a partição começa com "_")."""
    caminho = config.DIR_BRONZE / nome
    if not caminho.exists():
        return None
    return ds.dataset(caminho, format="parquet", partitioning="hive", ignore_prefixes=["."])


def conferir_scr():
    dataset = abrir("bronze_scr")
    if dataset is None:
        print("bronze_scr: não existe.")
        return

    # Agrupa os arquivos Parquet por versão (_source_object): cada bloco gravado
    # pertence a uma única versão de CSV.
    arquivos_por_versao = defaultdict(list)
    linhas_por_versao = defaultdict(int)
    for fragmento in dataset.get_fragments():
        tabela = fragmento.to_table(columns=["_source_object"])
        for versao in tabela.column("_source_object").unique().to_pylist():
            arquivos_por_versao[versao].append(fragmento)
        for versao, n in zip(*_contar(tabela.column("_source_object"))):
            linhas_por_versao[versao] += n

    total = sum(linhas_por_versao.values())
    print(f"bronze_scr: {total:,} linhas em {len(linhas_por_versao)} versões de CSV")

    por_ano = defaultdict(int)
    versoes_por_mes = defaultdict(list)
    for versao, n in linhas_por_versao.items():
        nome_csv = versao.split("@")[0]
        por_ano[nome_csv[len("scrdata_"):len("scrdata_") + 4]] += n
        versoes_por_mes[nome_csv].append((versao, n))
    for ano in sorted(por_ano):
        print(f"  {ano}: {por_ano[ano]:>12,}")

    republicados = {m: v for m, v in versoes_por_mes.items() if len(v) > 1}
    if republicados:
        print("  Meses com mais de uma versão guardada (republicação do BCB):")
        for mes, versoes in sorted(republicados.items()):
            for versao, n in sorted(versoes):
                print(f"    {versao}: {n:,} linhas")
    else:
        print("  Nenhum mês com mais de uma versão guardada.")

    duplicatas = 0
    for versao, fragmentos in arquivos_por_versao.items():
        hashes = []
        for fragmento in fragmentos:
            tabela = fragmento.to_table(columns=["_record_hash"],
                                        filter=ds.field("_source_object") == versao)
            hashes.extend(tabela.column("_record_hash").to_pylist())
        duplicatas += len(hashes) - len(set(hashes))
    print(f"  Duplicatas na chave (_source_object, _record_hash): {duplicatas}")


def conferir_selic():
    dataset = abrir("bronze_selic")
    if dataset is None:
        print("bronze_selic: não existe.")
        return
    df = dataset.to_table(columns=["VALDATA", "_source_object", "_record_hash", "_ingestion_mode"]).to_pandas()
    print(f"bronze_selic: {len(df):,} linhas | VALDATA de {df['VALDATA'].min()[:10]} a {df['VALDATA'].max()[:10]}")
    print(f"  Por modo de carga: {df['_ingestion_mode'].value_counts().to_dict()}")
    releituras = df["VALDATA"].str[:10].value_counts()
    releituras = releituras[releituras > 1]
    if not releituras.empty:
        print(f"  Meses com mais de uma leitura (mês corrente que mudou de valor): {releituras.to_dict()}")
    print(f"  Duplicatas na chave (_source_object, _record_hash): "
          f"{int(df.duplicated(['_source_object', '_record_hash']).sum())}")


def _contar(coluna):
    """Conta as linhas de cada valor de uma coluna do pyarrow."""
    contagem = coluna.value_counts()
    return contagem.field("values").to_pylist(), contagem.field("counts").to_pylist()


def main():
    inicio = time.time()
    print(f"Conferência da Bronze em {config.DIR_BRONZE}\n")
    conferir_scr()
    print()
    conferir_selic()
    print(f"\n(conferência feita em {time.time() - inicio:.0f} s)")


if __name__ == "__main__":
    main()
