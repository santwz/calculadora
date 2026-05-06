"""
Script de teste para validar a integração com o BCB.
"""
import os

import pytest

from utils.market_data import BCBDataFetcher
from datetime import date

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Defina RUN_INTEGRATION_TESTS=1 para rodar testes que chamam APIs externas.",
)

def test_cdi():
    print("=== Teste CDI ===")
    start = date(2024, 1, 2)
    end = date(2025, 12, 11)
    
    fator = BCBDataFetcher.get_cdi_factor(start, end)
    print(f"Fator CDI ({start} -> {end}): {fator:.6f}")
    print(f"Variação: {(fator - 1) * 100:.4f}%")
    print()

def test_ptax():
    print("=== Teste PTAX ===")
    target = date(2024, 12, 10)
    
    ptax = BCBDataFetcher.get_ptax(target)
    print(f"PTAX em {target}: R$ {ptax:.4f}")
    print()

def test_ipca():
    print("=== Teste IPCA/VNA ===")
    start = date(2024, 1, 1)
    end = date(2024, 11, 30)
    
    vna = BCBDataFetcher.calculate_ipca_vna(start, end, vna_base=4000.0)
    print(f"VNA projetado ({start} -> {end}): {vna:.2f}")
    print()

def test_ipca_pro_rata():
    print("=== IPCA Pro Rata Index - Last Price (Bloomberg Style) ===\n")
    
    # Obtém o Last Price
    result = BCBDataFetcher.get_ipca_pro_rata_last_price()
    
    print(f"BRAZIL IPCA PRO RATA INDEX")
    print(f"{'=' * 60}")
    print(f"Last Price:        {result['index']:>15,.2f}")
    print(f"As of Date:        {result['date']}")
    print(f"-" * 60)
    print(f"1D Change:         {result['variation_1d']:>14.4f}%")
    print(f"MTD Change:        {result['variation_mtd']:>14.4f}%")
    print(f"YTD Change:        {result['variation_ytd']:>14.4f}%")
    print(f"{'=' * 60}")
    print(f"Base: 01/07/2015 = 1000.00\n")
    
    # Teste adicional: histórico de alguns dias
    print("=== Histórico (últimos dias disponíveis) ===\n")
    print(f"{'Data':<12} {'Índice':<15} {'Var % 1D':<12}")
    print("-" * 40)
    
    from datetime import timedelta
    base_date = date(2015, 7, 1)
    base_index = 1000.0
    
    # Mostra últimos 10 dias com dados disponíveis (Nov 2024)
    test_dates = [date(2024, 11, i) for i in range(21, 31)]
    
    prev_idx = None
    for target_date in test_dates:
        idx = BCBDataFetcher.get_ipca_pro_rata_index(
            target_date,
            base_date=base_date,
            base_index=base_index
        )
        
        if prev_idx:
            var = ((idx / prev_idx) - 1) * 100
            print(f"{target_date} {idx:>13.2f}   {var:>10.6f}%")
        else:
            print(f"{target_date} {idx:>13.2f}   {'---':>10}")
        
        prev_idx = idx
    
    print()


if __name__ == '__main__':
    test_cdi()
    test_ptax()
    test_ipca()
    test_ipca_pro_rata()
