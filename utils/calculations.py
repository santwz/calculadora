"""
Módulo de Cálculos de Derivativos
Implementa todas as fórmulas conforme documento LaTeX de especificação.

Convenções:
- BASE_DC: Base em dias corridos (tipicamente 360)
- BASE_DU: Base em dias úteis (tipicamente 252)
- dias_DC: dias corridos entre datas
- dias_DU: dias úteis (busday_count - 1, excluindo D0)
- período: dias / base
"""

import numpy as np
from datetime import date, timedelta

# Constantes
BASE_DC = 360  # Base dias corridos
BASE_DU = 252  # Base dias úteis


def calc_pre(principal_usd: float, 
             cotacao_cliente: float,
             spread: float,
             dias: int,
             base: int = BASE_DC,
             amortizacao_brl: float = 0.0,
             method: str = 'exponential') -> float:
    """
    Calcula Pré-fixado (linear ou exponencial).
    
    Fórmulas:
    - Linear: Valor = P$ * c_cli * s * período + A * c_cli
    - Exponencial: Valor = P$ * c_cli * [(1+s)^período - 1] + A * c_cli
    
    Args:
        principal_usd: Principal em USD (P$)
        cotacao_cliente: Cotação cliente no início (c_cli)
        spread: Taxa anual (s) como decimal (ex: 0.04 para 4%)
        dias: Número de dias (DC ou DU conforme base)
        base: Base de cálculo (360 para DC, 252 para DU)
        amortizacao_brl: Amortização em BRL (A)
        method: 'linear' ou 'exponential'
    
    Returns:
        Valor em BRL
    """
    periodo = dias / base
    principal_brl = principal_usd * cotacao_cliente
    
    if method == 'linear':
        juros = principal_brl * spread * periodo
    else:  # exponential
        juros = principal_brl * ((1 + spread) ** periodo - 1)
    
    amort_ajustada = amortizacao_brl * cotacao_cliente
    
    return juros + amort_ajustada


def calc_mtm_cdi(principal_usd: float,
                 cotacao_cliente: float,
                 fator_di: float,
                 spread: float,
                 dias: int,
                 base: int = BASE_DU,
                 amortizacao_brl: float = 0.0) -> float:
    """
    Calcula CDI com spread.
    
    Fórmula: Valor = P$ * c_cli * [F_DI * (1+s)^período - 1] + A
    
    Args:
        principal_usd: Principal em USD
        cotacao_cliente: Cotação cliente
        fator_di: Fator DI acumulado obtido do BCB
        spread: Spread anual como decimal
        dias: Dias úteis (DU_incl - 1)
        base: Base de cálculo (tipicamente 252)
        amortizacao_brl: Amortização em BRL
    
    Returns:
        Valor em BRL
    """
    periodo = dias / base
    principal_brl = principal_usd * cotacao_cliente
    
    fator_total = fator_di * ((1 + spread) ** periodo)
    valor = principal_brl * (fator_total - 1) + amortizacao_brl
    
    return valor


def calc_mtm_cdi_percentual(principal_usd: float,
                            cotacao_cliente: float,
                            fator_cdi_percentual: float,
                            amortizacao_brl: float = 0.0) -> float:
    """
    Calcula CDI a α% (sem spread, sem FX, sem CAP).
    
    Fórmula: Valor = P$ * c_cli * [F_α_CDI - 1] + A
    
    Onde F_α_CDI é o fator CDI ponderado por α calculado como:
    F_α_CDI = ∏(1 + α * r_CDI_d) para cada dia d
    
    Args:
        principal_usd: Principal em USD
        cotacao_cliente: Cotação cliente
        fator_cdi_percentual: Fator CDI ponderado já calculado
        amortizacao_brl: Amortização em BRL
    
    Returns:
        Valor em BRL
    """
    principal_brl = principal_usd * cotacao_cliente
    valor = principal_brl * (fator_cdi_percentual - 1) + amortizacao_brl
    
    return valor


def calc_vc_parte(principal_usd: float,
                  cotacao_cliente: float,
                  cotacao_atual: float,
                  spread: float,
                  dias: int,
                  base: int = BASE_DC,
                  amortizacao_usd: float = 0.0) -> float:
    """
    Calcula Variação Cambial - Parte (sem CAP).
    
    Fórmulas:
    - Juros = P$ * c_atual * s * período
    - Amortização ajustada = A * (c_atual / c_cli)
    - Valor = Juros + Amortização ajustada
    
    Args:
        principal_usd: Principal em USD
        cotacao_cliente: Cotação cliente no início
        cotacao_atual: Cotação de mercado atual
        spread: Spread anual como decimal
        dias: Número de dias
        base: Base de cálculo
        amortizacao_usd: Amortização em USD
    
    Returns:
        Valor em BRL
    """
    periodo = dias / base
    juros = principal_usd * cotacao_atual * spread * periodo
    
    fx_ratio = cotacao_atual / cotacao_cliente
    amort_ajustada = amortizacao_usd * fx_ratio
    
    return juros + amort_ajustada


