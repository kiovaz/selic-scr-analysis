"""
Constrói a gold_ml_dataset, a base do modelo de ML (seção 6.1 do
docs/architecture.md).

Pergunta: o crédito desta combinação UF × modalidade vai GANHAR FORÇA no
trimestre que o decisor ainda pode usar?

- Cada linha é "o que se sabia no fim do mês t" (a ORIGEM) para uma
  combinação da coorte.
- Rótulo ganha_forca = 1 quando o saldo cresce MAIS de t+2 a t+5 do que
  cresceu de t−3 a t. A folga de 2 meses existe porque o SCR é publicado
  ~60 dias depois: quando o dado de t chega, t+1 e t+2 já passaram.
- Features: SÓ dados de meses <= t (shift para trás). O shift para frente
  aparece apenas no rótulo. Um teste prova que mexer no futuro não muda as
  features.
- Coorte: só as combinações com todos os meses do recorte (174 de 216).
- Conjuntos: desenvolvimento (até ago/2024), embargo (set/2024–jan/2025,
  fora do modelo avaliado porque o rótulo delas cai no período de teste),
  teste (fev/2025–jan/2026) e producao (t0 = jun/2026, sem rótulo).
"""

import logging

import pandas as pd

from src import config
from src.transformation.silver_scr import _gravar_parquet, meses_do_recorte

logger = logging.getLogger(__name__)

CHAVE = ["uf", "modalidade", "origem"]
# Variáveis da Selic: entram ou saem na comparação "o modelo com e sem a Selic".
FEATURES_SELIC = ["selic_pct", "selic_var_3m", "selic_var_6m"]
FEATURES_CREDITO = ["var_1m", "var_3m", "var_6m", "var_12m", "aceleracao_3m",
                    "rel_3m", "rel_12m", "participacao", "var_participacao_12m"]
FEATURES_NUMERICAS = FEATURES_CREDITO + FEATURES_SELIC
FEATURES_CATEGORICAS = ["uf", "modalidade"]


def _variacao(tabela, meses):
    """Crescimento % de t−meses até t (só olha para trás)."""
    return (tabela / tabela.shift(meses) - 1) * 100


def _mes(ano_mes):
    return pd.Timestamp(ano_mes[0], ano_mes[1], 1)


def definir_coorte(gold):
    """Combinações com todos os meses do recorte (as demais têm buracos)."""
    meses = gold.groupby(["uf", "modalidade"]).size()
    coorte = meses[meses == meses_do_recorte()].index
    excluidas = [{"uf": uf, "modalidade": mod, "meses_presentes": int(n)}
                 for (uf, mod), n in meses[meses < meses_do_recorte()].items()]
    return coorte, excluidas


def calcular_rotulo(volume):
    """
    ganha_forca por (origem, combinação): crescimento de t+2 a t+5 maior que o
    de t−3 a t. Vazio quando t+5 ainda não existe.
    """
    folga, h = config.FOLGA_PUBLICACAO_MESES, config.HORIZONTE_MESES
    futuro = (volume.shift(-(folga + h)) / volume.shift(-folga) - 1) * 100
    passado = _variacao(volume, 3)
    return (futuro > passado).astype("float").where(futuro.notna() & passado.notna())


def calcular_features(volume, nacional_por_combinacao, selic):
    """
    Features de cada (origem, combinação), todas com meses <= origem.
    Devolve um dicionário {nome: tabela larga (meses × combinações)}.
    """
    f = {f"var_{k}m": _variacao(volume, k) for k in (1, 3, 6, 12)}
    f["aceleracao_3m"] = f["var_3m"] - f["var_3m"].shift(3)
    for k in (3, 12):
        f[f"rel_{k}m"] = f[f"var_{k}m"] - _variacao(nacional_por_combinacao, k)
    f["participacao"] = volume / nacional_por_combinacao
    f["var_participacao_12m"] = f["participacao"] - f["participacao"].shift(12)
    # Selic: a mesma para todas as combinações do mês.
    for nome, serie in {"selic_pct": selic, "selic_var_3m": selic - selic.shift(3),
                        "selic_var_6m": selic - selic.shift(6)}.items():
        f[nome] = pd.DataFrame({c: serie for c in volume.columns}, index=volume.index).set_axis(volume.columns, axis=1)
    return f


def marcar_conjunto(origens, tem_rotulo, t0):
    """desenvolvimento / embargo / teste / producao (ou None = fora da base)."""
    fim_treino, inicio_teste = _mes(config.FIM_TREINO_FINAL), _mes(config.INICIO_TESTE)
    conjunto = pd.Series(None, index=origens.index, dtype="object")
    conjunto[tem_rotulo & (origens <= fim_treino)] = "desenvolvimento"
    conjunto[tem_rotulo & (origens > fim_treino) & (origens < inicio_teste)] = "embargo"
    conjunto[tem_rotulo & (origens >= inicio_teste)] = "teste"
    conjunto[origens == t0] = "producao"
    return conjunto


def montar_base(gold):
    """Monta a base (DataFrame longo) a partir da Gold. Devolve (base, excluidas)."""
    gold = gold.assign(ano_mes=pd.to_datetime(gold["ano_mes"]))
    coorte, excluidas = definir_coorte(gold)

    todas = gold.pivot_table(index="ano_mes", columns=["uf", "modalidade"], values="volume_rs").asfreq("MS")
    volume = todas[coorte]
    # Nacional da modalidade = soma de TODAS as UFs (é o "mercado").
    nacional = gold.groupby(["ano_mes", "modalidade"])["volume_rs"].sum().unstack().asfreq("MS")
    nacional_por_combinacao = pd.DataFrame({c: nacional[c[1]] for c in volume.columns},
                                           index=volume.index).set_axis(volume.columns, axis=1)
    selic = gold.drop_duplicates("ano_mes").set_index("ano_mes")["selic_pct"].sort_index().asfreq("MS")

    tabelas = calcular_features(volume, nacional_por_combinacao, selic)
    tabelas["ganha_forca"] = calcular_rotulo(volume)
    tabelas["volume_origem"] = volume          # peso da AUC ponderada (não é feature)

    base = pd.concat({nome: t.stack(["uf", "modalidade"], future_stack=True) for nome, t in tabelas.items()},
                     axis=1).reset_index().rename(columns={"ano_mes": "origem"})

    # Só origens com o histórico completo (12 meses para trás).
    base = base.dropna(subset=FEATURES_NUMERICAS)
    t0 = gold["ano_mes"].max()
    base["conjunto"] = marcar_conjunto(base["origem"], base["ganha_forca"].notna(), t0)
    base = base.dropna(subset=["conjunto"])
    base = base[CHAVE + FEATURES_NUMERICAS + ["volume_origem", "ganha_forca", "conjunto"]]
    return base.sort_values(["origem", "uf", "modalidade"]).reset_index(drop=True), excluidas


def construir_gold_ml_dataset():
    """Lê a Gold, monta a base e grava gold_ml_dataset.parquet. Devolve (base, excluidas)."""
    if not config.ARQUIVO_GOLD.exists():
        logger.error("Gold não encontrada. Rode a Gold antes do ML.")
        return None, None
    base, excluidas = montar_base(pd.read_parquet(config.ARQUIVO_GOLD))
    _gravar_parquet(base, config.ARQUIVO_ML_DATASET)
    logger.info(f"gold_ml_dataset: {len(base)} linhas, {base['conjunto'].value_counts().to_dict()}; "
                f"{len(excluidas)} combinações fora da coorte.")
    return base, excluidas
