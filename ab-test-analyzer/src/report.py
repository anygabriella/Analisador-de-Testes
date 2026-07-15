"""
report.py — monta o relatório executivo em Markdown a partir do analysis dict.
Gerado 100% pelo Python (não depende de uma chamada de IA em runtime), pra
ser reprodutível e testável. Um agente de IA pode enriquecer a conversa em
cima disso (ver CLAUDE.md), mas o artefato de entrega já nasce completo
sozinho.

Ordem do relatório é deliberada: decisão e dimensões de negócio primeiro
(o que um gestor de Growth quer ler em 10 segundos), metodologia estatística
depois e compacta (pra quem quiser auditar o rigor, sem competir visualmente
com a decisão).
"""


def _fmt_brl(v):
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _fmt_metric_value(v, unidade):
    if v != v:  # NaN
        return "n/d"
    if unidade == "R$":
        return _fmt_brl(v)
    if unidade == "x":
        return f"{v:.2f}x"
    return f"{v:,.1f}".replace(",", ".")


def generate_markdown_report(analysis: dict) -> str:
    meta = analysis["metadados"]
    metrics = analysis["metricas_por_grupo"]
    stats_r = analysis["estatistica"]
    dec = analysis["decisao"]
    insights = analysis.get("insights_automaticos", [])
    issues = analysis["avisos_qualidade_dados"]
    dims = dec.get("dimensoes", {})

    lines = []
    lines.append(f"# Relatório de Teste A/B — {meta['parceiro']}")
    lines.append("")
    lines.append(f"**Período analisado:** {meta['periodo_inicio']} a {meta['periodo_fim']} "
                 f"({meta['dias_totais']} dias)")
    lines.append(f"**Grupos comparados:** {', '.join(meta['grupos'])}")
    lines.append(f"**Métrica-alvo desta análise:** {dec['metrica_alvo_label']}")
    lines.append(f"**Gerado em:** {meta['gerado_em']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 Decisão")
    lines.append("")
    lines.append(f"> **{dec['resumo']}**")
    lines.append("")
    lines.append(f"| Recomendação | Confiança | Impacto financeiro | Risco |")
    lines.append(f"|---|---|---|---|")
    lines.append(f"| `{dec['recomendacao']}` | {dims.get('confianca', 'n/d')} | "
                 f"{dims.get('impacto_financeiro', 'n/d')} | {dims.get('risco', 'n/d')} |")
    lines.append("")
    lines.append(f"- **Vencedor de negócio (por {dec['metrica_alvo_label']}):** {dec['vencedor_de_negocio']}")
    if dec["efeito_pratico_pct_vs_segundo_colocado"] is not None:
        lines.append(f"- **Efeito prático vs. 2º colocado:** {dec['efeito_pratico_pct_vs_segundo_colocado']:+.1f}%/dia")
    lines.append(f"- **Significativo estatisticamente contra todos os demais grupos?** "
                 f"{'Sim' if dec['significativo_vs_todos_os_grupos'] else 'Não'}")
    lines.append("")
    lines.append(f"*Por que essa métrica:* {dec['justificativa_metrica']}")
    lines.append("")

    if insights:
        lines.append("---")
        lines.append("")
        lines.append("## 🔍 Observações automáticas")
        lines.append("")
        lines.append(
            "Padrões factuais detectados nos dados — não substituem uma leitura crítica humana, "
            "mas apontam onde vale investigar antes de decidir:"
        )
        lines.append("")
        for i in insights:
            lines.append(f"- {i}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 📊 Métricas por variante")
    lines.append("")
    lines.append("| Métrica | " + " | ".join(metrics.keys()) + " |")
    lines.append("|---|" + "---|" * len(metrics))
    campos = [
        ("Dias observados", "dias_observados", ""),
        ("Compradores (total)", "compradores_total", ""),
        ("Compradores/dia (média)", "compradores_media_dia", ""),
        ("Comissão total", "comissao_total", "brl"),
        ("Cashback total", "cashback_total", "brl"),
        ("Vendas totais (GMV)", "vendas_totais", "brl"),
        ("Lucro total", "lucro_total", "brl"),
        ("Lucro médio/dia", "lucro_media_dia", "brl"),
        ("ROI (comissão/cashback)", "roi", ""),
        ("Ticket médio", "ticket_medio", "brl"),
        ("Take rate (comissão/GMV)", "take_rate", "%"),
        ("Cashback rate (cashback/GMV)", "cashback_rate_sobre_vendas", "%"),
    ]
    for label, key, fmt in campos:
        row = [label]
        for g in metrics:
            v = metrics[g][key]
            if fmt == "brl":
                row.append(_fmt_brl(v))
            elif fmt == "%":
                row.append(f"{v}%")
            else:
                row.append(str(v))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("![Lucro total por variante](profit_bar.png)")
    lines.append("")
    lines.append("![Lucro acumulado ao longo do teste](daily_trend.png)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## ⚠️ Avisos de qualidade de dados")
    lines.append("")
    if issues:
        for i in issues:
            emoji = {"warning": "🟠", "info": "🔵", "error": "🔴"}.get(i["severity"], "•")
            lines.append(f"- {emoji} **[{i['code']}]** {i['message']}")
    else:
        lines.append("Nenhum problema relevante encontrado nos dados.")
    lines.append("")

    # --- metodologia estatística: compacta, no fim, pra quem quiser auditar o rigor ---
    lines.append("---")
    lines.append("")
    lines.append("<details>")
    lines.append("<summary><strong>🔬 Metodologia estatística (detalhes para auditoria)</strong></summary>")
    lines.append("")
    lines.append(f"- **Unidade de análise:** {stats_r['unidade_de_analise']}")
    lines.append(f"- **Método escolhido:** `{stats_r['teste_global']['method']}` "
                 f"— {stats_r['metodo_escolhido_motivo']}")
    lines.append(f"- **p-valor do teste global:** {stats_r['teste_global']['p_value']} "
                 f"(alpha = {stats_r['alpha']})")
    lines.append("")
    lines.append("**Normalidade por grupo (Shapiro-Wilk):**")
    for g, v in stats_r["normalidade_por_grupo"].items():
        estado = "normal" if v["normal"] else ("não-normal" if v["normal"] is not None else "n/a — amostra pequena ou variância zero")
        lines.append(f"- {g}: p = {v['p_value']} ({estado})")
    lines.append("")
    lines.append("**Comparações par-a-par (correção de Bonferroni):**")
    lines.append("")
    lines.append("| Comparação | Teste | p (ajustado) | Significativo? | Effect size |")
    lines.append("|---|---|---|---|---|")
    for pair, v in stats_r["comparacoes_par_a_par"].items():
        lines.append(f"| {pair} | {v['test']} | {v['p_value_bonferroni']} | "
                     f"{'Sim' if v['significant'] else 'Não'} | {v['effect_size']} |")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 🧭 Limitações conhecidas")
    lines.append("")
    lines.append(
        "- Os dados não incluem visitantes/sessões, apenas compradores — não é possível "
        "calcular taxa de conversão, só volume de compra e resultado financeiro."
    )
    lines.append(
        "- A granularidade é diária por grupo, não por usuário — o teste estatístico compara "
        "dias, não usuários individuais, então o \"n\" efetivo é o número de dias observados."
    )
    lines.append(
        "- A decisão assume que os grupos foram alocados aleatoriamente e rodaram de forma "
        "concorrente no mesmo período — este pipeline não consegue validar a aleatorização em si."
    )
    lines.append(
        f"- A métrica-alvo desta análise foi **{dec['metrica_alvo_label']}**; rodar com "
        f"`--metrica-alvo` diferente (`lucro`, `roi` ou `compradores`) pode indicar um vencedor "
        f"diferente — vale checar se o objetivo do teste era mesmo esse."
    )
    lines.append("")
    return "\n".join(lines)
