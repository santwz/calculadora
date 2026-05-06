import datetime as dt
import math
import re
import unicodedata
from functools import lru_cache
from io import BytesIO
from typing import NamedTuple

import pandas as pd
import requests


ANBIMA_XLS = "https://www.anbima.com.br/informacoes/indicadores/arqs/indicadores.xls"
PT_MONTHS = {
    "JAN": 1,
    "FEV": 2,
    "MAR": 3,
    "ABR": 4,
    "MAI": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SET": 9,
    "OUT": 10,
    "NOV": 11,
    "DEZ": 12,
}


class IPCASnapshot(NamedTuple):
    ipca_index: float
    index_month: dt.date
    ipca_projection: float
    projection_month: dt.date


def _norm(value) -> str:
    text = "" if value is None else str(value)
    text = text.strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.upper()


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value)):
        return float(value)

    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", "")

    try:
        return float(text)
    except ValueError:
        return None


def _first_number_right(row_values: list, start_column: int) -> float | None:
    for column in range(start_column + 1, len(row_values)):
        value = _to_float(row_values[column])
        if value is not None:
            return value
    return None


def _parse_month_reference(value) -> dt.date | None:
    normalized = _norm(value)
    match = re.search(r"\(([A-Z]{3})/(\d{2})\)", normalized)
    if not match:
        return None

    month = PT_MONTHS.get(match.group(1))
    if month is None:
        return None

    return dt.date(2000 + int(match.group(2)), month, 1)


@lru_cache(maxsize=1)
def _download_indicadores(url: str = ANBIMA_XLS) -> pd.DataFrame:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return pd.read_excel(BytesIO(response.content), header=None, engine="xlrd")


@lru_cache(maxsize=1)
def get_ipca_snapshot() -> IPCASnapshot:
    df = _download_indicadores()
    ipca_index = None
    ipca_index_month = None
    ipca_projection = None
    ipca_projection_month = None

    for row_index in range(len(df)):
        row = df.iloc[row_index].tolist()
        normalized = [_norm(value) for value in row]
        joined = " ".join(value for value in normalized if value and value != "NAN")

        if "IPCA" in joined and "NUMERO" in joined and "INDICE" in joined:
            for column, cell in enumerate(normalized):
                if "NUMERO" in cell and "INDICE" in cell:
                    value = _first_number_right(row, column)
                    if value is not None:
                        ipca_index = value
                        ipca_index_month = next(
                            (month for month in (_parse_month_reference(cell) for cell in row) if month is not None),
                            None,
                        )
                        break

        if "IPCA1" in joined and "PROJECAO" in joined:
            for column, cell in enumerate(normalized):
                if "PROJECAO" in cell:
                    value = _first_number_right(row, column)
                    if value is not None:
                        ipca_projection = value
                        ipca_projection_month = next(
                            (month for month in (_parse_month_reference(cell) for cell in row) if month is not None),
                            None,
                        )
                        break

        if (
            ipca_index is not None
            and ipca_index_month is not None
            and ipca_projection is not None
            and ipca_projection_month is not None
        ):
            return IPCASnapshot(ipca_index, ipca_index_month, ipca_projection, ipca_projection_month)

    raise RuntimeError("Nao foi possivel localizar IPCA numero-indice e IPCA1 projecao no arquivo ANBIMA")


@lru_cache(maxsize=1)
def _get_ipca_inputs() -> tuple[float, float]:
    snapshot = get_ipca_snapshot()
    return snapshot.ipca_index, snapshot.ipca_projection


def _last_15_before_or_equal(value_date: dt.date) -> dt.date:
    if value_date.day >= 15:
        return dt.date(value_date.year, value_date.month, 15)

    year = value_date.year
    month = value_date.month - 1
    if month == 0:
        year -= 1
        month = 12
    return dt.date(year, month, 15)


def _add_months(value_date: dt.date, months: int) -> dt.date:
    year = value_date.year + (value_date.month - 1 + months) // 12
    month = (value_date.month - 1 + months) % 12 + 1
    return dt.date(year, month, value_date.day)


def _business_days_exclusive_inclusive(start_exclusive: dt.date, end_inclusive: dt.date) -> int:
    from utils.calendars import B3Calendar

    calendar = B3Calendar()
    current = start_exclusive + dt.timedelta(days=1)
    count = 0
    while current <= end_inclusive:
        count += int(calendar.business_days(current, current + dt.timedelta(days=1)))
        current += dt.timedelta(days=1)

    return count


def ipca_prorata(value_date: dt.date | str) -> float:
    """
    Calcula IPCA pro rata com insumos ANBIMA.

    Usa dias uteis pandas como fallback leve; para uso operacional fino, o
    calendario B3 oficial deve substituir essa contagem.
    """
    if isinstance(value_date, str):
        value_date = dt.date.fromisoformat(value_date)

    from utils.calendars import B3Calendar

    value_date = B3Calendar().get_last_business_day(value_date)
    ipca_index, ipca_projection = _get_ipca_inputs()
    anchor = _last_15_before_or_equal(value_date)
    next_anchor = _add_months(anchor, 1)

    total_days = _business_days_exclusive_inclusive(anchor, next_anchor)
    elapsed_days = _business_days_exclusive_inclusive(anchor, value_date)
    if total_days <= 0:
        raise RuntimeError("Janela de dias uteis invalida para IPCA pro rata")

    return float(ipca_index * ((1.0 + ipca_projection / 100.0) ** (elapsed_days / total_days)))
