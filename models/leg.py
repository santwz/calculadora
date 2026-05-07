from abc import ABC, abstractmethod
from typing import Optional
import numpy as np
from utils.calculations import (
    calc_pre, calc_mtm_cdi, calc_mtm_cdi_percentual,
    calc_vc_parte, calc_vc_contra, calc_ipca, calc_sofr,
    calc_duplo_indexador, BASE_DC, BASE_DU
)

class SwapLeg(ABC):
    def __init__(self, notional: float, start_date, end_date, currency: str = "USD"):
        self.notional = notional
        self.start_date = start_date
        self.end_date = end_date
        self.currency = currency
    
    @abstractmethod
    def calculate_future_value(self, calendar) -> float:
        pass

    def calculate_initial_value(self) -> float:
        return self.notional

    def calculate_flow(self, calendar) -> float:
        fv = self.calculate_future_value(calendar)
        return fv - self.calculate_initial_value()


class PreLeg(SwapLeg):
    def __init__(self, notional, start_date, end_date, rate: float, 
                 method: str = 'exponential', base: int = BASE_DU,
                 cotacao_cliente: float = 1.0, amortizacao: float = 0.0,
                 currency: str = "USD"):
        """
        Pré-fixado (linear ou exponencial).
        
        Args:
            notional: Notional na moeda do contrato (P$)
            start_date: Data início
            end_date: Data fim
            rate: Taxa anual como decimal (ex: 0.12 para 12%)
            method: 'linear' ou 'exponential'
            base: BASE_DC (360) ou BASE_DU (252)
            cotacao_cliente: Cotação cliente (c_cli)
            amortizacao: Amortização na moeda do contrato
            currency: Moeda do contrato (USD, EUR ou BRL)
        """
        super().__init__(notional, start_date, end_date, currency)
        self.rate = rate
        self.method = method
        self.base = base
        self.cotacao_cliente = cotacao_cliente
        self.amortizacao = amortizacao

    def calculate_future_value(self, calendar) -> float:
        if self.base == BASE_DC:
            dias = calendar.calendar_days(self.start_date, self.end_date)
        else:
            dias = calendar.business_days(self.start_date, self.end_date)
        
        valor = calc_pre(
            principal_usd=self.notional,
            cotacao_cliente=self.cotacao_cliente,
            spread=self.rate,
            dias=dias,
            base=self.base,
            amortizacao_brl=self.amortizacao,
            method=self.method
        )
        
        # FV = Notional + Valor (juros + amortização)
        return self.notional * self.cotacao_cliente + valor

    def calculate_initial_value(self) -> float:
        return self.notional * self.cotacao_cliente


class CDILeg(SwapLeg):
    def __init__(self, notional, start_date, end_date, cdi_factor: float = None,
                 spread: float = 0.0, percent: float = 1.0,
                 use_percentual_method: bool = False,
                 cotacao_cliente: float = 1.0, amortizacao: float = 0.0,
                 currency: str = "USD"):
        """
        CDI (com spread ou percentual).
        
        Args:
            notional: Notional na moeda do contrato
            start_date: Data início
            end_date: Data fim
            cdi_factor: Fator DI acumulado (se None, será calculado)
            spread: Spread anual (para método com spread)
            percent: Percentual do CDI (para ambos métodos)
            use_percentual_method: Se True, usa calc_mtm_cdi_percentual
            cotacao_cliente: Cotação cliente
            amortizacao: Amortização na moeda do contrato
            currency: Moeda do contrato (USD, EUR ou BRL)
        """
        super().__init__(notional, start_date, end_date, currency)
        self.cdi_factor = cdi_factor
        self.spread = spread
        self.percent = percent
        self.use_percentual_method = use_percentual_method
        self.cotacao_cliente = cotacao_cliente
        self.amortizacao = amortizacao

    def calculate_future_value(self, calendar) -> float:
        from utils.market_data import BCBDataFetcher
        
        dias_du = calendar.business_days(self.start_date, self.end_date)
        
        if self.use_percentual_method:
            # Método percentual (sem spread)
            if self.cdi_factor is None:
                fator_cdi_pct = BCBDataFetcher.get_cdi_percentual_factor(
                    self.start_date, self.end_date, self.percent
                )
            else:
                if dias_du <= 0:
                    fator_cdi_pct = 1.0
                else:
                    daily_factor = self.cdi_factor ** (1 / dias_du)
                    fator_cdi_pct = (1 + self.percent * (daily_factor - 1)) ** dias_du
            
            valor = calc_mtm_cdi_percentual(
                principal_usd=self.notional,
                cotacao_cliente=self.cotacao_cliente,
                fator_cdi_percentual=fator_cdi_pct,
                amortizacao_brl=self.amortizacao
            )
        else:
            # Método com spread
            if self.cdi_factor is None:
                fator_di = BCBDataFetcher.get_cdi_factor(self.start_date, self.end_date)
            else:
                fator_di = self.cdi_factor
            
            valor = calc_mtm_cdi(
                principal_usd=self.notional,
                cotacao_cliente=self.cotacao_cliente,
                fator_di=fator_di,
                spread=self.spread,
                dias=dias_du,
                base=BASE_DU,
                amortizacao_brl=self.amortizacao
            )
        
        # FV = Notional + Valor
        return self.notional * self.cotacao_cliente + valor

    def calculate_initial_value(self) -> float:
        return self.notional * self.cotacao_cliente


