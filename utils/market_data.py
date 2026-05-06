import requests
import pandas as pd
from datetime import datetime, date, timedelta
import numpy as np

class BCBDataFetcher:
    """
    Fetcher for Banco Central do Brasil (BCB) data.
    Uses SGS (Sistema Gerenciador de Séries Temporais) API.
    """
    
    SGS_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series}/dados"
    IBGE_SIDRA_IPCA_NUMBER_INDEX_URL = (
        "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/{period_range}"
    )
    NYFED_SOFRAI_URL = "https://markets.newyorkfed.org/api/rates/secured/sofrai/search.json"
    PT_MONTH_ABBR = {
        1: "jan",
        2: "fev",
        3: "mar",
        4: "abr",
        5: "mai",
        6: "jun",
        7: "jul",
        8: "ago",
        9: "set",
        10: "out",
        11: "nov",
        12: "dez",
    }
    
    @staticmethod
    def _fetch_series(series_code: int, start_date: date, end_date: date):
        """Fetch time series from BCB SGS."""
        url = BCBDataFetcher.SGS_BASE_URL.format(series=series_code)
        params = {
            'formato': 'json',
            'dataInicial': start_date.strftime('%d/%m/%Y'),
            'dataFinal': end_date.strftime('%d/%m/%Y')
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return None
                
            df = pd.DataFrame(data)
            df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
            df['valor'] = df['valor'].astype(float)
            return df
        except Exception as e:
            print(f"Erro ao buscar série {series_code}: {e}")
            return None
    
    @staticmethod
    def get_cdi_factor(start_date: date, end_date: date) -> float:
        """
        Calcula o fator acumulado do CDI entre duas datas.
        Série 12: CDI (% a.d. - Taxa Percentual ao Dia)
        
        Retorna: F_DI = ∏(1 + r_CDI_d) para cada dia d
        """
        df = BCBDataFetcher._fetch_series(12, start_date, end_date)
        
        if df is None or df.empty:
            print("Aviso: Usando CDI flat de 11.75% a.a. (sem dados disponíveis)")
            # Fallback: aproximação com 252 dias úteis
            days_approx = (end_date - start_date).days * 0.7  # ~70% são úteis
            return (1.1175) ** (days_approx / 252)
        
        # CDI vem em % ao dia. Precisamos: produto de (1 + CDI/100)
        df['fator'] = 1 + (df['valor'] / 100)
        fator_acumulado = df['fator'].prod()
        
        return fator_acumulado
    
    @staticmethod
    def get_cdi_percentual_factor(start_date: date, end_date: date, percent: float = 1.0) -> float:
        """
        Calcula o fator CDI ponderado por percentual α.
        
        Fórmula: F_α_CDI = ∏(1 + α * r_CDI_d) para cada dia d
        
        Args:
            start_date: Data inicial
            end_date: Data final
            percent: Percentual do CDI (ex: 0.90 para 90% do CDI)
        
        Returns:
            Fator acumulado ponderado
        """
        df = BCBDataFetcher._fetch_series(12, start_date, end_date)
        
        if df is None or df.empty:
            print(f"Aviso: Usando CDI flat {percent*100}% x 11.75% a.a.")
            days_approx = (end_date - start_date).days * 0.7
            cdi_daily = (1.1175) ** (1/252) - 1
            return (1 + percent * cdi_daily) ** days_approx
        
        # Aplicar percentual a cada taxa diária
        df['fator'] = 1 + (percent * df['valor'] / 100)
        fator_acumulado = df['fator'].prod()
        
        return fator_acumulado
    
    @staticmethod
    def get_ptax(target_date: date, use_bid=False) -> float:
        """
        Obtém a cotação PTAX (dólar) de uma data específica.
        Série 1: PTAX Venda (USD)
        Série 10813: PTAX Compra (USD)
        """
        series_code = 10813 if use_bid else 1
        
        # Busca em uma janela de 5 dias para lidar com fins de semana/feriados
        start = target_date - pd.Timedelta(days=5)
        df = BCBDataFetcher._fetch_series(series_code, start, target_date)
        
        if df is None or df.empty:
            print(f"Aviso: PTAX não disponível para {target_date}, usando R$ 5.50")
            return 5.50
        
        # Pega o valor mais recente disponível
        return df.iloc[-1]['valor']
    
    @staticmethod
    def get_ipca_index(year: int, month: int) -> float:
        """
        Obtém o índice IPCA para um mês/ano.
        Série 433: IPCA (% mensal)
        
        Nota: Para VNA real, seria necessário a série Anbima de VNA diária.
        Esta é uma aproximação usando índices mensais.
        """
        # Monta data de início e fim do mês
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        df = BCBDataFetcher._fetch_series(433, start_date, end_date)
        
        if df is None or df.empty:
            print(f"Aviso: IPCA não disponível para {month}/{year}")
            return None
        
        # Retorna o valor do IPCA mensal (%)
        return df.iloc[-1]['valor']
    
    @staticmethod
    def get_ipca_factor(start_date: date, end_date: date) -> float:
        """
        Calcula o fator IPCA entre duas datas.
        
        Retorna: F_IPCA = I_final / I_inicial
        
        Nota: Esta é uma aproximação usando índices mensais.
        Para precisão real, seria necessário VNA diário da Anbima.
        """
        factor = 1.0
        current = start_date
        
        while current <= end_date:
            ipca_month = BCBDataFetcher.get_ipca_index(current.year, current.month)
            if ipca_month is not None:
                factor *= (1 + ipca_month / 100)
            
            # Avança para próximo mês
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)
            
            if current > end_date:
                break
        
        return factor
    
    @staticmethod
    def get_ipca_pro_rata_index(target_date: date, base_date: date = None, base_index: float = 1.0) -> float:
        """
        Calcula o índice IPCA pro rata acumulado entre duas datas, similar ao Bloomberg.
        
        O índice acumula:
        1. IPCA completo de todos os meses fechados entre base_date e target_date
        2. IPCA pro rata do mês da target_date (se aplicável)
        
        Fórmula:
        I_t = I_base * ∏(1 + IPCA_m/100) * (1 + IPCA_t/100)^(d_t/D_t)
        
        Onde:
        - I_t: índice na data alvo
        - I_base: índice na data base
        - IPCA_m: IPCA dos meses completos entre as datas
        - IPCA_t: IPCA do mês da data alvo
        - d_t: dia do mês da data alvo
        - D_t: total de dias no mês da data alvo
        
        Args:
            target_date: Data alvo para calcular o índice
            base_date: Data inicial (default: início do mês da target_date)
            base_index: Valor do índice na data base (default: 1.0)
        
        Returns:
            Índice IPCA pro rata acumulado
        """
        # Se base_date não fornecida, usa início do mês da target_date
        if base_date is None:
            base_date = date(target_date.year, target_date.month, 1)
        
        index = base_index
        current = base_date
        
        # Acumula IPCA de meses completos
        while current.month != target_date.month or current.year != target_date.year:
            ipca_month = BCBDataFetcher.get_ipca_index(current.year, current.month)
            if ipca_month is not None:
                index *= (1 + ipca_month / 100)
            else:
                print(f"Aviso: IPCA não disponível para {current.month}/{current.year}")
            
            # Avança para próximo mês
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)
        
        # Aplica pro rata do mês da data alvo
        ipca_target_month = BCBDataFetcher.get_ipca_index(target_date.year, target_date.month)
        
        if ipca_target_month is not None:
            # Calcula total de dias no mês
            if target_date.month == 12:
                next_month = date(target_date.year + 1, 1, 1)
            else:
                next_month = date(target_date.year, target_date.month + 1, 1)
            
            days_in_month = (next_month - date(target_date.year, target_date.month, 1)).days
            
            # Fator pro rata: (1 + IPCA/100)^(dia/dias_mês)
            pro_rata_factor = (1 + ipca_target_month / 100) ** (target_date.day / days_in_month)
            index *= pro_rata_factor
        else:
            print(f"Aviso: IPCA pro rata não aplicado para {target_date.month}/{target_date.year}")
        
        return index
    
    @staticmethod
    def get_ipca_pro_rata_last_price(base_date: date = date(2015, 7, 1), base_index: float = 1000.0) -> dict:
        """
        Obtém o "Last Price" do índice IPCA Pro Rata, similar ao Bloomberg.
        
        Retorna o índice para a última data disponível (ontem ou dia mais recente).
        Usa base padrão: 01/07/2015 = 1000 (convenção Bloomberg para índices Brasil).
        
        Args:
            base_date: Data base do índice (default: 01/07/2015)
            base_index: Valor do índice na data base (default: 1000.0)
        
        Returns:
            dict com: {
                'index': valor do índice,
                'date': data do índice,
                'variation_1d': variação em 1 dia (%),
                'variation_mtd': variação no mês (%),
                'variation_ytd': variação no ano (%)
            }
        """
        from datetime import timedelta
        
        # Tenta pegar índice de ontem (pode não ter se for fim de semana)
        target_date = date.today() - timedelta(days=1)
        
        # Calcula índice atual
        current_index = BCBDataFetcher.get_ipca_pro_rata_index(
            target_date, 
            base_date=base_date, 
            base_index=base_index
        )
        
        # Calcula índice do dia anterior para variação diária
        prev_date = target_date - timedelta(days=1)
        prev_index = BCBDataFetcher.get_ipca_pro_rata_index(
            prev_date,
            base_date=base_date,
            base_index=base_index
        )
        variation_1d = ((current_index / prev_index) - 1) * 100 if prev_index > 0 else 0
        
        # Calcula índice do início do mês (MTD - Month to Date)
        month_start = date(target_date.year, target_date.month, 1)
        month_start_index = BCBDataFetcher.get_ipca_pro_rata_index(
            month_start,
            base_date=base_date,
            base_index=base_index
        )
        variation_mtd = ((current_index / month_start_index) - 1) * 100 if month_start_index > 0 else 0
        
        # Calcula índice do início do ano (YTD - Year to Date)
        year_start = date(target_date.year, 1, 1)
        year_start_index = BCBDataFetcher.get_ipca_pro_rata_index(
            year_start,
            base_date=base_date,
            base_index=base_index
        )
        variation_ytd = ((current_index / year_start_index) - 1) * 100 if year_start_index > 0 else 0
        
        return {
            'index': current_index,
            'date': target_date,
            'variation_1d': variation_1d,
            'variation_mtd': variation_mtd,
            'variation_ytd': variation_ytd
        }
    
    @staticmethod
    def calculate_ipca_vna(start_date: date, end_date: date, vna_base: float = 4000.0):
        """
        Calcula VNA projetado usando variação IPCA acumulada.
        
        Simplificação: usa variação mensal composta.
        Para precisão real, seria necessário VNA diário da Anbima.
        """
        try:
            factor = BCBDataFetcher.get_ipca_anbima_factor(start_date, end_date)
        except Exception as e:
            print(f"Aviso: IPCA ANBIMA indisponivel ({e}); usando IPCA mensal BCB")
            factor = BCBDataFetcher.get_ipca_factor(start_date, end_date)
        return vna_base * factor

    @staticmethod
    def _add_months(month_date: date, months: int) -> date:
        year = month_date.year + (month_date.month - 1 + months) // 12
        month = (month_date.month - 1 + months) % 12 + 1
        return date(year, month, 1)

    @staticmethod
    def _month_label(month_date: date) -> str:
        return f"{month_date.year}-{month_date.month:02d}"

    @staticmethod
    def _sidra_period(month_date: date) -> str:
        return f"{month_date.year}{month_date.month:02d}"

    @staticmethod
    def _month_from_sidra_period(period: str) -> date:
        return date(int(period[:4]), int(period[4:6]), 1)

    @staticmethod
    def _ipca_source_label(index_month: date, uses_bcb_history: bool) -> str:
        month_abbr = BCBDataFetcher.PT_MONTH_ABBR[index_month.month]
        source = f"ANBIMA IPCA {month_abbr}/{index_month.year % 100:02d}"
        if uses_bcb_history:
            source += " + BCB SGS 433"
        return source

    @staticmethod
    def _fetch_ipca_number_index_series(start_month: date, end_month: date) -> pd.DataFrame:
        period_range = f"{BCBDataFetcher._sidra_period(start_month)}-{BCBDataFetcher._sidra_period(end_month)}"
        url = BCBDataFetcher.IBGE_SIDRA_IPCA_NUMBER_INDEX_URL.format(period_range=period_range)
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        rows = response.json()

        parsed = []
        for row in rows:
            period = row.get("D3C")
            value = row.get("V")
            if not period or not value or period == "Mês (Código)" or value == "Valor":
                continue

            parsed.append(
                {
                    "month": BCBDataFetcher._month_from_sidra_period(str(period)),
                    "vna": float(str(value).replace(",", ".")),
                }
            )

        if not parsed:
            raise RuntimeError("Historico de numero-indice IPCA indisponivel no SIDRA/IBGE")

        return pd.DataFrame(parsed).sort_values("month").reset_index(drop=True)

    @staticmethod
    def get_ipca_vna_months_back(months_back: int = 0) -> dict:
        """Retorna VNA historico por backcast a partir do ultimo IPCA ANBIMA."""
        if months_back < -1:
            raise ValueError("Meses para tras do IPCA deve ser -1 ou maior")

        from utils.anbima import get_ipca_snapshot

        snapshot = get_ipca_snapshot()
        reference_month = BCBDataFetcher._add_months(snapshot.index_month, -months_back)
        source = BCBDataFetcher._ipca_source_label(snapshot.index_month, months_back > 0)

        if months_back == 0:
            return {
                "vna": snapshot.ipca_index,
                "reference_month": BCBDataFetcher._month_label(reference_month),
                "source": source,
            }

        fetch_start = BCBDataFetcher._add_months(reference_month, 1)
        fetch_end = snapshot.index_month
        df = BCBDataFetcher._fetch_series(433, fetch_start, fetch_end)
        if df is None or df.empty:
            raise RuntimeError("Historico IPCA BCB indisponivel para calcular VNA inicial")

        factor = 1.0
        for value in df["valor"]:
            factor *= 1 + float(value) / 100

        return {
            "vna": snapshot.ipca_index / factor,
            "reference_month": BCBDataFetcher._month_label(reference_month),
            "source": source,
        }

    @staticmethod
    def resolve_ipca_auto_vnas(end_date: date, months_back: int = 0, initial_vna: float | None = None) -> dict:
        """Resolve VNA inicial e final para o modo IPCA automatico."""
        if isinstance(end_date, pd.Timestamp):
            end_date = end_date.date()

        months_offset = abs(int(months_back))
        target_month = date(end_date.year, end_date.month, 1)
        requested_final_month = BCBDataFetcher._add_months(target_month, -months_offset)
        start_month = BCBDataFetcher._add_months(target_month, -(months_offset + 24))

        try:
            series = BCBDataFetcher._fetch_ipca_number_index_series(start_month, target_month)
            available = series[series["month"] <= target_month]
            if available.empty:
                raise RuntimeError("Sem numero-indice IPCA disponivel ate a data de vencimento")

            final_candidates = available[available["month"] <= requested_final_month]
            if final_candidates.empty:
                raise RuntimeError(
                    f"Historico IPCA insuficiente para voltar {months_offset} meses a partir de {target_month}"
                )

            final_row = final_candidates.iloc[-1]
            final_month = final_row["month"]
            if initial_vna is not None:
                return {
                    "vna_start": float(initial_vna),
                    "vna_end": float(final_row["vna"]),
                    "reference_month": "Manual",
                    "final_month": BCBDataFetcher._month_label(final_month),
                    "source": "Manual + IBGE SIDRA 1737/2266",
                }

            reference_month = BCBDataFetcher._add_months(final_month, -months_offset)
            start_rows = available[available["month"] == reference_month]
            if start_rows.empty:
                raise RuntimeError(
                    f"Historico IPCA insuficiente para voltar {months_offset} meses a partir de {final_month}"
                )

            return {
                "vna_start": float(start_rows.iloc[0]["vna"]),
                "vna_end": float(final_row["vna"]),
                "reference_month": BCBDataFetcher._month_label(reference_month),
                "final_month": BCBDataFetcher._month_label(final_month),
                "source": "IBGE SIDRA 1737/2266",
            }
        except Exception as e:
            print(f"Aviso: SIDRA IPCA numero-indice indisponivel ({e}); usando fallback ANBIMA/BCB")

        from utils.anbima import ipca_prorata

        if initial_vna is not None:
            from utils.anbima import ipca_prorata

            return {
                "vna_start": float(initial_vna),
                "vna_end": ipca_prorata(end_date),
                "reference_month": "Manual",
                "final_month": end_date.isoformat(),
                "source": "Manual + ANBIMA/BCB",
            }

        initial = BCBDataFetcher.get_ipca_vna_months_back(months_offset)
        return {
            "vna_start": initial["vna"],
            "vna_end": ipca_prorata(end_date),
            "reference_month": initial["reference_month"],
            "final_month": end_date.isoformat(),
            "source": initial["source"],
        }
    
    @staticmethod
    def get_ipca_anbima_factor(start_date: date, end_date: date) -> float:
        """Calcula o fator IPCA pro rata usando a fonte ANBIMA."""
        from utils.anbima import ipca_prorata

        start_index = ipca_prorata(start_date)
        end_index = ipca_prorata(end_date)

        if start_index <= 0:
            raise ValueError("Indice IPCA ANBIMA inicial invalido")

        return end_index / start_index

    @staticmethod
    def _fetch_sofrai_records(start_date: date, end_date: date) -> list[dict]:
        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
        }
        response = requests.get(BCBDataFetcher.NYFED_SOFRAI_URL, params=params, timeout=10)
        response.raise_for_status()
        records = response.json().get("refRates", [])

        parsed = []
        for record in records:
            if record.get("type") != "SOFRAI" or "index" not in record:
                continue
            effective_date = datetime.strptime(record["effectiveDate"], "%Y-%m-%d").date()
            parsed.append(
                {
                    "effectiveDate": effective_date,
                    "index": float(record["index"]),
                    "record": record,
                }
            )

        return parsed

    @staticmethod
    def get_sofr_index_for_value_date(value_date: date, observation_lag_days: int = 2) -> tuple[date, float]:
        """
        Retorna a observacao SOFR com lag em dias de publicacao NY Fed.

        Evita aplicar calendario B3 a uma taxa USD: o proprio historico da
        API oficial define as datas publicadas disponiveis.
        """
        if isinstance(value_date, pd.Timestamp):
            value_date = value_date.date()

        start_date = value_date - timedelta(days=21)
        records = BCBDataFetcher._fetch_sofrai_records(start_date, value_date)
        candidates = sorted(
            [record for record in records if record["effectiveDate"] <= value_date],
            key=lambda record: record["effectiveDate"],
            reverse=True,
        )

        if len(candidates) <= observation_lag_days:
            raise RuntimeError(f"Historico SOFR insuficiente para aplicar T-{observation_lag_days} em {value_date}")

        selected = candidates[observation_lag_days]
        return selected["effectiveDate"], selected["index"]

    @staticmethod
    def get_sofr_index(target_date: date) -> float:
        """Retorna o ultimo SOFR Index oficial disponivel ate target_date."""
        if isinstance(target_date, pd.Timestamp):
            target_date = target_date.date()

        start_date = target_date - timedelta(days=14)
        records = BCBDataFetcher._fetch_sofrai_records(start_date, target_date)
        candidates = [record for record in records if record["effectiveDate"] <= target_date]

        if not candidates:
            raise RuntimeError(f"SOFR Index nao disponivel para {target_date}")

        latest = max(candidates, key=lambda record: record["effectiveDate"])
        return latest["index"]


class MarketDataCache:
    """Cache simples para evitar chamadas repetidas à API."""
    _cache = {}
    
    @staticmethod
    def get(key):
        return MarketDataCache._cache.get(key)
    
    @staticmethod
    def set(key, value):
        MarketDataCache._cache[key] = value
