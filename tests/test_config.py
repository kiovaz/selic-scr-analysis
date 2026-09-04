"""
Testes da configuração do projeto.

Sprint 1: são simples de propósito. Eles existem para que o GitHub Actions
tenha algo para rodar desde o primeiro dia, e para pegar erro de digitação
em constante que o resto do pipeline vai usar.
"""

from src import config


def test_existem_27_ufs():
    """O Brasil tem 26 estados mais o Distrito Federal."""
    assert len(config.UFS_VALIDAS) == 27


def test_ufs_nao_tem_duplicata():
    assert len(config.UFS_VALIDAS) == len(set(config.UFS_VALIDAS))


def test_ufs_tem_duas_letras_maiusculas():
    for uf in config.UFS_VALIDAS:
        assert len(uf) == 2
        assert uf.isupper()


def test_url_do_scr_aceita_o_ano():
    url = config.SCR_URL_TEMPLATE.format(ano=2024)
    assert "2024" in url
    assert url.startswith("https://")


def test_url_da_selic_tem_o_codigo_da_serie():
    assert config.SELIC_SERIE in config.SELIC_URL


def test_recorte_comeca_depois_da_quebra_de_serie():
    """
    A quebra de série do SCR é em jun/2016 (o limite de registro das
    operações caiu de R$ 1.000 para R$ 200). O recorte precisa começar
    depois disso.
    """
    assert (config.ANO_INICIO, config.MES_INICIO) >= (2016, 7)


def test_colunas_usadas_do_scr():
    assert len(config.SCR_COLUNAS_USADAS) == 5
    assert "carteira_ativa" in config.SCR_COLUNAS_USADAS
    assert "numero_de_operacoes" in config.SCR_COLUNAS_USADAS
