"""
insights.py — detecta padrões factuais e não-óbvios nos dados, pra servir de
base grounded para a camada de leitura crítica do agente de IA (ver CLAUDE.md).

Importante: este módulo NUNCA gera texto de opinião — só observações
verificáveis a partir dos números já calculados (ex: "grupo X tem mais
compradores mas menos lucro que Y"). A interpretação de negócio ("isso sugere
que o incentivo está acima do ótimo") é responsabilidade do agente de IA na
conversa, mas sempre ancorada nesses fatos, nunca inventando um número novo.
"""


def compute_insights(group_metrics: dict) -> list:
    insights = []
    groups = list(group_metrics.keys())
    if len(groups) < 2:
        return insights

    # 1) grupo com mais compradores não é o grupo com mais lucro
    top_buyers = max(groups, key=lambda g: group_metrics[g]["compradores_total"])
    top_profit = max(groups, key=lambda g: group_metrics[g]["lucro_total"])
    if top_buyers != top_profit:
        insights.append(
            f"'{top_buyers}' tem o maior volume de compradores, mas '{top_profit}' tem o maior "
            f"lucro líquido — o grupo que mais vende não é o mais rentável. O custo de cashback "
            f"parece estar corroendo parte do ganho de volume em '{top_buyers}'."
        )

    # 2) ROI abaixo de 1 (Méliuz paga mais cashback do que recebe de comissão)
    for g in groups:
        roi = group_metrics[g]["roi"]
        if roi == roi and roi < 1.0:  # not NaN
            insights.append(
                f"'{g}' opera com ROI abaixo de 1 ({roi}x) — cada R$ 1 de cashback dado nesse "
                f"grupo retorna menos de R$ 1 em comissão. Mesmo que o volume seja bom, essa "
                f"variante está estruturalmente no vermelho."
            )

    # 3) cashback_rate muito mais alto em um grupo que nos demais (incentivo desproporcional)
    rates = {g: group_metrics[g]["cashback_rate_sobre_vendas"] for g in groups}
    valid_rates = {g: v for g, v in rates.items() if v == v}
    if len(valid_rates) >= 2:
        max_g = max(valid_rates, key=valid_rates.get)
        min_g = min(valid_rates, key=valid_rates.get)
        if valid_rates[max_g] > 0 and valid_rates[min_g] >= 0:
            diff = valid_rates[max_g] - valid_rates[min_g]
            if diff >= 3.0:  # pontos percentuais de diferença
                insights.append(
                    f"'{max_g}' distribui {valid_rates[max_g]}% do GMV em cashback, contra "
                    f"{valid_rates[min_g]}% em '{min_g}' — uma diferença de {round(diff, 1)} "
                    f"pontos percentuais no incentivo entre as variantes."
                )

    # 4) ticket médio muito diferente entre grupos (pode indicar mudança de mix, não só de preço)
    tickets = {g: group_metrics[g]["ticket_medio"] for g in groups if group_metrics[g]["ticket_medio"] == group_metrics[g]["ticket_medio"]}
    if len(tickets) >= 2:
        max_g = max(tickets, key=tickets.get)
        min_g = min(tickets, key=tickets.get)
        if tickets[min_g] > 0:
            ratio = tickets[max_g] / tickets[min_g]
            if ratio >= 1.15:
                insights.append(
                    f"Ticket médio de '{max_g}' (R$ {tickets[max_g]:.2f}) é "
                    f"{round((ratio - 1) * 100, 1)}% maior que o de '{min_g}' (R$ {tickets[min_g]:.2f}) "
                    f"— vale investigar se o cashback maior está atraindo um perfil de compra diferente, "
                    f"não só mais volume do mesmo perfil."
                )

    return insights
