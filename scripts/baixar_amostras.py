"""
Sprint 1 — Baixa uma amostra real de cada base e imprime um diagnóstico.

Este script NÃO faz ingestão. Ele existe para responder as perguntas que
só dá para responder olhando o arquivo de verdade:

  - o download funciona ou a URL mudou?
  - qual é o encoding do CSV?
  - o decimal é vírgula ou ponto?
  - `carteira_ativa` está em reais ou em milhares?
  - quantas linhas tem um ano?
  - as colunas têm os nomes que a documentação diz?

Como rodar (da raiz do projeto):
    python scripts/baixar_amostras.py

Se algum download falhar, isso é resultado, não erro do script: significa
que a fonte mudou e o tema precisa ser reavaliado ANTES de escrever o
pipeline. Anote o que aconteceu.
"""

import io
import sys
import zipfile
from pathlib import Path

import requests

# Permite importar `src` rodando o script da raiz do projeto.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import config  # noqa: E402

ANO_AMOSTRA = 2024
PASTA_AMOSTRAS = config.RAIZ / "data" / "raw" / "_amostras"


def separador(titulo):
    print("\n" + "=" * 70)
    print(titulo)
    print("=" * 70)


def baixar_amostra_scr():
    """Baixa o ZIP de um ano do SCR.data e inspeciona o primeiro CSV."""
    separador(f"FONTE 1 — SCR.data ({ANO_AMOSTRA})")

    url = config.SCR_URL_TEMPLATE.format(ano=ANO_AMOSTRA)
    print(f"URL: {url}")
    print("Baixando... (o arquivo é grande, pode demorar)")

    try:
        resposta = requests.get(url, timeout=300)
        resposta.raise_for_status()
    except requests.exceptions.RequestException as erro:
        print(f"\nFALHOU: {erro}")
        print(f"Confira se a URL ainda existe em: {config.SCR_PORTAL}")
        return

    tamanho_mb = len(resposta.content) / 1024 / 1024
    print(f"OK. ZIP baixado: {tamanho_mb:.1f} MB")

    PASTA_AMOSTRAS.mkdir(parents=True, exist_ok=True)
    caminho_zip = PASTA_AMOSTRAS / f"scrdata_{ANO_AMOSTRA}.zip"
    caminho_zip.write_bytes(resposta.content)
    print(f"Salvo em: {caminho_zip}")

    with zipfile.ZipFile(io.BytesIO(resposta.content)) as z:
        arquivos = z.namelist()
        print(f"\nArquivos dentro do ZIP: {len(arquivos)}")
        for nome in arquivos[:5]:
            print(f"  - {nome}")
        if len(arquivos) > 5:
            print(f"  ... e mais {len(arquivos) - 5}")

        # Abre só o primeiro arquivo, só as primeiras linhas.
        primeiro = arquivos[0]
        print(f"\nInspecionando: {primeiro}")

        with z.open(primeiro) as f:
            primeiros_bytes = f.read(4000)

        encoding_detectado = None
        for encoding in config.SCR_ENCODINGS_CANDIDATOS:
            try:
                texto = primeiros_bytes.decode(encoding)
                encoding_detectado = encoding
                break
            except UnicodeDecodeError:
                continue

        if encoding_detectado is None:
            print("Nenhum dos encodings candidatos funcionou. Investigar.")
            return

        print(f"Encoding que funcionou: {encoding_detectado}")

        linhas = texto.splitlines()
        print(f"\nCabeçalho:\n  {linhas[0]}")
        print("\nPrimeiras 3 linhas de dados:")
        for linha in linhas[1:4]:
            print(f"  {linha}")

        colunas = linhas[0].split(config.SCR_SEPARADOR)
        print(f"\nTotal de colunas: {len(colunas)}")

        print("\nAs 5 colunas que o projeto usa estão presentes?")
        for coluna in config.SCR_COLUNAS_USADAS:
            existe = "SIM" if coluna in colunas else "NAO ENCONTRADA"
            print(f"  {coluna:25} {existe}")

    print("\n--- ANOTAR NO DOCUMENTO (Sprint 1) ---")
    print("  [ ] Decimal é vírgula ou ponto?")
    print("  [ ] carteira_ativa está em reais ou em milhares?")
    print("  [ ] Data de coleta:", "________")


def baixar_amostra_selic():
    """Chama a API do Ipeadata e inspeciona a resposta."""
    separador("FONTE 2 — Selic (Ipeadata)")

    print(f"URL: {config.SELIC_URL}")
    print("Requisitando...")

    try:
        resposta = requests.get(config.SELIC_URL, timeout=60)
        resposta.raise_for_status()
        dados = resposta.json()
    except requests.exceptions.RequestException as erro:
        print(f"\nFALHOU: {erro}")
        return
    except ValueError:
        print("\nFALHOU: a resposta não é um JSON válido.")
        print(f"Começo da resposta: {resposta.text[:200]}")
        return

    # A API OData devolve os registros dentro da chave "value".
    registros = dados.get("value", [])
    print(f"OK. Registros recebidos: {len(registros)}")

    if not registros:
        print("A resposta veio vazia. Investigar.")
        return

    print(f"\nCampos disponíveis: {list(registros[0].keys())}")
    print("\nPrimeiro registro da série:")
    print(f"  {registros[0]}")
    print("\nÚltimo registro da série:")
    print(f"  {registros[-1]}")

    print("\n--- ANOTAR NO DOCUMENTO (Sprint 1) ---")
    print("  [ ] Última competência disponível:", registros[-1].get("VALDATA"))
    print("  [ ] Licença / termos de uso do Ipeadata: ________")
    print("  [ ] Data de coleta:", "________")


if __name__ == "__main__":
    config.criar_pastas()
    baixar_amostra_scr()
    baixar_amostra_selic()
    separador("FIM")
    print("Preencha as pendências acima em docs/architecture.md, seção 2.")
