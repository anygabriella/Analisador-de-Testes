"""
metrics.py — métricas de negócio por grupo (variante do teste).
"""
import math

# Registro central das métricas que podem ser usadas como "métrica-alvo" da
# decisão (qual variante é a "vencedora"). Adicionar uma nova métrica no
# futuro é só adicionar uma entrada aqui — main.py, decision.py e stats_tests.py
# já são genéricos em cima disso.
METRIC_OPTIONS = {
    "lucro": {
        "label": "Lucro líquido (comissão − cashback)",
        "total_key": "lucro_total",
        "daily_key": "lucro_media_dia",
        "daily_series_col": "lucro",
        "unidade": "R$",
        "justificativa": (
            "Lucro líquido é a métrica padrão porque representa o impacto financeiro direto "
            "para o Méliuz — quanto sobra no caixa depois de pagar o cashback ao usuário. É a "
            "resposta mais direta a 'vale escalar?' quando o objetivo do teste não foi "
            "especificado de outra forma."
        ),
    },
    "roi": {
        "label": "ROI (comissão / cashback)",
        "total_key": "roi",
        "daily_key": "roi_media_dia",
        "daily_series_col": "roi_diario",
        "unidade": "x",
        "justificativa": (
            "ROI mede eficiência de capital: quanto de comissão volta pra cada R$ de cashback "
            "investido. É a métrica certa quando o objetivo é maximizar retorno sobre o "
            "orçamento de cashback, não o lucro absoluto — que pode ser maior só porque o "
            "grupo movimentou mais volume, não porque é mais eficiente."
        ),
    },
    "compradores": {
        "label": "Volume de compradores",
        "total_key": "compradores_total",
        "daily_key": "compradores_media_dia",
        "daily_series_col": "compradores",
        "unidade": "compradores",
        "justificativa": (
            "Volume de compradores é a métrica certa quando o objetivo do teste é "
            "aquisição/ativação, mesmo que isso custe margem no curto prazo — por exemplo, "
            "entrada em um parceiro novo, onde construir base de usuários importa mais que "
            "lucro imediato."
        ),
    },
}


def compute_group_metrics(df) -> dict:
    """
    Retorna um dict {grupo: {métricas...}} com os totais e razões de negócio
    relevantes pra decisão de escalar ou não uma variante de cashback.
    """
    out = {}
    for g, sub in df.groupby("grupo"):
        compradores = sub["compradores"].sum()
        comissao = sub["comissao"].sum()
        cashback = sub["cashback"].sum()
        vendas = sub["vendas_totais"].sum()
        lucro = comissao - cashback
        dias = sub["data"].nunique()
        roi_diario_medio = sub["roi_diario"].mean(skipna=True)

        out[g] = {
            "dias_observados": int(dias),
            "compradores_total": int(compradores),
            "compradores_media_dia": round(compradores / dias, 2) if dias else math.nan,
            "comissao_total": round(comissao, 2),
            "cashback_total": round(cashback, 2),
            "vendas_totais": round(vendas, 2),
            "lucro_total": round(lucro, 2),
            "lucro_media_dia": round(lucro / dias, 2) if dias else math.nan,
            # ROI do ponto de vista do Méliuz: quanto de comissão volta pra cada R$ de cashback dado
            "roi": round(comissao / cashback, 4) if cashback else math.nan,
            "roi_media_dia": round(float(roi_diario_medio), 4) if roi_diario_medio == roi_diario_medio else math.nan,
            "ticket_medio": round(vendas / compradores, 2) if compradores else math.nan,
            # % do GMV que virou cashback pro usuário
            "cashback_rate_sobre_vendas": round(cashback / vendas * 100, 2) if vendas else math.nan,
            # % do GMV que o Méliuz recebe de comissão do parceiro
            "take_rate": round(comissao / vendas * 100, 2) if vendas else math.nan,
        }
    return out
