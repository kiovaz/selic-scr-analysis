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


def obter_zip_do_scr(forcar_download=False):
    """
    Devolve o caminho do ZIP da amostra, baixando só quando precisa.

    O arquivo tem ~176 MB. Rebaixar a cada execução é desperdício, então
    só baixamos se ele ainda não está em disco. Para conferir se a fonte
    mudou, rode com --forcar-download.

    Devolve None se o download falhar — quem chama trata isso como
    resultado do diagnóstico, não como erro do script.
    """
    PASTA_AMOSTRAS.mkdir(parents=True, exist_ok=True)
    caminho_zip = PASTA_AMOSTRAS / f"scrdata_{ANO_AMOSTRA}.zip"

    if caminho_zip.exists() and not forcar_download:
        tamanho_mb = caminho_zip.stat().st_size / 1024 / 1024
        print(f"Amostra já em disco: {caminho_zip} ({tamanho_mb:.1f} MB)")
        print("Nada foi baixado. Use --forcar-download para rebaixar da fonte.")
        return caminho_zip

    url = config.SCR_URL_TEMPLATE.format(ano=ANO_AMOSTRA)
    print(f"URL: {url}")
    print("Baixando... (o arquivo é grande, pode demorar)")

    try:
        resposta = requests.get(url, timeout=300)
        resposta.raise_for_status()
    except requests.exceptions.RequestException as erro:
        print(f"\nFALHOU: {erro}")
        print(f"Confira se a URL ainda existe em: {config.SCR_PORTAL}")
        return None

    tamanho_mb = len(resposta.content) / 1024 / 1024
    print(f"OK. ZIP baixado: {tamanho_mb:.1f} MB")

    caminho_zip.write_bytes(resposta.content)
    print(f"Salvo em: {caminho_zip}")
    return caminho_zip


def baixar_amostra_scr(forcar_download=False):
    """Baixa o ZIP de um ano do SCR.data e inspeciona o primeiro CSV."""
    separador(f"FONTE 1 — SCR.data ({ANO_AMOSTRA})")

    caminho_zip = obter_zip_do_scr(forcar_download)
    if caminho_zip is None:
        return

    with zipfile.ZipFile(caminho_zip) as z:
        arquivos = z.namelist()
        print(f"\nArquivos dentro do ZIP: {len(arquivos)}")
        for nome in arquivos[:5]:
            print(f"  - {nome}")
        if len(arquivos) > 5:
            print(f"  ... e mais {len(arquivos) - 5}")

        # O ZIP traz um CSV por mês do ano. Inspecionamos o último da
        # lista: além do layout, ele dá a competência mais recente.
        alvo = sorted(arquivos)[-1]
        print(f"\nInspecionando: {alvo}")

        with z.open(alvo) as f:
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

        # `data_base` é a 1ª coluna e é a mesma em todas as linhas de um
        # arquivo mensal (conferido na amostra de 2024). Então a 1ª linha
        # de dados do último arquivo já dá a competência mais recente.
        posicao = colunas.index("data_base") if "data_base" in colunas else 0
        ultima_competencia = linhas[1].split(config.SCR_SEPARADOR)[posicao].strip('"')
        print(f"\nÚltima competência na amostra: {ultima_competencia}")
        print(f"config.ANO_FIM está em {config.ANO_FIM}.")
        if not ultima_competencia.startswith(str(config.ANO_FIM)):
            print("  ATENÇÃO: não batem. Conferir se ANO_FIM precisa ser ajustado")
            print("  (a amostra é de {}, então divergir aqui é esperado".format(ANO_AMOSTRA))
            print("   enquanto a amostra não for do ano mais recente publicado).")

    print("\n--- ANOTAR NO DOCUMENTO (Sprint 1) ---")
    print("  [ ] Decimal é vírgula ou ponto?")
    print("  [ ] carteira_ativa está em reais ou em milhares?")
    print("  [ ] Data de coleta:", "________")


def baixar_amostra_selic():
    """Chama a API do Ipeadata e inspeciona a resposta."""
    separador("FONTE 2 — Selic (Ipeadata)")

    print(f"URL: {config.SELIC_URL}")
    print(f"Série: {config.SELIC_SERIE} — a taxa vem em % AO MÊS, não ao ano.")
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
    # Sem argumento, reaproveita a amostra que já estiver em disco.
    # Com --forcar-download, rebaixa da fonte para conferir se ela mudou.
    forcar = "--forcar-download" in sys.argv

    config.criar_pastas()
    baixar_amostra_scr(forcar)
    baixar_amostra_selic()
    separador("FIM")
    print("Preencha as pendências acima em docs/architecture.md, seção 2.")
