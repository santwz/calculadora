from datetime import date

import pytest

from models.leg import CDILeg, PreLeg, SOFRLeg, VCLeg
from models.swap import Swap
from utils.calendars import B3Calendar
from utils.market_data import BCBDataFetcher
from utils.calculations import calc_duplo_indexador


class FixedBusinessDaysCalendar(B3Calendar):
    def __init__(self, business_days):
        super().__init__()
        self._business_days = business_days

    def business_days(self, start_date, end_date):
        return self._business_days


def test_swap_flows_subtract_initial_value_in_brl():
    calendar = B3Calendar()
    start = date(2024, 1, 2)
    end = date(2024, 7, 2)
    long_leg = PreLeg(1_000_000, start, end, 0.0, cotacao_cliente=5.0)
    short_leg = PreLeg(1_000_000, start, end, 0.0, cotacao_cliente=5.0)

    result = Swap(long_leg, short_leg).calculate_net_value(calendar)

    assert result["flow_long"] == pytest.approx(0.0)
    assert result["flow_short"] == pytest.approx(0.0)


def test_vc_future_value_revalues_principal_at_final_spot():
    calendar = B3Calendar()
    leg = VCLeg(
        1_000_000,
        date(2024, 1, 2),
        date(2024, 7, 2),
        spot_start=5.0,
        spot_end=5.5,
        coupon=0.0,
    )

    assert leg.calculate_future_value(calendar) == pytest.approx(5_500_000.0)
    assert leg.calculate_flow(calendar) == pytest.approx(500_000.0)


def test_sofr_future_value_revalues_principal_at_final_spot_and_index_accrual():
    calendar = B3Calendar()
    leg = SOFRLeg(
        1_000_000,
        date(2024, 1, 1),
        date(2024, 6, 29),
        sofr_index_start=1.00,
        sofr_index_end=1.02,
        spot_start=5.0,
        spot_end=5.2,
        coupon=0.03,
    )

    # 2% SOFR index accrual over the period plus 3% annual spread for 180/360.
    assert leg.calculate_future_value(calendar) == pytest.approx(5_382_000.0)
    assert leg.calculate_flow(calendar) == pytest.approx(382_000.0)


def test_cdi_percentual_manual_uses_equivalent_daily_weighting():
    calendar = FixedBusinessDaysCalendar(20)
    start = date(2024, 1, 2)
    end = date(2024, 1, 30)
    cdi_factor = 1.02**20
    leg = CDILeg(
        1_000_000,
        start,
        end,
        cdi_factor=cdi_factor,
        percent=0.5,
        use_percentual_method=True,
        cotacao_cliente=5.0,
    )

    expected_factor = 1.01**20
    expected_fv = 5_000_000 * expected_factor

    assert leg.calculate_future_value(calendar) == pytest.approx(expected_fv)


def test_sofr_index_fetches_latest_official_index_on_or_before_target(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "refRates": [
                    {
                        "effectiveDate": "2024-01-05",
                        "type": "SOFRAI",
                        "index": 1.11577724,
                    },
                    {
                        "effectiveDate": "2024-01-04",
                        "type": "SOFRAI",
                        "index": 1.11561237,
                    },
                ]
            }

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params, timeout))
        return FakeResponse()

    monkeypatch.setattr("utils.market_data.requests.get", fake_get)

    index = BCBDataFetcher.get_sofr_index(date(2024, 1, 6))

    assert index == pytest.approx(1.11577724)
    assert calls
    assert "markets.newyorkfed.org" in calls[0][0]


def test_ipca_vna_prefers_anbima_prorata_factor(monkeypatch):
    monkeypatch.setattr(
        BCBDataFetcher,
        "get_ipca_anbima_factor",
        staticmethod(lambda start, end: 1.10),
    )

    def fail_if_called(start, end):
        raise AssertionError("BCB fallback should not be used when ANBIMA factor exists")

    monkeypatch.setattr(BCBDataFetcher, "get_ipca_factor", staticmethod(fail_if_called))

    vna = BCBDataFetcher.calculate_ipca_vna(
        date(2024, 1, 2),
        date(2024, 2, 2),
        vna_base=4_000.0,
    )

    assert vna == pytest.approx(4_400.0)


