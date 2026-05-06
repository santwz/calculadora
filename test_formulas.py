"""
Testes para as fórmulas de derivativos.
Baseado nos exemplos do documento LaTeX.
"""

import pytest
from datetime import date, timedelta
from utils.calculations import (
    calc_pre, calc_mtm_cdi, calc_mtm_cdi_percentual,
    calc_vc_parte, calc_vc_contra, calc_ipca, calc_sofr,
    calc_duplo_indexador, BASE_DC, BASE_DU
)
from utils.calendars import B3Calendar


class TestPreFormulas:
    """Testes para Pré-fixado (linear e exponencial)."""
    
    def test_pre_linear(self):
        """
        Exemplo do documento:
        P$ = USD 1,000,000
        c_cli = 5.00
        s = 4% a.a.
        dias = 180
        base = 360
        
        Resultado esperado: R$ 100.000,00
        """
        valor = calc_pre(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            spread=0.04,
            dias=180,
            base=BASE_DC,
            amortizacao_brl=0.0,
            method='linear'
        )
        
        assert abs(valor - 100_000.00) < 0.01, f"Esperado ~100,000.00, obtido {valor:.2f}"
    
    def test_pre_exponential(self):
        """
        Mesmo exemplo, modo exponencial.
        Resultado esperado: R$ 99.019,90
        """
        valor = calc_pre(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            spread=0.04,
            dias=180,
            base=BASE_DC,
            amortizacao_brl=0.0,
            method='exponential'
        )
        
        # (1.04)^0.5 - 1 ≈ 0.0198 → 1M * 5 * 0.0198 ≈ 99,019.90
        assert abs(valor - 99_019.90) < 1.0, f"Esperado ~99,019.90, obtido {valor:.2f}"


class TestCDIFormulas:
    """Testes para CDI."""
    
    def test_cdi_com_spread(self):
        """
        Exemplo do documento:
        P$ = USD 1,000,000
        c_cli = 5.00
        F_DI = 1.0045
        s = 2% a.a.
        período = 30/252
        
        Resultado esperado: ~R$ 6.870
        """
        valor = calc_mtm_cdi(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            fator_di=1.0045,
            spread=0.02,
            dias=30,
            base=BASE_DU,
            amortizacao_brl=0.0
        )
        
        # 5M * [1.0045 * 1.02^(30/252) - 1] ≈ 34,354
        assert abs(valor - 34_354) < 100, f"Esperado ~34,354, obtido {valor:.2f}"
    
    def test_cdi_percentual(self):
        """Teste CDI a α% sem spread."""
        valor = calc_mtm_cdi_percentual(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            fator_cdi_percentual=1.003,  # 3% acumulado
            amortizacao_brl=0.0
        )
        
        # 5M * (1.003 - 1) = 15,000
        assert abs(valor - 15_000) < 1, f"Esperado ~15,000, obtido {valor:.2f}"


class TestVCFormulas:
    """Testes para Variação Cambial."""
    
    def test_vc_parte_sem_cap(self):
        """Teste VC parte sem CAP."""
        valor = calc_vc_parte(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            cotacao_atual=5.50,
            spread=0.05,
            dias=180,
            base=BASE_DC,
            amortizacao_usd=0.0
        )
        
        # Juros = 1M * 5.50 * 0.05 * 0.5 = 137,500
        # Amort = 0
        # Total = 137,500
        assert abs(valor - 137_500) < 1, f"Esperado ~137,500, obtido {valor:.2f}"
    
    def test_vc_contra_com_cap(self):
        """Teste VC contra com CAP."""
        # Sem CAP
        valor_sem_cap = calc_vc_contra(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            cotacao_atual=6.00,  # Acima do CAP
            spread=0.05,
            dias=180,
            base=BASE_DC,
            amortizacao_usd=0.0,
            cap=5.50  # CAP em 5.50
        )
        
        # Com CAP, usa 5.50 ao invés de 6.00
        # Juros = 1M * 5.50 * 0.05 * 0.5 = 137,500
        assert abs(valor_sem_cap - 137_500) < 1, f"Esperado ~137,500, obtido {valor_sem_cap:.2f}"


