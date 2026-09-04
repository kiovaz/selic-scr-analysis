"""
Configuração central do projeto.

Todo caminho de pasta, URL de fonte e constante de negócio mora aqui.
Nenhum outro arquivo do projeto deve conter caminho ou URL "chumbado".

Referência: seções 2 e 9 de docs/architecture.md
"""

from pathlib import Path

# ---------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------
# __file__ é este arquivo (src/config.py).
# .parent = src/ ; .parent.parent = raiz do projeto.
RAIZ = Path(__file__).parent.parent

DIR_DADOS = RAIZ / "data"
DIR_BRONZE = DIR_DADOS / "raw"        # camada Bronze: dado cru
DIR_SILVER = DIR_DADOS / "processed"  # camada Silver: dado limpo
DIR_GOLD = DIR_DADOS / "final"        # camada Gold: dado pronto para a pergunta
DIR_QUARENTENA = DIR_DADOS / "raw" / "_quarentena"

# ---------------------------------------------------------------------
# Fonte 1 — SCR.data (Banco Central)
# ---------------------------------------------------------------------
SCR_URL_TEMPLATE = "https://www.bcb.gov.br/pda/desig/scrdata_{ano}.zip"
SCR_PORTAL = "https://dadosabertos.bcb.gov.br/dataset/scr_data"
SCR_SEPARADOR = ";"

# Confirmado na Sprint 1, abrindo a amostra de 2024: os CSVs do SCR vêm
# em UTF-8 com BOM (os três primeiros bytes do arquivo são EF BB BF).
# O `-sig` do "utf-8-sig" é justamente o que consome esse BOM — sem ele,
# o nome da primeira coluna viria "\ufeffdata_base" em vez de "data_base".
#
# A ORDEM DESTA LISTA IMPORTA e não pode ser trocada. Quem lê usa o
# primeiro encoding que decodificar sem erro, e "latin-1" mapeia todos os
# 256 bytes possíveis — ele nunca levanta erro, em arquivo nenhum. Se
# vier primeiro, vence sempre, mesmo em arquivo UTF-8, e os acentos viram
# lixo ("Comércio" lido como "ComÃ©rcio").
# Isso não é cosmético: `modalidade` é texto acentuado e o recorte do
# projeto é LIKE 'Financiamentos%'. Encoding errado quebra o filtro.
# Por isso "latin-1" fica por último, como fallback de último recurso.
SCR_ENCODINGS_CANDIDATOS = ["utf-8-sig", "utf-8", "latin-1"]

# Só estas cinco colunas viram Silver. As outras ficam na Bronze.
SCR_COLUNAS_USADAS = [
    "data_base",
    "uf",
    "modalidade",
    "numero_de_operacoes",
    "carteira_ativa",
]

# ---------------------------------------------------------------------
# Fonte 2 — Selic (Ipeadata)
# ---------------------------------------------------------------------
# BM12_TJOVER12 = Taxa Selic acumulada no mês, em % ao mês.
# Atenção: é % ao MÊS, não ao ano.
SELIC_SERIE = "BM12_TJOVER12"
SELIC_URL = (
    "http://www.ipeadata.gov.br/api/odata4/"
    f"ValoresSerie(SERCODIGO='{SELIC_SERIE}')"
)

# ---------------------------------------------------------------------
# Recorte do projeto
# ---------------------------------------------------------------------
# Começamos em jul/2016 porque em jun/2016 o limite de registro das
# operações no SCR caiu de R$ 1.000 para R$ 200. Antes e depois dessa
# data as séries não são comparáveis.
# Referência: seção 2.3 de docs/architecture.md
ANO_INICIO = 2016
MES_INICIO = 7
# Conferido na Sprint 1 (2026-09-03): o ZIP de 2026 existe e responde 200;
# o de 2027 dá 404. Então 2026 é o ano mais recente publicado.
# O arquivo de 2026 é parcial (100,8 MiB contra 167,9 MiB de um ano cheio),
# porque o SCR publica com ~30 dias de defasagem — o ano corrente só tem os
# meses já fechados. Revisar a cada virada de ano.
ANO_FIM = 2026

# Das 13 modalidades do SCR.data, usamos as 8 de financiamento.
PREFIXO_MODALIDADE = "Financiamentos"

# As 27 unidades da federação, para validar a coluna `uf`.
UFS_VALIDAS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]


def criar_pastas():
    """Cria as pastas de dados se ainda não existirem."""
    for pasta in (DIR_BRONZE, DIR_SILVER, DIR_GOLD, DIR_QUARENTENA):
        pasta.mkdir(parents=True, exist_ok=True)
