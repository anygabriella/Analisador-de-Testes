"""
sheets_writer.py — registra o resumo do teste na planilha de acompanhamento.

Tenta usar o Google Sheets via service account (gspread). Se não houver
credenciais configuradas (ou a chamada falhar por qualquer motivo de rede/
permissão), cai automaticamente para um CSV local no mesmo formato — o
pipeline nunca quebra por causa do Sheets, e o "mínimo aceito" do desafio
(CSV) sempre é satisfeito.
"""
import os
import csv
from datetime import datetime

HEADER = [
    "data_analise", "nome_do_teste", "parceiro", "periodo_inicio", "periodo_fim",
    "dias_totais", "grupos", "metrica_alvo", "vencedor_de_negocio", "lucro_total_vencedor",
    "p_valor_teste_global", "recomendacao", "confianca", "impacto_financeiro", "risco",
    "resumo", "link_relatorio",
]


def _row_from_analysis(analysis: dict, report_link: str) -> list:
    meta = analysis["metadados"]
    dec = analysis["decisao"]
    metrics = analysis["metricas_por_grupo"]
    winner = dec["vencedor_de_negocio"]
    dims = dec.get("dimensoes", {})
    return [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        meta["nome_do_teste"],
        meta["parceiro"],
        meta["periodo_inicio"],
        meta["periodo_fim"],
        meta["dias_totais"],
        ", ".join(meta["grupos"]),
        dec.get("metrica_alvo_label", "lucro"),
        winner,
        metrics[winner]["lucro_total"],
        analysis["estatistica"]["teste_global"]["p_value"],
        dec["recomendacao"],
        dims.get("confianca", dec.get("confianca")),
        dims.get("impacto_financeiro", ""),
        dims.get("risco", ""),
        dec["resumo"],
        report_link,
    ]


def _append_csv(path: str, row: list):
    file_exists = os.path.isfile(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(HEADER)
        writer.writerow(row)


def append_result(analysis: dict, cfg: dict, report_link: str = "") -> dict:
    """
    Retorna {"backend": "google_sheets" | "csv", "location": str, "error": str|None}
    """
    row = _row_from_analysis(analysis, report_link)
    sa_file = cfg["sheets"]["service_account_file"]
    sheet_id = os.environ.get("AB_TEST_SHEET_ID")

    if os.path.isfile(sa_file) and sheet_id:
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
            client = gspread.authorize(creds)
            sh = client.open_by_key(sheet_id)
            ws_name = cfg["sheets"]["worksheet_name"]
            try:
                ws = sh.worksheet(ws_name)
            except gspread.WorksheetNotFound:
                ws = sh.add_worksheet(title=ws_name, rows=1000, cols=len(HEADER))
                ws.append_row(HEADER)

            if ws.row_count == 0 or not ws.get_all_values():
                ws.append_row(HEADER)
            ws.append_row(row, value_input_option="USER_ENTERED")
            return {"backend": "google_sheets", "location": f"sheet_id={sheet_id}", "error": None}
        except Exception as e:  # nunca deixa o Sheets quebrar o pipeline
            fallback_path = cfg["sheets"]["fallback_csv"]
            _append_csv(fallback_path, row)
            return {"backend": "csv", "location": fallback_path, "error": f"Google Sheets falhou, usado CSV: {e}"}

    fallback_path = cfg["sheets"]["fallback_csv"]
    _append_csv(fallback_path, row)
    return {"backend": "csv", "location": fallback_path, "error": None}
