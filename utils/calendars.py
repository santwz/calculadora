from datetime import date

import holidays
import numpy as np
import pandas as pd


class B3Calendar:
    def __init__(self, market: str = "B3"):
        self.market = market
        self._holiday_cache = {}
        self.holidays = np.array([], dtype="datetime64[D]")

    @staticmethod
    def _as_date(value):
        if isinstance(value, pd.Timestamp):
            return value.date()
        return value

    def _holidays_for_years(self, years) -> np.ndarray:
        years_tuple = tuple(sorted(set(years)))
        if years_tuple not in self._holiday_cache:
            calendar = holidays.financial_holidays(self.market, years=list(years_tuple))
            dates = sorted(calendar.keys())
            self._holiday_cache[years_tuple] = np.array(dates, dtype="datetime64[D]")

        return self._holiday_cache[years_tuple]

    def _holidays_between(self, start_date, end_date, year_padding: int = 1) -> np.ndarray:
        start_date = self._as_date(start_date)
        end_date = self._as_date(end_date)

        start_year = min(start_date.year, end_date.year) - year_padding
        end_year = max(start_date.year, end_date.year) + year_padding
        return self._holidays_for_years(range(start_year, end_year + 1))

    def _holidays_around_offset(self, start_date, days: int) -> np.ndarray:
        start_date = self._as_date(start_date)
        year_span = max(2, int(abs(days) / 252) + 2)
        return self._holidays_for_years(range(start_date.year - year_span, start_date.year + year_span + 1))

    def calendar_days(self, start_date, end_date):
        """
        Calculates the number of calendar days between start_date and end_date.
        """
        start_date = self._as_date(start_date)
        end_date = self._as_date(end_date)

        return (end_date - start_date).days

    def business_days(self, start_date, end_date):
        """
        Calculates the number of B3 business days between start_date and end_date.
        Excludes start_date (D0) following financial convention.
        """
        start_date = self._as_date(start_date)
        end_date = self._as_date(end_date)

        return np.busday_count(
            start_date,
            end_date,
            holidays=self._holidays_between(start_date, end_date),
        )

    def add_business_days(self, start_date, days):
        start_date = self._as_date(start_date)

        return np.busday_offset(
            start_date,
            days,
            roll="forward",
            holidays=self._holidays_around_offset(start_date, days),
        ).astype(date)

    def get_last_business_day(self, target_date, offset_days=0):
        """
        Gets the last B3 business day on or before target_date.

        Args:
            target_date: Reference date.
            offset_days: Number of business days to go back (0 = last BD on/before target).

        Returns:
            Last business day as date object.
        """
        target_date = self._as_date(target_date)

        holidays_array = self._holidays_around_offset(target_date, -offset_days)
        bd = np.busday_offset(
            target_date,
            0,
            roll="backward",
            holidays=holidays_array,
        ).astype(date)

        if offset_days > 0:
            bd = np.busday_offset(
                bd,
                -offset_days,
                roll="backward",
                holidays=holidays_array,
            ).astype(date)

        return bd
