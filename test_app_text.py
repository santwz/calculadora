from pathlib import Path


def test_app_uses_active_passive_labels_instead_of_side_a_b_labels():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "Tipo da Ponta {side_label}" in app_source
    assert 'configure_leg("A", "Ativa", cotacao_cliente_global)' in app_source
    assert 'configure_leg("B", "Passiva", cotacao_cliente_global)' in app_source


def test_app_shows_explicit_duplo_indexador_cap_and_component_labels():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "Aplicar CAP" in app_source
    assert "No componente VC" in app_source
    assert "Componente Pré" in app_source
    assert "Componente VC antes do CAP" in app_source
    assert "Componente VC após CAP" in app_source


def test_app_exposes_calculation_memory_download_button():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "build_calculation_memory_xlsx" in app_source
    assert "Baixar memória de cálculo (.xlsx)" in app_source
    assert "st.download_button" in app_source


def test_app_keeps_global_inputs_in_main_calculator_area_not_sidebar():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "st.sidebar" not in app_source
    assert "Configuração do Swap" in app_source
    assert 'st.text_input("Notional (USD)"' in app_source
    assert 'st.date_input("Data Início"' in app_source
    assert 'st.date_input("Data Vencimento"' in app_source


def test_app_defaults_dates_to_recent_swap_window():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "today = date.today()" in app_source
    assert 'st.date_input("Data Início", value=shift_months(today, -2))' in app_source
    assert 'st.date_input("Data Vencimento", value=shift_months(today, -1))' in app_source


def test_app_ipca_auto_uses_manual_initial_vna_and_months_back_for_final_vna():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "Meses para trás" in app_source
    assert "min_value=-120" in app_source
    assert "IPCA Inicial (VNA)" in app_source
    assert "resolve_ipca_auto_vnas" in app_source
    assert "VNA Base" not in app_source


def test_app_ipca_auto_allows_manual_initial_ipca_registration():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "IPCA Inicial (VNA)" in app_source
    assert "initial_vna=" in app_source


def test_app_has_single_global_client_fx_quote():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert 'cotacao_cliente_global = st.number_input("Cotação Cliente (USD/BRL)"' in app_source
    assert 'def configure_leg(prefix, side_label, cotacao_cliente):' in app_source
    assert "params['cotacao'] = cotacao_cliente" in app_source
    assert "params['spot_start'] = cotacao_cliente" in app_source
    assert "params['cotacao_cliente'] = cotacao_cliente" in app_source
    assert 'st.number_input(f"Cotação Cliente {side_label}"' not in app_source
    assert 'st.number_input(f"Cotação Inicial {side_label}"' not in app_source


def test_app_formats_notional_usd_with_ptbr_grouping():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "format_ptbr_number" in app_source
    assert "parse_ptbr_number" in app_source
    assert "value=format_ptbr_number(1_000_000.0)" in app_source
    assert 'f"US$ {format_ptbr_number(notional, 2)}"' in app_source