def calc_vc_contra(principal_usd: float,
                   cotacao_cliente: float,
                   cotacao_atual: float,
                   spread: float,
                   dias: int,
                   base: int = BASE_DC,
                   amortizacao_usd: float = 0.0,
                   cap: float = 0.0) -> float:
    """
    Calcula Variação Cambial - Contra-parte (com CAP opcional).
    
    Se cap > 0: c_cap = min(c_atual, cap)
    Senão: c_cap = c_atual
    
    Valor = P$ * c_cap * s * período + A * (c_cap / c_cli)
    
    Args:
        principal_usd: Principal em USD
        cotacao_cliente: Cotação cliente no início
        cotacao_atual: Cotação de mercado atual
        spread: Spread anual como decimal
        dias: Número de dias
        base: Base de cálculo
        amortizacao_usd: Amortização em USD
        cap: CAP opcional (0 = sem CAP)
    
    Returns:
        Valor em BRL
    """
    # Aplicar CAP se especificado
    if cap > 0:
        cotacao_cap = min(cotacao_atual, cap)
    else:
        cotacao_cap = cotacao_atual
    
    periodo = dias / base
    juros = principal_usd * cotacao_cap * spread * periodo
    
    fx_ratio = cotacao_cap / cotacao_cliente
    amort_ajustada = amortizacao_usd * fx_ratio
    
    return juros + amort_ajustada


def calc_ipca(principal_usd: float,
              cotacao_cliente: float,
              fator_ipca: float,
              spread: float,
              dias_du: int,
              amortizacao_brl: float = 0.0,
              capitalizado: bool = True) -> float:
    """
    Calcula IPCA (capitalizado ou não capitalizado).
    
    Capitalizado (capitalizado=True):
        P_BRL_cap = P$ * c_cli * F_IPCA
        A_cap = A * F_IPCA
        Valor = P_BRL_cap * [(1+s)^período - 1] + A_cap
    
    Não Capitalizado (capitalizado=False):
        P_BRL = P$ * c_cli
        Valor = P_BRL * [F_IPCA * (1+s)^período - 1] + A
    
    Args:
        principal_usd: Principal em USD
        cotacao_cliente: Cotação cliente
        fator_ipca: Fator IPCA (I_final / I_inicial)
        spread: Taxa real anual como decimal
        dias_du: Dias úteis (DU_incl - 1)
        amortizacao_brl: Amortização em BRL
        capitalizado: Se True, usa modo capitalizado
    
    Returns:
        Valor em BRL
    """
    periodo = dias_du / BASE_DU
    principal_brl = principal_usd * cotacao_cliente
    
    if capitalizado:
        principal_cap = principal_brl * fator_ipca
        amort_cap = amortizacao_brl * fator_ipca
        
        valor = principal_cap * ((1 + spread) ** periodo) - principal_brl
        return valor + amort_cap
    else:
        # Não capitalizado: fator IPCA multiplica o termo completo
        fator_total = fator_ipca * ((1 + spread) ** periodo)
        valor = principal_brl * (fator_total - 1) + amortizacao_brl
        return valor


def calc_sofr(principal_usd: float,
              cotacao_cliente: float,
              cotacao_atual: float,
              sofr_index_inicio: float,
              sofr_index_fim: float,
              spread: float,
              dias: int,
              base: int = BASE_DC,
              amortizacao_usd: float = 0.0) -> float:
    """
    Calcula SOFR.
    
    Taxa SOFR anualizada:
        r_SOFR_anual = (Index_fim / Index_inicio - 1) * (360 / dias)
    
    Fórmula:
        Valor = P$ * c_atual * (s + r_SOFR_anual) * período + A * (c_atual / c_cli)
    
    Nota: As datas de início e fim devem ser ajustadas T-2 úteis antes de 
    consultar os índices SOFR.
    
    Args:
        principal_usd: Principal em USD
        cotacao_cliente: Cotação cliente
        cotacao_atual: Cotação atual
        sofr_index_inicio: Índice SOFR na data início (T-2 ajustada)
        sofr_index_fim: Índice SOFR na data fim (T-2 ajustada)
        spread: Spread anual como decimal
        dias: Número de dias
        base: Base de cálculo (tipicamente 360)
        amortizacao_usd: Amortização em USD
    
    Returns:
        Valor em BRL
    """
    if dias <= 0:
        return 0.0

    periodo = dias / base
    
    # Calcular taxa SOFR anualizada
    if sofr_index_inicio > 0 and sofr_index_fim > 0:
        r_sofr_anual = (sofr_index_fim / sofr_index_inicio - 1) * (360 / dias)
    else:
        r_sofr_anual = 0.0  # Se índices não disponíveis
    
    # Taxa total (spread + SOFR)
    taxa_total = spread + r_sofr_anual
    
    # Juros em BRL
    juros = principal_usd * cotacao_atual * taxa_total * periodo
    
    # Amortização ajustada
    fx_ratio = cotacao_atual / cotacao_cliente
    amort_ajustada = amortizacao_usd * fx_ratio
    
    return juros + amort_ajustada