class VCLeg(SwapLeg):
    def __init__(self, notional, start_date, end_date, spot_start: float, spot_end: float, 
                 coupon: float, cap: float = 0.0, use_contra: bool = False,
                 amortizacao_usd: float = 0.0, day_count_base: int = BASE_DC,
                 currency: str = "USD"):
        """
        Variação Cambial (parte ou contra-parte).
        
        Args:
            notional: Notional na moeda do contrato
            start_date: Data início
            end_date: Data fim
            spot_start: PTAX inicial (cotação cliente)
            spot_end: PTAX final (cotação atual)
            coupon: Cupom cambial anual
            cap: CAP (apenas para contra-parte)
            use_contra: Se True, usa calc_vc_contra
            amortizacao_usd: Amortização na moeda do contrato
            currency: Moeda do contrato (USD, EUR ou BRL)
            day_count_base: Base de cálculo (360)
        """
        super().__init__(notional, start_date, end_date, currency)
        self.spot_start = spot_start
        self.spot_end = spot_end
        self.coupon = coupon
        self.cap = cap
        self.use_contra = use_contra
        self.amortizacao_usd = amortizacao_usd
        self.day_count_base = day_count_base

    def calculate_future_value(self, calendar) -> float:
        dias_dc = calendar.calendar_days(self.start_date, self.end_date)
        
        if self.use_contra:
            valor = calc_vc_contra(
                principal_usd=self.notional,
                cotacao_cliente=self.spot_start,
                cotacao_atual=self.spot_end,
                spread=self.coupon,
                dias=dias_dc,
                base=self.day_count_base,
                amortizacao_usd=self.amortizacao_usd,
                cap=self.cap
            )
        else:
            valor = calc_vc_parte(
                principal_usd=self.notional,
                cotacao_cliente=self.spot_start,
                cotacao_atual=self.spot_end,
                spread=self.coupon,
                dias=dias_dc,
                base=self.day_count_base,
                amortizacao_usd=self.amortizacao_usd
            )
        
        # FV = principal reavaliado pela cotacao final + juros/amortizacao
        return self.notional * self._principal_spot() + valor

    def _principal_spot(self) -> float:
        if self.use_contra and self.cap > 0:
            return min(self.spot_end, self.cap)
        return self.spot_end

    def calculate_initial_value(self) -> float:
        return self.notional * self.spot_start


class IPCALeg(SwapLeg):
    def __init__(self, notional, start_date, end_date, vna_start: float, vna_end: float, 
                 coupon: float, capitalizado: bool = True,
                 cotacao_cliente: float = 1.0, amortizacao: float = 0.0,
                 currency: str = "USD"):
        """
        IPCA (capitalizado ou não capitalizado).
        
        Args:
            notional: Notional na moeda do contrato
            start_date: Data início
            end_date: Data fim
            vna_start: VNA inicial
            vna_end: VNA final
            coupon: Juro real anual
            capitalizado: Se True, usa modo capitalizado
            cotacao_cliente: Cotação cliente
            amortizacao: Amortização na moeda do contrato
            currency: Moeda do contrato (USD, EUR ou BRL)
        """
        super().__init__(notional, start_date, end_date, currency)
        self.vna_start = vna_start
        self.vna_end = vna_end
        self.coupon = coupon
        self.capitalizado = capitalizado
        self.cotacao_cliente = cotacao_cliente
        self.amortizacao = amortizacao
    
    def calculate_future_value(self, calendar) -> float:
        dias_du = calendar.business_days(self.start_date, self.end_date)
        fator_ipca = self.vna_end / self.vna_start
        
        valor = calc_ipca(
            principal_usd=self.notional,
            cotacao_cliente=self.cotacao_cliente,
            fator_ipca=fator_ipca,
            spread=self.coupon,
            dias_du=dias_du,
            amortizacao_brl=self.amortizacao,
            capitalizado=self.capitalizado
        )
        
        # FV = Notional + Valor
        return self.notional * self.cotacao_cliente + valor

    def calculate_initial_value(self) -> float:
        return self.notional * self.cotacao_cliente


