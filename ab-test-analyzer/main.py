#!/usr/bin/env python3
"""
main.py — ponto de entrada único do pipeline de análise de teste A/B de cashback.

Uso:
    python main.py data/dataset_01_parceiroA.csv
    python main.py data/dataset_02_parceiroB.csv --nome "Teste cashback Parceiro B - Maio/Jun 2025"
    python main.py <qualquer_csv_no_mesmo_schema> --output-dir output/parceiro_x

Zero mudança de código entre datasets: tudo entra por parâmetro.
"""
import argparse
import json
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data_loader import load_and_validate
from src.metrics import compute_group_metrics, METRIC_OPTIONS
from src.insights import compute_insights
from src.stats_tests import run_statistical_tests
from src.decision import decide
from src.charts import plot_profit_bar, plot_daily_trend
from src.report import generate_markdown_report
from src.sheets_writer import append_result


def load_config(path="config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(csv_path: str, cfg: dict, nome_teste: str, descricao: str, output_dir: str, metrica_alvo: str = None) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    metrica_alvo = metrica_alvo or cfg["decision"]["metrica_alvo_default"]
    if metrica_alvo not in METRIC_OPTIONS:
        raise ValueError(f"--metrica-alvo inválida: {metrica_alvo!r}. Opções: {list(METRIC_OPTIONS.keys())}")
    metric_spec = METRIC_OPTIONS[metrica_alvo]

    df, issues = load_and_validate(csv_path, cfg)
    group_metrics = compute_group_metrics(df)
    stats_result = run_statistical_tests(
        df, cfg, metric_col=metric_spec["daily_series_col"], metric_label=metric_spec["label"]
    )
    decision = decide(group_metrics, stats_result, issues, cfg, metrica_alvo=metrica_alvo)
    insights = compute_insights(group_metrics)

    parceiro = df["parceiro"].iloc[0]
    meta = {
        "nome_do_teste": nome_teste or f"Teste cashback - {parceiro}",
        "descricao": descricao or (
            f"Teste A/B de variantes de cashback para o parceiro {parceiro}, "
            f"comparando {', '.join(sorted(df['grupo'].unique()))}."
        ),
        "parceiro": parceiro,
        "arquivo_origem": os.path.basename(csv_path),
        "periodo_inicio": df["data"].min().strftime("%Y-%m-%d"),
        "periodo_fim": df["data"].max().strftime("%Y-%m-%d"),
        "dias_totais": int(df["data"].nunique()),
        "grupos": sorted(df["grupo"].unique().tolist()),
        "gerado_em": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    analysis = {
        "metadados": meta,
        "metricas_por_grupo": group_metrics,
        "estatistica": stats_result,
        "decisao": decision,
        "insights_automaticos": insights,
        "avisos_qualidade_dados": issues,
    }

    # --- charts ---
    plot_profit_bar(group_metrics, os.path.join(output_dir, "profit_bar.png"))
    plot_daily_trend(df, os.path.join(output_dir, "daily_trend.png"))

    # --- analysis.json ---
    json_path = os.path.join(output_dir, "analysis.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)

    # --- relatório markdown ---
    report_md = generate_markdown_report(analysis)
    report_path = os.path.join(output_dir, "relatorio.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    # --- planilha de acompanhamento (Google Sheets ou CSV) ---
    sheet_result = append_result(analysis, cfg, report_link=report_path)
    analysis["registro_planilha"] = sheet_result
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)

    return {
        "analysis": analysis,
        "paths": {"json": json_path, "report": report_path, "output_dir": output_dir},
        "sheet_result": sheet_result,
    }


def main():
    parser = argparse.ArgumentParser(description="Analisa um teste A/B de cashback e recomenda uma decisão.")
    parser.add_argument("csv_path", help="Caminho do CSV do teste (schema: Data, Grupos de usuários, Parceiro, compradores, comissão, cashback, vendas totais)")
    parser.add_argument("--nome", default=None, help="Nome do teste (aparece no relatório e na planilha)")
    parser.add_argument("--descricao", default=None, help="Descrição curta do teste")
    parser.add_argument("--output-dir", default=None, help="Pasta de saída (default: output/<nome_do_csv>)")
    parser.add_argument("--config", default="config.yaml", help="Caminho do config.yaml")
    parser.add_argument(
        "--metrica-alvo", default=None, choices=list(METRIC_OPTIONS.keys()),
        help="Métrica usada para decidir o vencedor: lucro (padrão), roi, ou compradores. "
             "Se não informado, usa o default do config.yaml.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    output_dir = args.output_dir or os.path.join("output", os.path.splitext(os.path.basename(args.csv_path))[0])

    result = run(args.csv_path, cfg, args.nome, args.descricao, output_dir, metrica_alvo=args.metrica_alvo)

    dec = result["analysis"]["decisao"]
    print(f"\n✅ Análise concluída: {result['paths']['report']}")
    print(f"   Métrica-alvo: {dec['metrica_alvo_label']}")
    print(f"   Recomendação: {dec['recomendacao']}")
    print(f"   Confiança: {dec['dimensoes']['confianca']}  |  Impacto financeiro: {dec['dimensoes']['impacto_financeiro']}  |  Risco: {dec['dimensoes']['risco']}")
    print(f"   {dec['resumo']}")
    print(f"   Planilha: {result['sheet_result']['backend']} -> {result['sheet_result']['location']}")


if __name__ == "__main__":
    main()
