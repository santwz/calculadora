from datetime import date

from utils.vc_inputs import resolve_vc_spots


def test_auto_ptax_keeps_manual_initial_spot_and_fetches_only_final_spot():
    calls = []

    def fake_fetch_ptax(target_date):
        calls.append(target_date)
        return 5.4321

    params = {
        "auto_ptax": True,
        "spot_start": 5.1111,
        "spot_end": 9.9999,
    }

    spot_start, spot_end = resolve_vc_spots(
        params,
        start=date(2024, 1, 2),
        end=date(2024, 7, 2),
        fetch_ptax=fake_fetch_ptax,
    )

    assert spot_start == 5.1111
    assert spot_end == 5.4321
    assert calls == [date(2024, 7, 2)]


def test_manual_ptax_uses_both_manual_spots_without_fetching():
    def fail_if_called(target_date):
        raise AssertionError("PTAX fetch should not run for manual VC spots")

    params = {
        "auto_ptax": False,
        "spot_start": 5.1111,
        "spot_end": 5.2222,
    }

    spot_start, spot_end = resolve_vc_spots(
        params,
        start=date(2024, 1, 2),
        end=date(2024, 7, 2),
        fetch_ptax=fail_if_called,
    )

    assert spot_start == 5.1111
    assert spot_end == 5.2222
