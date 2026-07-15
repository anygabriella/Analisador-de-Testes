"""
parsers.py — conversão robusta de valores monetários em formato brasileiro (R$)
para float, tolerando variações de formatação e dados sujos.
"""
import re
import math


def parse_brl(value) -> float:
    """
    Converte uma string tipo 'R$ 10.273', 'R$ 1.234,56', 'R$-50', '  R$ 0,00  '
    (ou já um número) para float.

    Regras do formato brasileiro:
      - '.' é separador de milhar
      - ',' é separador decimal
    Se não houver vírgula, assume-se que os pontos são milhares (não decimais),
    que é o padrão observado nos datasets do Méliuz (ex: 'R$ 93.390' = 93390,0).

    Retorna math.nan se o valor não puder ser interpretado (em vez de estourar
    exceção), para que a camada de validação de dados possa contabilizar e
    reportar o problema.
    """
    if value is None:
        return math.nan
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "-"):
        return math.nan

    # remove símbolo de moeda e espaços
    s = s.replace("R$", "").replace("r$", "").strip()

    # detecta sinal negativo (pode vir como '-R$ 10' ou 'R$ -10' ou '(10)')
    negative = False
    if s.startswith("-") or s.startswith("("):
        negative = True
    s = s.replace("(", "").replace(")", "").lstrip("-").strip()

    # remove qualquer caractere que não seja dígito, ponto ou vírgula
    s = re.sub(r"[^\d.,]", "", s)
    if s == "":
        return math.nan

    if "," in s:
        # vírgula é decimal -> remove pontos de milhar, troca vírgula por ponto
        s = s.replace(".", "").replace(",", ".")
    else:
        # sem vírgula: pontos são separadores de milhar (padrão destes dados)
        s = s.replace(".", "")

    try:
        num = float(s)
    except ValueError:
        return math.nan

    return -num if negative else num
