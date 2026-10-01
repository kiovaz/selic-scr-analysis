"""
Associação entre a variação do crédito e a variação da Selic (seção 5.4 do
docs/architecture.md).

Regras seguidas:
- Compara VARIAÇÕES, nunca níveis (níveis com tendência dão correlação espúria).
- Testa a Selic defasada: o crédito do mês t contra a variação da Selic do mês
  t − k, para k de 0 a DEFASAGEM_MAXIMA (6) — o crédito reage com atraso.
- Roda separadamente por modalidade.
- Medida principal: correlação de SPEARMAN (compara a ordem dos valores; é
  menos sensível a meses extremos). A de Pearson vai ao lado para comparação.
- Muitos testes ao mesmo tempo dão resultados "significativos" por acaso: os
  valores-p são ajustados por Benjamini-Hochberg, e só é significativo o que
  tem valor-p AJUSTADO < 0,05.
- Relata ASSOCIAÇÃO, nunca causa.

Dois níveis (decisão do grupo):
1. Brasil por modalidade: soma as 27 UFs em cada mês e mede as 7 defasagens.
2. UF × modalidade: cada combinação medida na defasagem de maior associação
   da sua modalidade no nível Brasil (escolher a melhor defasagem combinação
   por combinação seria escolher o resultado a dedo), com amostra mínima.
"""

import logging
import warnings

import matplotlib

matplotlib.use("Agg")  # gera PNG sem abrir janela (roda em servidor e no CI)
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from scipy import stats  # noqa: E402

from src import config  # noqa: E402
from src.transformation.silver_scr import _gravar_parquet  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Cores (paleta validada para daltonismo: azul <-> vermelho, cinza no meio)
# ---------------------------------------------------------------------
AZUL = "#256abf"        # correlação negativa: Selic sobe, crédito cresce menos
VERMELHO = "#e34948"    # correlação positiva
NEUTRO = "#f0efec"      # zero: nenhuma associação
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
TINTA_APAGADA = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"
ESCALA_DIVERGENTE = LinearSegmentedColormap.from_list("azul_vermelho", [AZUL, NEUTRO, VERMELHO])


def nome_curto(modalidade):
    """'Financiamentos imobiliários' -> 'Imobiliários' (para caber nos gráficos)."""
    if modalidade.strip() == config.PREFIXO_MODALIDADE:
        return "Financiamentos (geral)"
    resto = modalidade[len(config.PREFIXO_MODALIDADE):].split("(")[0].strip()
    return resto[:1].upper() + resto[1:]


# ---------------------------------------------------------------------
# Estatística
# ---------------------------------------------------------------------

def _correlacionar(x, y):
    """
    Spearman e Pearson entre duas séries, só nos meses em que as duas existem.
    Devolve (n, spearman, p_valor, pearson). Com menos de 3 pontos, ou uma
    série constante, a correlação não existe e vem vazia (NaN).
    """
    validos = x.notna() & y.notna()
    n = int(validos.sum())
    if n < 3:
        return n, np.nan, np.nan, np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")      # série constante: scipy avisa e devolve NaN
        rho, p = stats.spearmanr(x[validos], y[validos])
        r, _ = stats.pearsonr(x[validos], y[validos])
    return n, float(rho), float(p), float(r)


def _ajustar_p(tabela):
    """Benjamini-Hochberg nos valores-p existentes; os vazios continuam vazios."""
    tabela["p_ajustado"] = np.nan
    existe = tabela["p_valor"].notna()
    if existe.any():
        tabela.loc[existe, "p_ajustado"] = stats.false_discovery_control(
            tabela.loc[existe, "p_valor"].to_numpy(), method="bh")
    tabela["significativo"] = tabela["p_ajustado"] < 0.05
    return tabela


def variacao_da_selic(gold):
    """Série mensal contínua de var_selic_pp (a mesma para todas as linhas do mês)."""
    selic = gold.drop_duplicates("ano_mes").assign(ano_mes=lambda d: pd.to_datetime(d["ano_mes"]))
    return selic.set_index("ano_mes")["var_selic_pp"].sort_index().asfreq("MS")


def analise_brasil(gold):
    """
    Nível Brasil por modalidade: soma o volume das 27 UFs em cada mês, calcula
    a variação nacional e mede a associação com a variação da Selic de k meses
    antes (k = 0..DEFASAGEM_MAXIMA). Uma UF sem linha no mês soma zero: não
    havia operação (limitação 10 do architecture.md).
    """
    var_selic = variacao_da_selic(gold)
    gold = gold.assign(ano_mes=pd.to_datetime(gold["ano_mes"]))
    linhas = []
    for modalidade, grupo in gold.groupby("modalidade"):
        volume = grupo.groupby("ano_mes")["volume_rs"].sum().asfreq("MS")   # mês faltando -> NaN
        var_volume = volume.pct_change(fill_method=None) * 100
        for k in range(config.DEFASAGEM_MAXIMA + 1):
            selic_k = var_selic.shift(k).reindex(var_volume.index)
            n, rho, p, r = _correlacionar(var_volume, selic_k)
            linhas.append({"modalidade": modalidade, "defasagem_meses": k, "n_meses": n,
                           "spearman": rho, "pearson": r, "p_valor": p})
    return _ajustar_p(pd.DataFrame(linhas))