class SOFRLeg(SwapLeg):
    def __init__(self, notional, start_date, end_date, sofr_index_start: float,
                 sofr_index_end: float, spot_start: float, spot_end: float,
                 coupon: float, amortizacao_usd: float = 0.0,
                 currency: str = "USD"):
        """
        SOFR.
        
        Args:
            notional: Notional na moeda do contrato
            start_date: Data início
            end_date: Data fim
            sofr_index_start: Índice SOFR inicial (T-2 ajustado)
            sofr_index_end: Índice SOFR final (T-2 ajustado)
            spot_start: Cotação inicial
            spot_end: Cotação atual
            coupon: Spread anual
            amortizacao_usd: Amortização na moeda do contrato
            currency: Moeda do contrato (USD, EUR ou BRL)
        """
        super().__init__(notional, start_date, end_date, currency)
        self.sofr_index_start = sofr_index_start
        self.sofr_index_end = sofr_index_end
        self.spot_start = spot_start
        self.spot_end = spot_end
        self.coupon = coupon
        self.amortizacao_usd = amortizacao_usd
    
    def calculate_future_value(self, calendar) -> float:
        dias_dc = calendar.calendar_days(self.start_date, self.end_date)
        
        valor = calc_sofr(
            principal_usd=self.notional,
            cotacao_cliente=self.spot_start,
            cotacao_atual=self.spot_end,
            sofr_index_inicio=self.sofr_index_start,
            sofr_index_fim=self.sofr_index_end,
            spread=self.coupon,
            dias=dias_dc,
            base=BASE_DC,
            amortizacao_usd=self.amortizacao_usd
        )
        
        # FV = principal reavaliado pela cotacao final + juros/amortizacao
        return self.notional * self.spot_end + valor

    def calculate_initial_value(self) -> float:
        return self.notional * self.spot_start


class DuploIndexadorLeg(SwapLeg):
    def __init__(self, notional, start_date, end_date, cotacao_cliente: float,
                 cotacao_atual: float, spread_pre: float, spread_vc: float,
                 cap: float = 0.0, amortizacao_usd: float = 0.0,
                 use_vc_contra: bool = True, cap_target: str = "vc",
                 currency: str = "USD"):
        """
        Duplo Indexador (máximo entre Pré exponencial e VC).
        
        Args:
            notional: Notional na moeda do contrato
            start_date: Data início
            end_date: Data fim
            cotacao_cliente: Cotação cliente
            cotacao_atual: Cotação atual
            spread_pre: Spread para pré-fixado
            spread_vc: Spread para variação cambial
            cap: CAP para VC (se use_vc_contra=True)
            amortizacao_usd: Amortização na moeda do contrato
            currency: Moeda do contrato (USD, EUR ou BRL)
            use_vc_contra: Se True usa VC contra, senão usa VC parte
        """
        super().__init__(notional, start_date, end_date, currency)
        self.cotacao_cliente = cotacao_cliente
        self.cotacao_atual = cotacao_atual
        self.spread_pre = spread_pre
        self.spread_vc = spread_vc
        self.cap = cap
        self.amortizacao_usd = amortizacao_usd
        self.use_vc_contra = use_vc_contra
        self.cap_target = cap_target
        self.resultado = None  # Armazena detalhes do cálculo
    
    def calculate_future_value(self, calendar) -> float:
        dias_du = calendar.business_days(self.start_date, self.end_date)
        dias_dc = calendar.calendar_days(self.start_date, self.end_date)
        
        resultado = calc_duplo_indexador(
            principal_usd=self.notional,
            cotacao_cliente=self.cotacao_cliente,
            cotacao_atual=self.cotacao_atual,
            spread_pre=self.spread_pre,
            spread_vc=self.spread_vc,
            dias_du=dias_du,
            dias_dc=dias_dc,
            amortizacao_usd=self.amortizacao_usd,
            cap=self.cap,
            use_vc_contra=self.use_vc_contra,
            cap_target=self.cap_target
        )
        
        self.resultado = resultado
        
        # FV = Notional + Valor escolhido
        return self.notional * self.cotacao_cliente + resultado['valor_final']

    def calculate_initial_value(self) -> float:
        return self.notional * self.cotacao_cliente
