from datetime import date

import pytest

from models.leg import CDILeg, PreLeg, VCLeg
from utils.calendars import B3Calendar


class TestFinancials:
    def setup_method(self):
        self.calendar = B3Calendar()
        self.start = date(2023, 1, 2)
        self.end = date(2024, 1, 2)

    def test_calendar_days(self):
        du = self.calendar.business_days(self.start, self.end)
        assert 248 <= du <= 255

    def test_pre_leg(self):
        du = self.calendar.business_days(self.start, self.end)

        leg = PreLeg(1000.0, self.start, self.end, 0.10, cotacao_cliente=5.0)
        fv = leg.calculate_future_value(self.calendar)

        expected = 1000.0 * 5.0 * (1.10) ** (du / 252)
        assert fv == pytest.approx(expected)

    def test_cdi_leg(self):
        du = self.calendar.business_days(self.start, self.end)
        cdi_factor = (1.10) ** (du / 252)
        leg = CDILeg(
            1000.0,
            self.start,
            self.end,
            cdi_factor=cdi_factor,
            spread=0.0,
            percent=1.0,
            cotacao_cliente=5.0,
        )
        fv = leg.calculate_future_value(self.calendar)

        expected = 1000.0 * 5.0 * (1.10) ** (du / 252)
        assert fv == pytest.approx(expected)

    def test_vc_leg(self):
        dc = self.calendar.calendar_days(self.start, self.end)
        leg = VCLeg(
            1000.0,
            self.start,
            self.end,
            spot_start=5.0,
            spot_end=5.5,
            coupon=0.05,
        )
        fv = leg.calculate_future_value(self.calendar)

        expected = 1000.0 * 5.5 + 1000.0 * 5.5 * 0.05 * (dc / 360)
        assert fv == pytest.approx(expected)
