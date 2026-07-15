"""
decision.py — combina significância estatística + magnitude do efeito de
negócio + qualidade dos dados numa decisão acionável.

Duas mudanças importantes em relação à v1:
  1. A "métrica-alvo" (o que significa "vencer") é um parâmetro, não uma
     conta fixa em lucro. Growth raramente otimiza uma métrica só — às vezes
     o objetivo é lucro, às vezes ROI (eficiência de capital), às vezes
     volume de compradores (aquisição). O agente de IA pergunta isso ao
     usuário quando não está claro (ver CLAUDE.md) e passa via --metrica-alvo.
  2. A decisão não é só uma string binária ESCALAR/NÃO. Ela é reportada em
     3 dimensões — confiança (estatística), impacto financeiro (magnitude
     prática) e risco (qualidade do dado por trás) — porque um "escalar"
     com risco alto e impacto pequeno pede uma conversa diferente de um
     "escalar" com risco baixo e impacto grande, mesmo com a mesma palavra.
"""
from .metrics import METRIC_OPTIONS


def _classificar_impacto(effect_pct, cfg):
    if effect_pct is None:
        return "Indeterminado"
    if effect_pct >= cfg["decision"]["impacto_alto_pct"]:
        return "Alto"
    if effect_pct >= cfg["decision"]["impacto_medio_pct"]:
        return "Médio"
    return "Baixo"


def _classificar_risco(significant_vs_all, n_warnings, has_small_sample):
    if not significant_vs_all or has_small_sample:
        return "Alto"
    if n_warnings > 0:
        return "Médio"
    return "Baixo"


