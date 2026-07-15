"""
data_loader.py — carrega o CSV do teste A/B, normaliza schema e roda uma
bateria de checagens de qualidade de dado. Cada checagem gera um "issue"
estruturado (não um print solto), pra virar avisos rastreáveis no
analysis.json e no relatório final.
"""
import unicodedata
import math
import pandas as pd
import numpy as np

from .parsers import parse_brl

# nomes canônicos internos -> possíveis variações de nome de coluna (normalizadas)
COLUMN_ALIASES = {
    "data": ["data", "date", "dia"],
    "grupo": ["gruposdeusuarios", "grupo", "variante", "variant", "group"],
    "parceiro": ["parceiro", "partner"],
    "compradores": ["compradores", "buyers", "compras"],
    "comissao": ["comissao", "commission"],
    "cashback": ["cashback"],
    "vendas_totais": ["vendastotais", "vendas", "gmv", "totalsales"],
}


def _normalize(text: str) -> str:
    """minúsculo, sem acento, sem espaço/underscore — pra casar nomes de coluna."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return text.lower().replace(" ", "").replace("_", "")


def _map_columns(df: pd.DataFrame) -> dict:
    """Mapeia colunas do CSV para nomes canônicos. Levanta erro claro se faltar algo essencial."""
    normalized_to_original = {_normalize(c): c for c in df.columns}
    mapping = {}
    missing = []
    for canonical, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            if alias in normalized_to_original:
                found = normalized_to_original[alias]
                break
        if found is None:
            missing.append(canonical)
        else:
            mapping[canonical] = found

    if missing:
        raise ValueError(
            f"Colunas obrigatórias não encontradas no CSV: {missing}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )
    return mapping


def load_and_validate(csv_path: str, cfg: dict):
    """
    Retorna (df_limpo, issues) onde:
      - df_limpo: DataFrame com colunas canônicas, tipos corretos, pronto pra análise
      - issues: lista de dicts {severity, code, message} — usada no relatório e no JSON
    """
    issues = []

    raw = pd.read_csv(csv_path, dtype=str)
    if raw.empty:
        raise ValueError("O arquivo CSV está vazio.")

    colmap = _map_columns(raw)
    df = raw.rename(columns={v: k for k, v in colmap.items()})[list(colmap.keys())].copy()

    # --- datas ---
    parsed_dates = pd.to_datetime(df["data"], errors="coerce", format=None)
    n_bad_dates = parsed_dates.isna().sum()
    if n_bad_dates:
        issues.append({
            "severity": "warning",
            "code": "invalid_dates_dropped",
            "message": f"{n_bad_dates} linha(s) com data inválida foram descartadas.",
        })
    df["data"] = parsed_dates
    df = df[df["data"].notna()].copy()

    # --- grupo / parceiro: strip de espaços, remove linhas vazias ---
    df["grupo"] = df["grupo"].astype(str).str.strip()
    df["parceiro"] = df["parceiro"].astype(str).str.strip()
    n_empty_group = (df["grupo"] == "").sum() + df["grupo"].isna().sum()
    if n_empty_group:
        issues.append({
            "severity": "warning",
            "code": "empty_group_dropped",
            "message": f"{n_empty_group} linha(s) sem identificação de grupo foram descartadas.",
        })
        df = df[df["grupo"] != ""].copy()

    # --- colunas monetárias / numéricas ---
    df["compradores"] = pd.to_numeric(df["compradores"], errors="coerce")
    for col in ["comissao", "cashback", "vendas_totais"]:
        df[col] = df[col].apply(parse_brl)

    numeric_cols = ["compradores", "comissao", "cashback", "vendas_totais"]
    n_bad_numeric = int(df[numeric_cols].isna().any(axis=1).sum())
    if n_bad_numeric:
        issues.append({
            "severity": "warning",
            "code": "invalid_numeric_dropped",
            "message": f"{n_bad_numeric} linha(s) com valor numérico/monetário ilegível foram descartadas.",
        })
        df = df.dropna(subset=numeric_cols).copy()

    # --- valores negativos (não fazem sentido de negócio aqui) ---
    neg_mask = (df[numeric_cols] < 0).any(axis=1)
    n_neg = int(neg_mask.sum())
    if n_neg:
        issues.append({
            "severity": "warning",
            "code": "negative_values_dropped",
            "message": f"{n_neg} linha(s) com valores negativos (inconsistentes) foram descartadas.",
        })
        df = df[~neg_mask].copy()

    if df.empty:
        raise ValueError("Depois da limpeza, não sobrou nenhuma linha válida para análise.")

    # --- duplicatas (mesma data + grupo) ---
    dup_mask = df.duplicated(subset=["data", "grupo"], keep=False)
    n_dup = int(dup_mask.sum())
    if n_dup:
        issues.append({
            "severity": "warning",
            "code": "duplicate_rows_aggregated",
            "message": (
                f"{n_dup} linha(s) duplicadas (mesma data+grupo) foram somadas "
                f"em uma única observação por dia."
            ),
        })
        df = (
            df.groupby(["data", "grupo", "parceiro"], as_index=False)
            .agg({"compradores": "sum", "comissao": "sum", "cashback": "sum", "vendas_totais": "sum"})
        )

    # --- número de grupos ---
    groups = sorted(df["grupo"].unique())
    if len(groups) < 2:
        raise ValueError(
            f"É preciso pelo menos 2 grupos para comparar variantes. Encontrado: {groups}"
        )

    # --- desbalanceamento entre grupos (nº de dias por grupo) ---
    days_per_group = df.groupby("grupo")["data"].nunique()
    max_days, min_days = days_per_group.max(), days_per_group.min()
    imbalance_pct = 0.0 if max_days == 0 else (max_days - min_days) / max_days * 100
    if imbalance_pct > cfg["data_quality"]["max_group_size_imbalance_pct"]:
        issues.append({
            "severity": "warning",
            "code": "group_size_imbalance",
            "message": (
                f"Grupos com números de dias bem diferentes "
                f"({days_per_group.to_dict()}), diferença de {imbalance_pct:.1f}%. "
                f"Isso pode indicar que o teste não rodou de forma concorrente para todos os grupos."
            ),
        })

    # --- gaps de data dentro de cada grupo ---
    for g, sub in df.groupby("grupo"):
        full_range = pd.date_range(sub["data"].min(), sub["data"].max())
        missing_days = len(set(full_range) - set(sub["data"]))
        pct_missing = missing_days / len(full_range) * 100 if len(full_range) else 0
        if pct_missing > cfg["data_quality"]["max_missing_days_pct"]:
            issues.append({
                "severity": "warning",
                "code": "date_gaps",
                "message": (
                    f"Grupo '{g}' tem {missing_days} dia(s) faltando dentro do período "
                    f"do teste ({pct_missing:.1f}% do período) — possível gap de coleta."
                ),
            })

    # --- amostra pequena ---
    min_days_recommended = cfg["statistics"]["min_days_recommended"]
    if min_days < min_days_recommended:
        issues.append({
            "severity": "warning",
            "code": "small_sample",
            "message": (
                f"O grupo com menos dados tem apenas {min_days} dia(s) de observação "
                f"(recomendado: >= {min_days_recommended}). Resultado deve ser tratado com cautela."
            ),
        })

    # --- outliers (z-score sobre lucro diário por grupo) ---
    df["lucro"] = df["comissao"] - df["cashback"]

    # ROI diário (comissão/cashback por dia) — usado quando --metrica-alvo roi é escolhida.
    # Dias com cashback=0 tornam o ROI indefinido (divisão por zero); marcamos como NaN
    # e avisamos, em vez de deixar a conta estourar ou mentir com um número arbitrário.
    df["roi_diario"] = df.apply(
        lambda r: (r["comissao"] / r["cashback"]) if r["cashback"] > 0 else float("nan"), axis=1
    )
    n_roi_undefined = int(df["roi_diario"].isna().sum())
    if n_roi_undefined:
        issues.append({
            "severity": "info",
            "code": "roi_undefined_days",
            "message": (
                f"{n_roi_undefined} dia(s) com cashback = R$ 0 tornam o ROI diário indefinido "
                f"nesses dias — excluídos apenas do cálculo estatístico de ROI (não afetam "
                f"lucro nem volume de compradores)."
            ),
        })

    z_thresh = cfg["data_quality"]["outlier_zscore_threshold"]
    outlier_days = []
    for g, sub in df.groupby("grupo"):
        if sub["lucro"].std(ddof=0) > 0:
            z = (sub["lucro"] - sub["lucro"].mean()) / sub["lucro"].std(ddof=0)
            n_out = int((z.abs() > z_thresh).sum())
            if n_out:
                outlier_days.append((g, n_out))
    zero_variance_groups = [
        g for g, sub in df.groupby("grupo") if sub["lucro"].std(ddof=0) == 0 and len(sub) > 1
    ]
    if zero_variance_groups:
        issues.append({
            "severity": "info",
            "code": "zero_variance_profit_group",
            "message": (
                f"Grupo(s) {zero_variance_groups} têm lucro diário idêntico em todos os dias "
                f"(possível variante de controle com comissão = cashback por desenho, ou dado "
                f"sintético/simulado). Testes de normalidade não se aplicam a esses grupos."
            ),
        })

    if outlier_days:
        detail = ", ".join(f"{g}: {n}" for g, n in outlier_days)
        issues.append({
            "severity": "info",
            "code": "outlier_days_detected",
            "message": (
                f"Dias com lucro atípico (|z| > {z_thresh}) detectados por grupo ({detail}). "
                f"Não foram removidos automaticamente — podem ser picos legítimos (ex: promoção pontual)."
            ),
        })

    return df.reset_index(drop=True), issues