def test_ipca_auto_vnas_use_sidra_number_index_history_not_anbima(monkeypatch):
    sidra_payload = [
        {"V": "Valor", "D3C": "Mês (Código)"},
        {"V": "7323.9100000000000", "D3C": "202508"},
        {"V": "7359.0600000000000", "D3C": "202509"},
        {"V": "7365.6800000000000", "D3C": "202510"},
        {"V": "7378.9400000000000", "D3C": "202511"},
        {"V": "7403.2900000000000", "D3C": "202512"},
        {"V": "7427.7200000000000", "D3C": "202601"},
        {"V": "7479.7100000000000", "D3C": "202602"},
        {"V": "7545.5300000000000", "D3C": "202603"},
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return sidra_payload

    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        assert "apisidra.ibge.gov.br" in url
        assert "/v/2266/" in url
        return FakeResponse()

    def fail_old_anbima_path(*args, **kwargs):
        raise AssertionError("IPCA automatico nao deve usar ANBIMA quando ha historico de numero-indice")

    monkeypatch.setattr("utils.market_data.requests.get", fake_get)
    monkeypatch.setattr(BCBDataFetcher, "get_ipca_vna_months_back", staticmethod(fail_old_anbima_path))
    monkeypatch.setattr("utils.anbima.ipca_prorata", fail_old_anbima_path)

    resolved = BCBDataFetcher.resolve_ipca_auto_vnas(
        date(2026, 5, 4),
        months_back=0,
        initial_vna=7_323.91,
    )

    assert calls
    assert resolved["vna_start"] == pytest.approx(7_323.91)
    assert resolved["vna_end"] == pytest.approx(7_545.53)
    assert resolved["reference_month"] == "Manual"
    assert resolved["final_month"] == "2026-03"
    assert resolved["source"] == "Manual + IBGE SIDRA 1737/2266"


def test_ipca_auto_vnas_use_disclosed_previous_month_when_maturity_passed_release_month(monkeypatch):
    sidra_payload = [
        {"V": "Valor", "D3C": "Mês (Código)"},
        {"V": "7427.7200000000000", "D3C": "202601"},
        {"V": "7479.7100000000000", "D3C": "202602"},
        {"V": "7545.5300000000000", "D3C": "202603"},
        {"V": "7596.0800000000000", "D3C": "202604"},
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return sidra_payload

    monkeypatch.setattr("utils.market_data.requests.get", lambda url, timeout=None: FakeResponse())

    resolved = BCBDataFetcher.resolve_ipca_auto_vnas(
        date(2026, 5, 20),
        months_back=0,
        initial_vna=7_403.29,
    )

    assert resolved["vna_start"] == pytest.approx(7_403.29)
    assert resolved["vna_end"] == pytest.approx(7_596.08)
    assert resolved["reference_month"] == "Manual"
    assert resolved["final_month"] == "2026-04"
    assert resolved["source"] == "Manual + IBGE SIDRA 1737/2266"


def test_ipca_auto_vnas_apply_months_back_to_final_index(monkeypatch):
    sidra_payload = [
        {"V": "Valor", "D3C": "Mês (Código)"},
        {"V": "7479.7100000000000", "D3C": "202602"},
        {"V": "7545.5300000000000", "D3C": "202603"},
        {"V": "7596.0800000000000", "D3C": "202604"},
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return sidra_payload

    monkeypatch.setattr("utils.market_data.requests.get", lambda url, timeout=None: FakeResponse())

    resolved = BCBDataFetcher.resolve_ipca_auto_vnas(
        date(2026, 5, 20),
        months_back=1,
        initial_vna=7_403.29,
    )

    assert resolved["vna_start"] == pytest.approx(7_403.29)
    assert resolved["vna_end"] == pytest.approx(7_596.08)
    assert resolved["final_month"] == "2026-04"


def test_ipca_auto_vnas_treats_positive_and_negative_months_back_as_same_offset(monkeypatch):
    sidra_payload = [
        {"V": "Valor", "D3C": "Mes (Codigo)"},
        {"V": "7427.7200000000000", "D3C": "202601"},
        {"V": "7479.7100000000000", "D3C": "202602"},
        {"V": "7545.5300000000000", "D3C": "202603"},
        {"V": "7596.0800000000000", "D3C": "202604"},
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return sidra_payload

    monkeypatch.setattr("utils.market_data.requests.get", lambda url, timeout=None: FakeResponse())

    positive = BCBDataFetcher.resolve_ipca_auto_vnas(
        date(2026, 5, 20),
        months_back=2,
        initial_vna=7_403.29,
    )
    negative = BCBDataFetcher.resolve_ipca_auto_vnas(
        date(2026, 5, 20),
        months_back=-2,
        initial_vna=7_403.29,
    )

    assert positive["vna_end"] == pytest.approx(7_545.53)
    assert negative["vna_end"] == pytest.approx(positive["vna_end"])
    assert positive["final_month"] == negative["final_month"] == "2026-03"


def test_ipca_auto_vnas_minus_one_uses_month_before_maturity_when_available(monkeypatch):
    sidra_payload = [
        {"V": "Valor", "D3C": "Mês (Código)"},
        {"V": "7545.5300000000000", "D3C": "202603"},
        {"V": "7596.0800000000000", "D3C": "202604"},
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return sidra_payload

    monkeypatch.setattr("utils.market_data.requests.get", lambda url, timeout=None: FakeResponse())

    resolved = BCBDataFetcher.resolve_ipca_auto_vnas(
        date(2026, 5, 20),
        months_back=-1,
        initial_vna=7_403.29,
    )

    assert resolved["vna_end"] == pytest.approx(7_596.08)
    assert resolved["final_month"] == "2026-04"


def test_ipca_auto_vnas_minus_one_falls_back_to_latest_available_when_previous_month_missing(monkeypatch):
    sidra_payload = [
        {"V": "Valor", "D3C": "Mês (Código)"},
        {"V": "7479.7100000000000", "D3C": "202602"},
        {"V": "7545.5300000000000", "D3C": "202603"},
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return sidra_payload

    monkeypatch.setattr("utils.market_data.requests.get", lambda url, timeout=None: FakeResponse())

    resolved = BCBDataFetcher.resolve_ipca_auto_vnas(
        date(2026, 5, 20),
        months_back=-1,
        initial_vna=7_403.29,
    )

    assert resolved["vna_end"] == pytest.approx(7_545.53)
    assert resolved["final_month"] == "2026-03"


def test_ipca_prorata_uses_b3_business_days_for_projection(monkeypatch):
    from utils import anbima

    monkeypatch.setattr(anbima, "_get_ipca_inputs", lambda: (7_545.53, 0.67))

    projected = anbima.ipca_prorata(date(2026, 5, 4))

    assert projected == pytest.approx(7_545.53 * ((1 + 0.0067) ** (11 / 20)))


def test_duplo_indexador_reports_pre_vc_before_and_after_cap():
    result = calc_duplo_indexador(
        principal_usd=1_000_000,
        cotacao_cliente=5.0,
        cotacao_atual=6.5,
        spread_pre=0.05,
        spread_vc=0.10,
        dias_du=252,
        dias_dc=360,
        cap=5.5,
        cap_target="vc",
        use_vc_contra=False,
    )

    assert result["componente_pre"] == pytest.approx(250_000.0)
    assert result["componente_vc_antes_cap"] == pytest.approx(2_150_000.0)
    assert result["componente_vc_apos_cap"] == pytest.approx(1_050_000.0)
    assert result["cap_aplicado"] == pytest.approx(5.5)
    assert result["componente_escolhido"] == "VC"
    assert result["valor_final"] == pytest.approx(1_050_000.0)


def test_duplo_indexador_can_ignore_cap_value_when_cap_target_is_none():
    result = calc_duplo_indexador(
        principal_usd=1_000_000,
        cotacao_cliente=5.0,
        cotacao_atual=6.5,
        spread_pre=0.05,
        spread_vc=0.10,
        dias_du=252,
        dias_dc=360,
        cap=5.5,
        cap_target="none",
        use_vc_contra=False,
    )

    assert result["componente_vc_antes_cap"] == pytest.approx(2_150_000.0)
    assert result["componente_vc_apos_cap"] == pytest.approx(2_150_000.0)
    assert result["cap_aplicado"] == 0.0
    assert result["valor_final"] == pytest.approx(2_150_000.0)