def decide(group_metrics: dict, stats_result: dict, issues: list, cfg: dict, metrica_alvo: str = None) -> dict:
    alpha = cfg["statistics"]["alpha"]
    min_effect_pct = cfg["statistics"]["min_effect_pct_recommended"]
    metrica_alvo = metrica_alvo or cfg["decision"]["metrica_alvo_default"]

    if metrica_alvo not in METRIC_OPTIONS:
        raise ValueError(
            f"metrica_alvo '{metrica_alvo}' desconhecida. Opções: {list(METRIC_OPTIONS.keys())}"
        )
    metric_spec = METRIC_OPTIONS[metrica_alvo]
    total_key = metric_spec["total_key"]
    daily_key = metric_spec["daily_key"]

    # 1) vencedor de negócio segundo a métrica-alvo escolhida
    business_winner = max(group_metrics.items(), key=lambda kv: kv[1][total_key])[0]
    ranked = sorted(group_metrics.items(), key=lambda kv: kv[1][total_key], reverse=True)
    runner_up = ranked[1][0] if len(ranked) > 1 else None

    # 2) o vencedor é estatisticamente melhor que TODOS os outros grupos?
    #    (o teste estatístico em stats_result já foi rodado na série diária
    #     correspondente a essa mesma métrica-alvo — ver main.py)
    pairwise = stats_result["comparacoes_par_a_par"]
    comparisons_vs_winner = {
        k: v for k, v in pairwise.items()
        if k.startswith(f"{business_winner} vs") or k.endswith(f"vs {business_winner}")
    }
    significant_vs_all = all(v["significant"] for v in comparisons_vs_winner.values()) if comparisons_vs_winner else False

    # 3) magnitude prática do efeito (valor médio/dia do vencedor vs 2º colocado, na métrica-alvo)
    effect_pct = None
    effect_abs = None
    runner_is_breakeven_or_worse = False
    if runner_up is not None:
        winner_val = group_metrics[business_winner][daily_key]
        runner_val = group_metrics[runner_up][daily_key]
        if winner_val == winner_val and runner_val == runner_val:  # not NaN
            effect_abs = round(winner_val - runner_val, 4)
            if runner_val not in (0, None):
                effect_pct = round((winner_val - runner_val) / abs(runner_val) * 100, 2)
            elif runner_val == 0 and winner_val > 0:
                runner_is_breakeven_or_worse = bool(True)

    practically_significant = bool(
        (effect_pct is not None and effect_pct >= min_effect_pct)
        or runner_is_breakeven_or_worse
    )

    # 4) severidade dos avisos de qualidade de dado
    n_warnings = sum(1 for i in issues if i["severity"] == "warning")
    has_small_sample = any(i["code"] == "small_sample" for i in issues)
    has_negative_business = all(m["lucro_total"] < 0 for m in group_metrics.values())

    # 5) as 3 dimensões da decisão — sempre calculadas, independente da recomendação final
    confianca = "Alta" if (significant_vs_all and n_warnings == 0) else (
        "Média" if significant_vs_all else "Baixa"
    )
    impacto_financeiro = "Alto" if runner_is_breakeven_or_worse else _classificar_impacto(effect_pct, cfg)
    risco = _classificar_risco(significant_vs_all, n_warnings, has_small_sample)

    # 6) recomendação (a "palavra final"), construída em cima das 3 dimensões
    if has_negative_business:
        recommendation = "REVISAR_ECONOMIA_DO_TESTE"
        headline = (
            f"Nenhuma variante é lucrativa: todos os grupos gastam mais em cashback do que "
            f"geram em comissão. Escalar qualquer variante nesse estado aumenta prejuízo. "
            f"Recomenda-se revisar o % de cashback antes de pensar em escalar."
        )

    elif significant_vs_all and practically_significant:
        recommendation = f"ESCALAR_{business_winner.upper().replace(' ', '_')}"
        efeito_txt = (
            f"{effect_pct:+.1f}% vs. 2º colocado" if effect_pct is not None
            else f"2º colocado empata comissão=cashback (métrica zero); '{business_winner}' é a "
                 f"única variante positiva"
        )
        headline = (
            f"'{business_winner}' deve ser escalado para 100% do tráfego, otimizando "
            f"{metric_spec['label']}: {efeito_txt}, diferença estatisticamente significativa "
            f"contra todas as demais variantes (alpha={alpha}), impacto financeiro {impacto_financeiro.lower()} "
            f"e risco {risco.lower()}."
        )

    elif significant_vs_all and not practically_significant:
        recommendation = f"ESCALAR_{business_winner.upper().replace(' ', '_')}_COM_RESSALVA"
        efeito_txt = f"{effect_pct}%" if effect_pct is not None else (f"{effect_abs}" if effect_abs is not None else "n/d")
        headline = (
            f"'{business_winner}' venceu com significância estatística em {metric_spec['label']}, "
            f"mas a diferença prática é pequena ({efeito_txt}, abaixo do limiar de "
            f"{min_effect_pct}% configurado) — impacto financeiro {impacto_financeiro.lower()}. "
            f"Pode escalar, mas o ganho esperado é marginal; vale pesar o custo operacional "
            f"da mudança contra esse ganho."
        )

    elif has_small_sample:
        recommendation = "CONTINUAR_TESTE"
        headline = (
            f"Ainda não há evidência estatística suficiente para diferenciar as variantes em "
            f"{metric_spec['label']}, e o período observado é curto. Recomenda-se manter o "
            f"teste rodando e reavaliar com mais dados antes de escalar qualquer grupo."
        )

    else:
        recommendation = "NENHUMA_VARIANTE_SIGNIFICATIVA"
        headline = (
            f"As variantes não apresentam diferença estatisticamente significativa em "
            f"{metric_spec['label']} (alpha={alpha}), mesmo com amostra considerada suficiente. "
            f"Escalar qualquer uma não é sustentado pelos dados — considere manter a "
            f"configuração atual ou testar uma variação mais ousada."
        )

    return {
        "metrica_alvo": metrica_alvo,
        "metrica_alvo_label": metric_spec["label"],
        "justificativa_metrica": metric_spec["justificativa"],
        "vencedor_de_negocio": business_winner,
        "efeito_pratico_pct_vs_segundo_colocado": effect_pct,
        "efeito_pratico_absoluto_vs_segundo_colocado": effect_abs,
        "significativo_vs_todos_os_grupos": significant_vs_all,
        "relevante_na_pratica": practically_significant,
        "dimensoes": {
            "confianca": confianca,
            "impacto_financeiro": impacto_financeiro,
            "risco": risco,
        },
        "recomendacao": recommendation,
        # mantido por compatibilidade com quem já lia "confianca" no nível raiz da decisão
        "confianca": confianca,
        "resumo": headline,
        "avisos_qualidade_dados_relevantes": n_warnings,
    }