def defasagem_de_maior_associacao(brasil):
    """Para cada modalidade, o k com maior |Spearman| no nível Brasil."""
    com_valor = brasil.dropna(subset=["spearman"])
    idx = com_valor["spearman"].abs().groupby(com_valor["modalidade"]).idxmax()
    return com_valor.loc[idx].set_index("modalidade")["defasagem_meses"].to_dict()


def analise_uf(gold, brasil):
    """
    Nível UF × modalidade: cada combinação medida na defasagem k* da sua
    modalidade (nível Brasil). Só linhas com mês anterior e as duas variações.
    Combinações com menos de MESES_MINIMOS_CORRELACAO meses válidos ficam
    sem correlação (amostra insuficiente).
    """
    k_estrela = defasagem_de_maior_associacao(brasil)
    var_selic = variacao_da_selic(gold)
    gold = gold.assign(ano_mes=pd.to_datetime(gold["ano_mes"]))
    linhas = []
    for (uf, modalidade), grupo in gold.groupby(["uf", "modalidade"]):
        k = k_estrela.get(modalidade)
        validas = grupo[grupo["tem_mes_anterior"] & grupo["var_volume_pct"].notna()]
        var_volume = validas.set_index("ano_mes")["var_volume_pct"]
        selic_k = var_selic.shift(k).reindex(var_volume.index) if k is not None else var_volume * np.nan
        n, rho, p, r = _correlacionar(var_volume, selic_k)
        insuficiente = n < config.MESES_MINIMOS_CORRELACAO
        if insuficiente:
            rho = p = r = np.nan
        linhas.append({"uf": uf, "modalidade": modalidade, "defasagem_meses": k, "n_meses": n,
                       "amostra_insuficiente": insuficiente, "spearman": rho, "pearson": r, "p_valor": p})
    return _ajustar_p(pd.DataFrame(linhas))


# ---------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------

def _estilo_eixo(ax):
    """Grade e eixos discretos: o dado é o protagonista."""
    ax.set_facecolor(SUPERFICIE)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(EIXO)
    ax.tick_params(colors=TINTA_APAGADA, labelsize=8, length=0)
    ax.grid(axis="y", color=GRADE, linewidth=0.6)
    ax.set_axisbelow(True)


def grafico_por_modalidade(brasil, destino):
    """
    Primeiro gráfico: um painel por modalidade (small multiples), barras com a
    correlação de Spearman para cada defasagem de 0 a 6 meses. Cor = sinal
    (azul negativa, vermelho positiva); barra cheia = significativa (valor-p
    ajustado < 0,05); barra clara = não significativa.
    """
    modalidades = sorted(brasil["modalidade"].unique(), key=nome_curto)
    fig, eixos = plt.subplots(2, 4, figsize=(13, 6.2), sharey=True, facecolor=SUPERFICIE)
    for ax, modalidade in zip(eixos.flat, modalidades):
        dados = brasil[brasil["modalidade"] == modalidade].sort_values("defasagem_meses")
        cores = [AZUL if v < 0 else VERMELHO for v in dados["spearman"].fillna(0)]
        alfas = [1.0 if s else 0.3 for s in dados["significativo"]]
        for x, y, cor, alfa in zip(dados["defasagem_meses"], dados["spearman"].fillna(0), cores, alfas):
            ax.bar(x, y, width=0.62, color=cor, alpha=alfa, edgecolor=SUPERFICIE, linewidth=2)
        # rótulo só no ponto de maior associação (rótulos seletivos)
        pico = dados.loc[dados["spearman"].abs().idxmax()] if dados["spearman"].notna().any() else None
        if pico is not None:
            y = pico["spearman"]
            ax.annotate(f"{y:+.2f}", (pico["defasagem_meses"], y), ha="center",
                        va="bottom" if y >= 0 else "top", xytext=(0, 3 if y >= 0 else -3),
                        textcoords="offset points", fontsize=8, color=TINTA)
        ax.axhline(0, color=EIXO, linewidth=1)
        ax.set_ylim(-1, 1)
        ax.set_xticks(range(config.DEFASAGEM_MAXIMA + 1))
        ax.set_title(nome_curto(modalidade), fontsize=10, color=TINTA, loc="left")
        _estilo_eixo(ax)
    for ax in eixos[1]:
        ax.set_xlabel("defasagem (meses)", fontsize=8, color=TINTA_SECUNDARIA)
    for ax in eixos[:, 0]:
        ax.set_ylabel("correlação de Spearman", fontsize=8, color=TINTA_SECUNDARIA)

    fig.suptitle("Variação do crédito × variação da Selic k meses antes — Brasil, por modalidade",
                 x=0.01, ha="left", fontsize=12, color=TINTA)
    legenda = [plt.Rectangle((0, 0), 1, 1, color=AZUL), plt.Rectangle((0, 0), 1, 1, color=VERMELHO),
               plt.Rectangle((0, 0), 1, 1, color=TINTA_APAGADA, alpha=0.3)]
    fig.legend(legenda, ["negativa, significativa", "positiva, significativa", "não significativa (cor clara)"],
               loc="upper right", ncol=3, fontsize=8, frameon=False, labelcolor=TINTA_SECUNDARIA)
    fig.text(0.01, 0.005, "Associação, não causa. Significativa = valor-p ajustado (Benjamini-Hochberg) < 0,05. "
             f"Volume = saldo somado das 27 UFs; jul/2016–jun/2026.", fontsize=7.5, color=TINTA_APAGADA)
    fig.tight_layout(rect=(0, 0.03, 1, 0.93))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


