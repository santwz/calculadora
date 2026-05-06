import datetime as dt
from io import BytesIO
from functools import lru_cache
import unicodedata
import math

import pandas as pd
import requests
import exchange_calendars as ec


ANBIMA_XLS = "https://www.anbima.com.br/informacoes/indicadores/arqs/indicadores.xls"


# ----------------------------
# Helpers de normalização/parse
# ----------------------------
def _norm(x) -> str:
    s = "" if x is None else str(x)
    s = s.strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.upper()


def _to_float(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x)):
        return float(x)

    s = str(x).strip()
    if not s or s.lower() == "nan":
        return None

    # aceita "7,378.94", "7.378,94", "7378.94", etc.
    if "," in s and "." in s:
        # último separador é o decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")

    try:
        return float(s)
    except ValueError:
        return None


def _first_number_right(row_vals: list, start_j: int) -> float | None:
    for j in range(start_j + 1, len(row_vals)):
        v = _to_float(row_vals[j])
        if v is not None:
            return v
    return None


# ----------------------------
# ANBIMA: download + parse (com cache)
# ----------------------------
@lru_cache(maxsize=1)
def _download_anbima_indicadores(url: str = ANBIMA_XLS) -> pd.DataFrame:
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    # .xls -> xlrd
    # Se der erro: pip install xlrd
    return pd.read_excel(BytesIO(r.content), header=None, engine="xlrd")


@lru_cache(maxsize=1)
def _get_anbima_ipca_inputs() -> tuple[float, float]:
    """
    Retorna:
      ipca_idx: Número-índice do IPCA (nível)
      ipca_proj: IPCA1 Projeção (em %)
    """
    df = _download_anbima_indicadores()

    ipca_idx = None
    ipca_proj = None

    for i in range(len(df)):
        row = df.iloc[i].tolist()
        row_norm = [_norm(v) for v in row]
        joined = " ".join([x for x in row_norm if x and x != "NAN"])

        # IPCA + Número Índice (normalmente em colunas separadas)
        if ("IPCA" in joined) and ("NUMERO" in joined) and ("INDICE" in joined):
            for j, cell in enumerate(row_norm):
                if ("NUMERO" in cell) and ("INDICE" in cell):
                    v = _first_number_right(row, j)
                    if v is not None:
                        ipca_idx = v
                        break

        # IPCA1 + Projeção
        if ("IPCA1" in joined) and ("PROJECAO" in joined):
            for j, cell in enumerate(row_norm):
                if "PROJECAO" in cell:
                    v = _first_number_right(row, j)
                    if v is not None:
                        ipca_proj = v
                        break

        if ipca_idx is not None and ipca_proj is not None:
            return ipca_idx, ipca_proj

    raise RuntimeError(
        "Não consegui localizar IPCA Número-índice e/ou IPCA1 Projeção no indicadores.xls. "
        "Se a ANBIMA mudar o layout de novo, eu ajusto o parser."
    )


# ----------------------------
# Calendário B3 + contagens dud/dum
# ----------------------------
def _prev_session(cal, d: dt.date) -> dt.date:
    """Se cair em fim de semana/feriado, volta para a última sessão B3."""
    ts = pd.Timestamp(d)
    while not cal.is_session(ts):
        d -= dt.timedelta(days=1)
        ts = pd.Timestamp(d)
    return d


def _last_15_before_or_equal(d: dt.date) -> dt.date:
    """Último dia 15 <= d (se d<15, pega 15 do mês anterior)."""
    if d.day >= 15:
        return dt.date(d.year, d.month, 15)
    y, m = d.year, d.month - 1
    if m == 0:
        y, m = y - 1, 12
    return dt.date(y, m, 15)


def _add_months(date_: dt.date, months: int) -> dt.date:
    y = date_.year + (date_.month - 1 + months) // 12
    m = (date_.month - 1 + months) % 12 + 1
    return dt.date(y, m, date_.day)


def _sessions_excl_incl(cal, start_exclusive: dt.date, end_inclusive: dt.date) -> int:
    """
    Conta sessões no intervalo (start_exclusive, end_inclusive],
    coerente com:
      dudt = dias úteis decorridos a partir do dia 15
      dum  = (15 exclusive, próximo 15 inclusive)
    """
    start_ts = pd.Timestamp(start_exclusive)
    end_ts = pd.Timestamp(end_inclusive)
    sessions = cal.sessions_in_range(start_ts, end_ts)

    # exclui start_exclusive se ele for sessão (normalmente não é, mas por segurança)
    return sum(s.date() != start_exclusive for s in sessions)


# ----------------------------
# IPCA pró-rata (BZSXPRTA-like)
# ----------------------------
def ipca_prorata(date_: dt.date | str, cal_name: str = "BVMF") -> float:
    """
    Calcula o IPCA pro rata tempore pela fórmula do contrato DAP:
      PRTt = IPCAt-1 * (1 + IPCA_Proj/100)^(dudt/dum)
    com dud/dum em dias úteis (calendário B3). :contentReference[oaicite:1]{index=1}
    """
    if isinstance(date_, str):
        date_ = dt.date.fromisoformat(date_)

    cal = ec.get_calendar(cal_name)
    d = _prev_session(cal, date_)  # garante sessão B3

    ipca_idx, ipca_proj = _get_anbima_ipca_inputs()

    d15a = _last_15_before_or_equal(d)  # âncora do período
    d15p = _add_months(d15a, 1)

    dum = _sessions_excl_incl(cal, d15a, d15p)
    dud = _sessions_excl_incl(cal, d15a, d)

    if dum <= 0:
        raise RuntimeError("Janela de dias úteis inválida (dum<=0). Ver calendário.")

    return ipca_idx * ((1.0 + ipca_proj / 100.0) ** (dud / dum))


def ipca_prorata_series(start: str, end: str, cal_name: str = "BVMF") -> pd.DataFrame:
    """Série diária (somente sessões B3) entre start e end (YYYY-MM-DD)."""
    cal = ec.get_calendar(cal_name)
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)

    sessions = cal.sessions_in_range(pd.Timestamp(s), pd.Timestamp(e))
    out = []
    for ts in sessions:
        d = ts.date()
        out.append((d, ipca_prorata(d, cal_name=cal_name)))

    return pd.DataFrame(out, columns=["date", "ipca_prorata"]).set_index("date")


if __name__ == "__main__":
    print(ipca_prorata("2025-12-16"))
    # print(ipca_prorata_series("2025-12-10", "2025-12-20"))
