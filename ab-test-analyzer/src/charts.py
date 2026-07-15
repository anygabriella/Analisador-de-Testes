"""
charts.py — gráficos simples e diretos pro relatório executivo.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_profit_bar(group_metrics: dict, out_path: str):
    groups = list(group_metrics.keys())
    lucro = [group_metrics[g]["lucro_total"] for g in groups]
    colors = ["#2E7D32" if v == max(lucro) else "#90A4AE" for v in lucro]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(groups, lucro, color=colors)
    ax.set_ylabel("Lucro total no período (R$)")
    ax.set_title("Lucro total por variante (comissão - cashback)")
    ax.axhline(0, color="black", linewidth=0.8)
    for b, v in zip(bars, lucro):
        ax.text(b.get_x() + b.get_width() / 2, v, f"R$ {v:,.0f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_daily_trend(df, out_path: str):
    fig, ax = plt.subplots(figsize=(8, 4))
    for g, sub in df.groupby("grupo"):
        sub = sub.sort_values("data")
        ax.plot(sub["data"], sub["lucro"].cumsum(), label=g)
    ax.set_ylabel("Lucro acumulado (R$)")
    ax.set_title("Evolução do lucro acumulado ao longo do teste")
    ax.legend()
    ax.axhline(0, color="black", linewidth=0.6)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