def mapa_de_calor(uf_modalidade, destino):
    """
    Mapa de calor UF × modalidade: cor = Spearman na defasagem k* da modalidade
    (escala divergente azul-cinza-vermelho centrada em 0). Células com amostra
    insuficiente: cinza hachurado. Só as significativas levam o número.
    """
    ufs = sorted(uf_modalidade["uf"].unique())
    modalidades = sorted(uf_modalidade["modalidade"].unique(), key=nome_curto)
    matriz = uf_modalidade.pivot(index="uf", columns="modalidade", values="spearman").reindex(index=ufs, columns=modalidades)
    signif = uf_modalidade.pivot(index="uf", columns="modalidade", values="significativo").reindex(index=ufs, columns=modalidades)
    k_por_mod = uf_modalidade.drop_duplicates("modalidade").set_index("modalidade")["defasagem_meses"]

    fig, ax = plt.subplots(figsize=(10, 11), facecolor=SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    imagem = ax.imshow(matriz.to_numpy(dtype=float), cmap=ESCALA_DIVERGENTE, vmin=-1, vmax=1, aspect="auto")
    for i in range(len(ufs)):
        for j in range(len(modalidades)):
            valor = matriz.iat[i, j]
            if pd.isna(valor):
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=NEUTRO,
                                           hatch="///", edgecolor=EIXO, linewidth=0))
            elif signif.iat[i, j] is True or signif.iat[i, j] == True:  # noqa: E712
                ax.text(j, i, f"{valor:+.2f}", ha="center", va="center", fontsize=7,
                        color="white" if abs(valor) > 0.5 else TINTA)
    # linhas finas da cor da superfície separando as células
    ax.set_xticks(np.arange(-0.5, len(modalidades)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(ufs)), minor=True)
    ax.grid(which="minor", color=SUPERFICIE, linewidth=2)
    ax.tick_params(which="both", length=0, colors=TINTA_SECUNDARIA, labelsize=8)
    ax.set_xticks(range(len(modalidades)))
    ax.set_xticklabels([f"{nome_curto(m)}\n(k = {k_por_mod.get(m)})" for m in modalidades],
                       rotation=35, ha="right")
    ax.set_yticks(range(len(ufs)))
    ax.set_yticklabels(ufs)
    for lado in ax.spines.values():
        lado.set_visible(False)
    barra = fig.colorbar(imagem, ax=ax, fraction=0.03, pad=0.02)
    barra.set_label("correlação de Spearman", fontsize=8, color=TINTA_SECUNDARIA)
    barra.ax.tick_params(labelsize=7, colors=TINTA_APAGADA)
    barra.outline.set_visible(False)
    ax.set_title("Onde o crédito acompanha a Selic — UF × modalidade\n"
                 "(variação do volume × variação da Selic k meses antes)",
                 loc="left", fontsize=12, color=TINTA)
    fig.text(0.01, 0.005, "Número escrito = significativo (valor-p ajustado < 0,05). Hachurado = menos de "
             f"{config.MESES_MINIMOS_CORRELACAO} meses válidos. Associação, não causa.",
             fontsize=7.5, color=TINTA_APAGADA)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150, facecolor=SUPERFICIE)
    plt.close(fig)


# ---------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------

def executar_analise():
    """Roda os dois níveis sobre a Gold, grava as tabelas e as duas figuras."""
    if not config.ARQUIVO_GOLD.exists():
        logger.error("Gold não encontrada. Rode a Gold antes da análise.")
        return None, None
    gold = pd.read_parquet(config.ARQUIVO_GOLD)
    brasil = analise_brasil(gold)
    uf_modalidade = analise_uf(gold, brasil)
    _gravar_parquet(brasil, config.ARQUIVO_ANALISE_BRASIL)
    _gravar_parquet(uf_modalidade, config.ARQUIVO_ANALISE_UF)
    grafico_por_modalidade(brasil, config.DIR_FIGURAS / "correlacao_por_modalidade.png")
    mapa_de_calor(uf_modalidade, config.DIR_FIGURAS / "mapa_calor_uf_modalidade.png")
    return brasil, uf_modalidade
