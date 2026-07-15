"""
stats_tests.py — escolhe o teste estatístico certo pros dados que a gente tem
(em vez de aplicar ANOVA cegamente), e faz comparações par-a-par com correção
de múltiplas comparações.

Unidade de análise: dia. Cada grupo vira uma série de "lucro diário"
(comissão - cashback). Isso é uma limitação real (não temos dado por usuário)
e é reportada explicitamente nos avisos, não escondida.
"""
from itertools import combinations
import math
import numpy as np
from scipy import stats


def _cohend(a, b):
    na, nb = len(a), len(b)
    pooled_std = math.sqrt(((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2))
    if pooled_std == 0:
        return 0.0
    return (np.mean(a) - np.mean(b)) / pooled_std


def _rank_biserial(u_stat, na, nb):
    return 1 - (2 * u_stat) / (na * nb)


def run_statistical_tests(df, cfg: dict, metric_col: str = "lucro", metric_label: str = "Lucro (comissão - cashback)") -> dict:
    alpha = cfg["statistics"]["alpha"]
    normality_alpha = cfg["statistics"]["normality_alpha"]

    groups = sorted(df["grupo"].unique())
    # dropna: métricas como ROI diário podem ter dias indefinidos (cashback=0),
    # que já foram registrados como aviso de qualidade de dado em outro lugar.
    series = {g: sub[metric_col].dropna().to_numpy() for g, sub in df.groupby("grupo")}

    # --- normalidade por grupo (Shapiro-Wilk) ---
    normality = {}
    for g, vals in series.items():
        if len(vals) < 3 or float(vals.std(ddof=0)) == 0.0:
            # amostra pequena demais, ou grupo com variância zero (ex: comissão == cashback
            # todo dia, um empate exato) -> Shapiro não é aplicável/informativo aqui
            normality[g] = {"applicable": False, "p_value": None, "normal": None}
            continue
        stat, p = stats.shapiro(vals)
        normality[g] = {"applicable": True, "p_value": round(float(p), 4), "normal": bool(p > normality_alpha)}

    all_normal = all(v["normal"] for v in normality.values() if v["applicable"])
    any_inapplicable = any(not v["applicable"] for v in normality.values())
    use_parametric = all_normal and not any_inapplicable

    homogeneity = None
    if use_parametric and len(groups) > 2:
        lev_stat, lev_p = stats.levene(*series.values())
        homogeneity = {"statistic": round(float(lev_stat), 4), "p_value": round(float(lev_p), 4)}
        if lev_p <= alpha:
            use_parametric = False  # variâncias diferentes -> mais seguro ir de método não-paramétrico

    # --- teste global ---
    if len(groups) == 2:
        g1, g2 = groups
        if use_parametric:
            method = "welch_t_test"
            t_stat, p_val = stats.ttest_ind(series[g1], series[g2], equal_var=False)
            overall = {"method": method, "statistic": round(float(t_stat), 4), "p_value": round(float(p_val), 6)}
        else:
            method = "mann_whitney_u"
            u_stat, p_val = stats.mannwhitneyu(series[g1], series[g2], alternative="two-sided")
            overall = {"method": method, "statistic": round(float(u_stat), 4), "p_value": round(float(p_val), 6)}
    else:
        if use_parametric:
            method = "one_way_anova"
            f_stat, p_val = stats.f_oneway(*series.values())
            # eta-squared (tamanho de efeito da ANOVA)
            grand_mean = np.concatenate(list(series.values())).mean()
            ss_between = sum(len(v) * (v.mean() - grand_mean) ** 2 for v in series.values())
            ss_total = sum(((v - grand_mean) ** 2).sum() for v in series.values())
            eta_sq = ss_between / ss_total if ss_total else 0.0
            overall = {
                "method": method, "statistic": round(float(f_stat), 4),
                "p_value": round(float(p_val), 6), "eta_squared": round(float(eta_sq), 4),
            }
        else:
            method = "kruskal_wallis"
            h_stat, p_val = stats.kruskal(*series.values())
            overall = {"method": method, "statistic": round(float(h_stat), 4), "p_value": round(float(p_val), 6)}

    # --- comparações par-a-par com correção de Bonferroni ---
    pairs = list(combinations(groups, 2))
    n_comparisons = max(len(pairs), 1)
    pairwise = {}
    for g1, g2 in pairs:
        a, b = series[g1], series[g2]
        if use_parametric:
            t_stat, p_raw = stats.ttest_ind(a, b, equal_var=False)
            effect = _cohend(a, b)
            test_used = "welch_t_test"
        else:
            u_stat, p_raw = stats.mannwhitneyu(a, b, alternative="two-sided")
            effect = _rank_biserial(u_stat, len(a), len(b))
            test_used = "mann_whitney_u"
        p_adj = min(p_raw * n_comparisons, 1.0)
        pairwise[f"{g1} vs {g2}"] = {
            "test": test_used,
            "p_value_raw": round(float(p_raw), 6),
            "p_value_bonferroni": round(float(p_adj), 6),
            "significant": bool(p_adj < alpha),
            "effect_size": round(float(effect), 4),
            "media_diaria_por_grupo": {g1: round(float(a.mean()), 4), g2: round(float(b.mean()), 4)},
        }

    return {
        "metrica_testada": metric_col,
        "unidade_de_analise": f"dia (métrica testada: {metric_label})",
        "normalidade_por_grupo": normality,
        "homogeneidade_variancia_levene": homogeneity,
        "metodo_escolhido_motivo": (
            "paramétrico (dados compatíveis com normalidade em todos os grupos)"
            if use_parametric else
            "não-paramétrico (pelo menos um grupo não passou no teste de normalidade "
            "de Shapiro-Wilk, ou variâncias muito diferentes entre grupos, ou n pequeno demais)"
        ),
        "teste_global": overall,
        "comparacoes_par_a_par": pairwise,
        "alpha": alpha,
    }