def calc_duplo_indexador(principal_usd: float,
                         cotacao_cliente: float,
                         cotacao_atual: float,
                         spread_pre: float,
                         spread_vc: float,
                         dias_du: int,
                         dias_dc: int,
                         amortizacao_usd: float = 0.0,
                         cap: float = 0.0,
                         use_vc_contra: bool = True,
                         cap_target: str = "vc") -> dict:
    """
    Calcula Duplo Indexador (máximo entre Pré exponencial e VC).
    
    Opção A: Pré Exponencial
        Valor_A = P$ * c_cli * [(1+s)^(DU/252) - 1] + A
    
    Opção B: Variação Cambial (parte ou contra)
        Usa calc_vc_parte ou calc_vc_contra
    
    Resultado: max(Opção A, Opção B)
    
    Args:
        principal_usd: Principal em USD
        cotacao_cliente: Cotação cliente
        cotacao_atual: Cotação atual
        spread_pre: Spread para pré-fixado
        spread_vc: Spread para variação cambial
        dias_du: Dias úteis
        dias_dc: Dias corridos
        amortizacao_usd: Amortização em USD (convertida para BRL em pré)
        cap: CAP para VC (se use_vc_contra=True)
        use_vc_contra: Se True usa VC contra, senão usa VC parte
    
    Returns:
        Dict com opcao_a, opcao_b, valor_final, e opcao_escolhida
    """
    # Opção A: Pré Exponencial com amortização em BRL
    amortizacao_brl = amortizacao_usd * cotacao_cliente
    opcao_a = calc_pre(
        principal_usd=principal_usd,
        cotacao_cliente=cotacao_cliente,
        spread=spread_pre,
        dias=dias_du,
        base=BASE_DU,
        amortizacao_brl=amortizacao_brl,
        method='exponential'
    )
    
    def _calc_vc_component(cotacao_vc: float) -> float:
        if use_vc_contra:
            valor_vc = calc_vc_contra(
                principal_usd=principal_usd,
                cotacao_cliente=cotacao_cliente,
                cotacao_atual=cotacao_vc,
                spread=spread_vc,
                dias=dias_dc,
                base=BASE_DC,
                amortizacao_usd=amortizacao_usd,
                cap=0.0
            )
        else:
            valor_vc = calc_vc_parte(
                principal_usd=principal_usd,
                cotacao_cliente=cotacao_cliente,
                cotacao_atual=cotacao_vc,
                spread=spread_vc,
                dias=dias_dc,
                base=BASE_DC,
                amortizacao_usd=amortizacao_usd
            )

        return valor_vc + principal_usd * (cotacao_vc - cotacao_cliente)

    componente_vc_antes_cap = _calc_vc_component(cotacao_atual)
    cap_aplicado = cap if cap_target == "vc" and cap > 0 else 0.0
    cotacao_vc_apos_cap = min(cotacao_atual, cap_aplicado) if cap_aplicado > 0 else cotacao_atual
    componente_vc_apos_cap = _calc_vc_component(cotacao_vc_apos_cap)
    
    # Escolher o máximo
    valor_final = max(opcao_a, componente_vc_apos_cap)
    componente_escolhido = 'Pré' if opcao_a >= componente_vc_apos_cap else 'VC'
    
    return {
        'opcao_a': opcao_a,
        'opcao_b': componente_vc_apos_cap,
        'valor_final': valor_final,
        'opcao_escolhida': componente_escolhido,
        'componente_pre': opcao_a,
        'componente_vc_antes_cap': componente_vc_antes_cap,
        'componente_vc_apos_cap': componente_vc_apos_cap,
        'cap_aplicado': cap_aplicado,
        'componente_escolhido': componente_escolhido
    }