class TestIPCAFormulas:
    """Testes para IPCA."""
    
    def test_ipca_capitalizado(self):
        """Teste IPCA capitalizado."""
        valor = calc_ipca(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            fator_ipca=1.05,  # 5% de inflação
            spread=0.06,  # 6% a.a. real
            dias_du=252,  # 1 ano
            amortizacao_brl=0.0,
            capitalizado=True
        )
        
        # P_cap = 5M * 1.05 = 5.25M
        # Juros = 5.25M * (1.06^1 - 1) = 5.25M * 0.06 = 315,000
        assert abs(valor - 565_000) < 100, f"Esperado ~565,000, obtido {valor:.2f}"
    
    def test_ipca_nao_capitalizado(self):
        """Teste IPCA não capitalizado."""
        valor = calc_ipca(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            fator_ipca=1.05,
            spread=0.06,
            dias_du=252,
            amortizacao_brl=0.0,
            capitalizado=False
        )
        
        # Valor = 5M * [1.05 * 1.06 - 1] = 5M * 0.113 = 565,000
        assert abs(valor - 565_000) < 100, f"Esperado ~565,000, obtido {valor:.2f}"


class TestSOFRFormulas:
    """Testes para SOFR."""
    
    def test_sofr_basic(self):
        """Teste básico SOFR."""
        valor = calc_sofr(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            cotacao_atual=5.20,
            sofr_index_inicio=1.00,
            sofr_index_fim=1.02,  # 2% de variação
            spread=0.03,  # 3% spread
            dias=180,
            base=BASE_DC,
            amortizacao_usd=0.0
        )
        
        # r_SOFR = (1.02/1.00 - 1) * 360/180 = 0.02 * 2 = 0.04 (4% anual)
        # Taxa total = 3% + 4% = 7%
        # Juros = 1M * 5.20 * 0.07 * 0.5 = 182,000
        assert abs(valor - 182_000) < 100, f"Esperado ~182,000, obtido {valor:.2f}"


class TestDuploIndexador:
    """Testes para Duplo Indexador."""
    
    def test_duplo_indexador_escolhe_pre(self):
        """Duplo indexador escolhe Pré quando é maior."""
        resultado = calc_duplo_indexador(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            cotacao_atual=5.10,  # Variação pequena
            spread_pre=0.15,  # 15% Pré (alto)
            spread_vc=0.05,
            dias_du=252,
            dias_dc=360,
            amortizacao_usd=0.0,
            cap=0.0,
            use_vc_contra=False
        )
        
        assert resultado['opcao_escolhida'] == 'Pré', "Deveria escolher Pré"
        assert resultado['valor_final'] == resultado['opcao_a']
    
    def test_duplo_indexador_escolhe_vc(self):
        """Duplo indexador escolhe VC quando é maior."""
        resultado = calc_duplo_indexador(
            principal_usd=1_000_000,
            cotacao_cliente=5.00,
            cotacao_atual=6.50,  # Grande variação cambial
            spread_pre=0.05,  # Pré baixo
            spread_vc=0.10,
            dias_du=252,
            dias_dc=360,
            amortizacao_usd=0.0,
            cap=0.0,
            use_vc_contra=False
        )
        
        assert resultado['opcao_escolhida'] == 'VC', "Deveria escolher VC"
        assert resultado['valor_final'] == resultado['opcao_b']


class TestCalendar:
    """Testes para funções de calendário."""
    
    def test_calendar_days(self):
        """Teste contagem dias corridos."""
        calendar = B3Calendar()
        
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        
        dias = calendar.calendar_days(start, end)
        assert dias == 30, f"Esperado 30 dias, obtido {dias}"
    
    def test_business_days(self):
        """Teste contagem dias úteis."""
        calendar = B3Calendar()
        
        start = date(2024, 1, 1)  # Segunda-feira
        end = date(2024, 1, 8)    # Segunda-feira seguinte
        
        # De segunda a segunda (7 dias) = 5 dias úteis (excluindo D0)
        dias = calendar.business_days(start, end)
        # busday_count conta de start até end, excluindo start
        assert dias >= 4, f"Esperado >=4 dias úteis, obtido {dias}"

    def test_2026_holiday_is_not_business_day(self):
        calendar = B3Calendar()

        dias = calendar.business_days(date(2026, 1, 1), date(2026, 1, 2))

        assert dias == 0

    def test_future_mobile_b3_holidays_are_not_business_days(self):
        calendar = B3Calendar()

        holiday_dates = [
            date(2030, 3, 4),   # Carnaval
            date(2030, 3, 5),   # Carnaval
            date(2030, 4, 19),  # Sexta-feira Santa
            date(2030, 6, 20),  # Corpus Christi
        ]

        for holiday_date in holiday_dates:
            assert calendar.business_days(holiday_date, holiday_date + timedelta(days=1)) == 0

    def test_get_last_business_day_respects_future_mobile_holiday(self):
        calendar = B3Calendar()

        assert calendar.get_last_business_day(date(2030, 3, 5)) == date(2030, 3, 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
