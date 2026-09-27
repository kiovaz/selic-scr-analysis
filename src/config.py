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

# Amostras baixadas à mão na Sprint 1, só para diagnóstico (scripts/baixar_amostras.py).
DIR_AMOSTRAS = DIR_BRONZE / "_amostras"
# ZIPs anuais do SCR baixados pelo loader da Bronze. Ficam em disco para não
# baixar ~170 MB de novo a cada execução.
DIR_DOWNLOADS_SCR = DIR_BRONZE / "_downloads"
# Tabelas de controle da ingestão: registram o que já foi gravado na Bronze,
# para que rodar o pipeline de novo não duplique nada (seção 3.2).
DIR_CONTROLE = DIR_BRONZE / "_controle"
ARQUIVO_CONTROLE_SCR = DIR_CONTROLE / "controle_scr.json"      # versão de cada ZIP e de cada CSV
ARQUIVO_CONTROLE_SELIC = DIR_CONTROLE / "controle_selic.json"  # watermark da Selic

# Saídas da Silver (seção 4.2). São pequenas (até ~26 mil e 120 linhas), por
# isso um Parquet único por tabela. O relatório registra quantas linhas
# saíram em cada etapa (filtros de escopo e quarentena).
ARQUIVO_SILVER_SCR = DIR_SILVER / "silver_scr.parquet"
ARQUIVO_SILVER_SELIC = DIR_SILVER / "silver_selic.parquet"
ARQUIVO_RELATORIO_SILVER = DIR_SILVER / "_relatorio_silver.json"

# Saídas da Gold e da análise (seções 5.3 e 5.4).
ARQUIVO_GOLD = DIR_GOLD / "gold_credito_selic.parquet"
ARQUIVO_ANALISE_BRASIL = DIR_GOLD / "analise_brasil_modalidade.parquet"
ARQUIVO_ANALISE_UF = DIR_GOLD / "analise_uf_modalidade.parquet"
ARQUIVO_RELATORIO_GOLD = DIR_GOLD / "_relatorio_gold.json"
# Gráficos da análise: ficam em docs/ (e vão para o Git) porque são entregáveis.
DIR_FIGURAS = RAIZ / "docs" / "figuras"

# Regras da análise (seção 5.4).
# O crédito reage com atraso aos juros: testamos a Selic de 0 a 6 meses antes.
DEFASAGEM_MAXIMA = 6
# Uma combinação UF × modalidade precisa de pelo menos 2 anos de meses válidos
# para a correlação ser calculada; abaixo disso ela é instável demais.
MESES_MINIMOS_CORRELACAO = 24

# ---------------------------------------------------------------------
# Fonte 1 — SCR.data (Banco Central)
# ---------------------------------------------------------------------
SCR_URL_TEMPLATE = "https://www.bcb.gov.br/pda/desig/scrdata_{ano}.zip"
SCR_PORTAL = "https://dadosabertos.bcb.gov.br/dataset/scr_data"
SCR_SEPARADOR = ";"
# Separador decimal dos números do SCR ("1234,56"), confirmado na Sprint 1.
# Usado pela Silver para converter carteira_ativa em número.
SCR_DECIMAL = ","

# Nome do arquivo ZIP em disco: o mesmo que o BCB publica na URL.
# O loader e o script de amostras usam este nome, então um ZIP baixado por
# um pode ser reaproveitado pelo outro (basta copiar entre as pastas).
SCR_NOME_ZIP = "scrdata_{ano}.zip"

# Quantas linhas do CSV são lidas por vez. Um CSV mensal tem ~300 mil linhas;
# ler em blocos evita carregar o arquivo inteiro na memória.
SCR_TAMANHO_BLOCO = 200_000

# Tempo limite do download do ZIP, em segundos: (conectar, ler).
# O "ler" é o tempo máximo SEM receber nenhum byte, não o tempo total do
# download — por isso 300 s é folgado mesmo para um ZIP de 170 MB.
# Sem timeout, uma conexão que para de responder trava o pipeline para sempre.
TIMEOUT_DOWNLOAD_SCR = (10, 300)

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

# Só estas cinco colunas viram Silver. A Bronze guarda TODAS as colunas do
# CSV, como texto (seção 4.1 do architecture.md); o corte é feito na Silver.
# O loader usa esta lista só para conferir se o CSV serve ao projeto: CSV sem
# alguma delas é rejeitado inteiro, com log.
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
# BM366_TJOVER366 = Taxa Selic META, fixada pelo Copom, em % AO ANO.
# Série diária (dias corridos); a Silver usa o valor do ÚLTIMO dia de cada mês.
#
# Até 2026-09-27 o projeto usava a BM12_TJOVER12 (Selic acumulada no mês, em
# % ao mês). Ela foi trocada porque varia com o número de dias úteis do mês:
# em mar/2026 ela subiu (1,00 -> 1,21 % a.m.) enquanto o Copom CORTOU a meta
# (15,00 -> 14,75 % a.a.). Detalhes na seção 2.2 do architecture.md.
SELIC_SERIE = "BM366_TJOVER366"
SELIC_UNIDADE = "% ao ano"
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
# Fim do recorte: junho/2026. De jul/2016 a jun/2026 são 120 meses —
# exatamente 10 anos, todos já fechados e publicados nas duas bases.
# O fim é FIXO de propósito: assim o resultado não muda a cada nova
# publicação mensal do BCB (decisão do grupo, seção 2.3 do architecture.md).
# ANO_FIM também diz até que ano o loader baixa ZIPs do SCR; a Bronze guarda
# o ano de 2026 inteiro e o corte em junho é feito na Silver.
ANO_FIM = 2026
MES_FIM = 6

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
