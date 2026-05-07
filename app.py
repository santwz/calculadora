import streamlit as st
import pandas as pd
from calendar import monthrange
from datetime import date
from models.leg import PreLeg, CDILeg, VCLeg, IPCALeg, SOFRLeg, DuploIndexadorLeg
from models.swap import Swap
from utils.calendars import B3Calendar
from utils.market_data import BCBDataFetcher
from utils.vc_inputs import resolve_vc_spots
from utils.xlsx_export import build_calculation_memory_xlsx

st.set_page_config(
    page_title="Calculadora de Derivativos",
    layout="wide",
    page_icon="💸"
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 8px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }

    .section-heading {
        color: #1e3c72;
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0.25rem 0 0.75rem 0;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 8px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .metric-card.positive {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    }
    
    .metric-card.negative {
        background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
    }
    
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        padding: 0.75rem;
        border-radius: 8px;
        border: none;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>💸 Calculadora de Derivativos</h1>
    <p style="font-size: 1.1rem; margin-top: 0.5rem;">Pré | CDI | VC Cambial | IPCA | SOFR | Duplo Indexador</p>
</div>
""", unsafe_allow_html=True)

# Initialize Calendar
calendar = B3Calendar()


def format_ptbr_number(value, decimals=2):
    number = float(value)
    formatted = f"{number:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def parse_ptbr_number(value):
    text = str(value).strip()
    text = text.replace("US$", "").replace("R$", "").replace("$", "")
    text = text.replace(" ", "").replace("\xa0", "")

    if not text:
        raise ValueError("Valor vazio")

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            text = "".join(parts)

    return float(text)


def shift_months(base_date, months):
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)

# --- GLOBAL CONFIGURATION ---
st.markdown('<div class="section-heading">⚙️ Configuração do Swap</div>', unsafe_allow_html=True)

today = date.today()
config_col0, config_col1, config_col2, config_col3, config_col4, config_col5 = st.columns([0.75, 1.15, 1.15, 1, 1, 1])
with config_col0:
    moeda_contrato = st.selectbox("Moeda", ["USD", "EUR", "BRL"], key="moeda_contrato")
with config_col1:
    notional_text = st.text_input("Notional", value=format_ptbr_number(1_000_000.0), key="notional")
with config_col2:
    amortizacao_text = st.text_input("Amortização", value=format_ptbr_number(0.0), key="amortizacao")
with config_col3:
    start_date = st.date_input("Data Início", value=shift_months(today, -2))
with config_col4:
    end_date = st.date_input("Data Vencimento", value=shift_months(today, -1))
with config_col5:
    if moeda_contrato == "BRL":
        cotacao_cliente_global = 1.0
        st.number_input(
            f"Cotação Cliente ({moeda_contrato}/BRL)",
            value=1.0,
            format="%.4f",
            disabled=True,
        )
    else:
        cotacao_cliente_global = st.number_input(
            f"Cotação Cliente ({moeda_contrato}/BRL)",
            value=5.0,
            format="%.4f",
        )

try:
    notional = parse_ptbr_number(notional_text)
except ValueError:
    st.error("⚠️ Informe o Notional em um formato válido, como 1.000.000,00")
    st.stop()

try:
    amortizacao = parse_ptbr_number(amortizacao_text)
except ValueError:
    st.error("⚠️ Informe a Amortização em um formato válido, como 100.000,00")
    st.stop()

if start_date >= end_date:
    st.error("⚠️ Data de Vencimento deve ser posterior a Data de Início")
    st.stop()

# Helper to configure leg
def configure_leg(prefix, side_label, cotacao_cliente, moeda):
    leg_type = st.selectbox(
        f"Tipo da Ponta {side_label}", 
        ["Pré-Fixada", "CDI", "CDI Percentual", "Moeda (VC)", "IPCA", "SOFR", "Duplo Indexador"],
        key=f"type_{prefix}"
    )
    
    params = {'type': leg_type}
    
    if leg_type == "Pré-Fixada":
        col1, col2 = st.columns(2)
        params['rate'] = col1.number_input(f"Taxa (% a.a.) {side_label}", value=12.0, key=f"pre_rate_{prefix}") / 100
        params['method'] = col2.selectbox(f"Método {side_label}", ["Exponencial", "Linear"], key=f"pre_method_{prefix}")
        params['base'] = st.selectbox(f"Base {side_label}", [252, 360], key=f"pre_base_{prefix}")
        params['cotacao'] = cotacao_cliente
        
    elif leg_type in ["CDI", "CDI Percentual"]:
        use_auto = st.checkbox(f"🤖 Calcular CDI automaticamente (BCB) {side_label}", key=f"auto_cdi_{prefix}")
        
        if use_auto:
            params['auto_cdi'] = True
            params['cdi_factor'] = None
        else:
            params['auto_cdi'] = False
            params['cdi_factor'] = st.number_input(f"Fator CDI Acumulado {side_label}", value=1.0045, format="%.6f", key=f"cdi_factor_{prefix}")
        
        params['percent'] = st.number_input(f"% do CDI {side_label}", value=100.0, key=f"pct_cdi_{prefix}") / 100
        
        if leg_type == "CDI":
            params['spread'] = st.number_input(f"Spread (% a.a.) {side_label}", value=2.0, key=f"spread_cdi_{prefix}") / 100
        
        params['cotacao'] = cotacao_cliente
        
    elif leg_type == "Moeda (VC)":
        params['spot_start'] = cotacao_cliente
        if moeda == "BRL":
            st.info("Para BRL, a cotação inicial e final são 1,0000.")
            params['spot_end'] = 1.0
            use_auto_ptax = False
        else:
            supports_auto_quote = moeda == "USD"
            if supports_auto_quote:
                use_auto_ptax = st.checkbox(f"🤖 Buscar cotação final automaticamente {side_label}", key=f"auto_ptax_{prefix}")
            else:
                st.info("Para EUR, informe a cotação final manualmente.")
                use_auto_ptax = False
        params['auto_ptax'] = use_auto_ptax
        
        if moeda != "BRL" and not use_auto_ptax:
            params['spot_end'] = st.number_input(f"Cotação Final ({moeda}/BRL) {side_label}", value=5.50, format="%.4f", key=f"spot_e_{prefix}")
        
        params['coupon'] = st.number_input(f"Cupom Cambial (% a.a.) {side_label}", value=5.0, key=f"cupom_vc_{prefix}") / 100
        params['use_contra'] = st.checkbox(f"Usar Contra-Parte {side_label}", value=False, key=f"contra_{prefix}")
        
        if params['use_contra']:
            params['cap'] = st.number_input(f"CAP (0 = sem CAP) {side_label}", value=0.0, format="%.4f", key=f"cap_{prefix}")
        else:
            params['cap'] = 0.0
            
    elif leg_type == "IPCA":
        use_auto_ipca = st.checkbox(f"🤖 Calcular VNA automaticamente {side_label}", key=f"auto_ipca_{prefix}")
        
        if use_auto_ipca:
            params['auto_ipca'] = True
            params['manual_ipca_start'] = True
            params['vna_start'] = st.number_input(
                f"IPCA Inicial (VNA) {side_label}",
                value=7403.29,
                format="%.6f",
                key=f"auto_vna_start_{prefix}",
            )
            params['ipca_months_back'] = int(
                st.number_input(
                    f"Meses para trás {side_label}",
                    min_value=-120,
                    max_value=120,
                    value=0,
                    step=1,
                    key=f"ipca_months_back_{prefix}",
                )
            )
        else:
            params['auto_ipca'] = False
            params['vna_start'] = st.number_input(f"VNA Inicial {side_label}", value=4000.00, format="%.2f", key=f"vna_s_{prefix}")
            params['vna_end'] = st.number_input(f"VNA Final {side_label}", value=4200.00, format="%.2f", key=f"vna_e_{prefix}")
        
        params['coupon'] = st.number_input(f"Juro Real (% a.a.) {side_label}", value=6.0, key=f"cupom_ipca_{prefix}") / 100
        params['capitalizado'] = st.checkbox(f"Capitalizado {side_label}", value=True, key=f"cap_ipca_{prefix}")
        params['cotacao'] = cotacao_cliente
        
    elif leg_type == "SOFR":
        params['spot_start'] = cotacao_cliente
        if moeda == "BRL":
            params['spot_end'] = 1.0
            st.number_input(
                f"Cotação Final ({moeda}/BRL) {side_label}",
                value=1.0,
                format="%.4f",
                key=f"sofr_spot_e_{prefix}",
                disabled=True,
            )
        else:
            params['spot_end'] = st.number_input(f"Cotação Final ({moeda}/BRL) {side_label}", value=5.50, format="%.4f", key=f"sofr_spot_e_{prefix}")
        params['coupon'] = st.number_input(f"Spread (% a.a.) {side_label}", value=3.0, key=f"sofr_spread_{prefix}") / 100
        
        st.info("📊 SOFR usa índice oficial do New York Fed (T-2 por datas publicadas)")
        
    elif leg_type == "Duplo Indexador":
        params['cotacao_cliente'] = cotacao_cliente
        if moeda == "BRL":
            params['cotacao_atual'] = 1.0
            st.number_input(
                f"Cotação Atual ({moeda}/BRL) {side_label}",
                value=1.0,
                format="%.4f",
                key=f"di_cot_atu_{prefix}",
                disabled=True,
            )
        else:
            params['cotacao_atual'] = st.number_input(f"Cotação Atual ({moeda}/BRL) {side_label}", value=5.50, format="%.4f", key=f"di_cot_atu_{prefix}")
        params['spread_pre'] = st.number_input(f"Spread Pré (% a.a.) {side_label}", value=12.0, key=f"di_spread_pre_{prefix}") / 100
        params['spread_vc'] = st.number_input(f"Spread VC (% a.a.) {side_label}", value=5.0, key=f"di_spread_vc_{prefix}") / 100
        params['use_vc_contra'] = st.checkbox(f"VC Contra-Parte {side_label}", value=True, key=f"di_contra_{prefix}")
        cap_target_label = st.selectbox(f"Aplicar CAP {side_label}", ["Sem CAP", "No componente VC"], key=f"di_cap_target_{prefix}")
        params['cap_target'] = "vc" if cap_target_label == "No componente VC" else "none"

        if params['cap_target'] == "vc":
            params['cap'] = st.number_input(f"CAP do VC {side_label}", value=0.0, format="%.4f", key=f"di_cap_{prefix}")
        else:
            params['cap'] = 0.0
    
    return leg_type, params


# Create Leg Factory
def _attach_currency(leg, moeda):
    leg.currency = moeda
    return leg


def create_leg(leg_type, params, notional, amortizacao, moeda, start, end):
    if leg_type == "Pré-Fixada":
        method = 'exponential' if params['method'] == "Exponencial" else 'linear'
        return _attach_currency(
            PreLeg(
                notional, start, end,
                params['rate'],
                method=method,
                base=params['base'],
                cotacao_cliente=params['cotacao'],
                amortizacao=amortizacao,
            ),
            moeda,
        )
    
    elif leg_type in ["CDI", "CDI Percentual"]:
        use_percentual = (leg_type == "CDI Percentual")
        cdi_factor = params.get('cdi_factor')
        
        if params.get('auto_cdi') and cdi_factor is None:
            with st.spinner('🔍 Buscando CDI do BCB...'):
                if use_percentual:
                    cdi_factor = BCBDataFetcher.get_cdi_percentual_factor(start, end, params['percent'])
                else:
                    cdi_factor = BCBDataFetcher.get_cdi_factor(start, end)
                st.success(f"✅ Fator CDI: {cdi_factor:.6f}")
        
        return _attach_currency(
            CDILeg(
                notional, start, end,
                cdi_factor=cdi_factor,
                spread=params.get('spread', 0.0),
                percent=params['percent'],
                use_percentual_method=use_percentual,
                cotacao_cliente=params['cotacao'],
                amortizacao=amortizacao,
            ),
            moeda,
        )
    
    elif leg_type == "Moeda (VC)":
        if params.get('auto_ptax'):
            with st.spinner('🔍 Buscando cotação do BCB...'):
                spot_start, spot_end = resolve_vc_spots(params, start, end, BCBDataFetcher.get_ptax)
                st.success(f"✅ Cotação final: {end} = R$ {spot_end:.4f} | Cotação inicial: R$ {spot_start:.4f}")
        else:
            spot_start, spot_end = resolve_vc_spots(params, start, end, BCBDataFetcher.get_ptax)
        
        return _attach_currency(
            VCLeg(
                notional, start, end,
                spot_start, spot_end,
                params['coupon'],
                cap=params['cap'],
                use_contra=params['use_contra'],
                amortizacao_usd=amortizacao,
            ),
            moeda,
        )
    
    elif leg_type == "IPCA":
        if params.get('auto_ipca'):
            with st.spinner('🔍 Calculando VNA com IPCA...'):
                resolved_vnas = BCBDataFetcher.resolve_ipca_auto_vnas(
                    end,
                    months_back=params.get('ipca_months_back', 0),
                    initial_vna=params.get('vna_start') if params.get('manual_ipca_start') else None,
                )
                vna_start = resolved_vnas['vna_start']
                vna_end = resolved_vnas['vna_end']
                st.success(
                    f"✅ VNA inicial ({resolved_vnas['reference_month']}): {vna_start:,.6f} | "
                    f"VNA final ({resolved_vnas['final_month']}): {vna_end:,.6f}"
                )
        else:
            vna_start = params['vna_start']
            vna_end = params['vna_end']
        
        return _attach_currency(
            IPCALeg(
                notional, start, end,
                vna_start, vna_end,
                params['coupon'],
                capitalizado=params['capitalizado'],
                cotacao_cliente=params['cotacao'],
                amortizacao=amortizacao,
            ),
            moeda,
        )
    
    elif leg_type == "SOFR":
        with st.spinner('🔍 Buscando índices SOFR...'):
            start_t2, sofr_start = BCBDataFetcher.get_sofr_index_for_value_date(start)
            end_t2, sofr_end = BCBDataFetcher.get_sofr_index_for_value_date(end)
            st.info(f"📊 SOFR Index: {start_t2} = {sofr_start:.6f} | {end_t2} = {sofr_end:.6f}")
        
        return _attach_currency(
            SOFRLeg(
                notional, start, end,
                sofr_start, sofr_end,
                params['spot_start'], params['spot_end'],
                params['coupon'],
                amortizacao_usd=amortizacao,
            ),
            moeda,
        )
    
    elif leg_type == "Duplo Indexador":
        return _attach_currency(
            DuploIndexadorLeg(
                notional, start, end,
                params['cotacao_cliente'], params['cotacao_atual'],
                params['spread_pre'], params['spread_vc'],
                cap=params['cap'],
                amortizacao_usd=amortizacao,
                use_vc_contra=params['use_vc_contra'],
                cap_target=params.get('cap_target', 'vc'),
            ),
            moeda,
        )
    
    return None


# --- SWAP CONFIGURATION ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("🟢 Ponta Ativa (Recebe)")
    type_a, params_a = configure_leg("A", "Ativa", cotacao_cliente_global, moeda_contrato)

with col2:
    st.subheader("🔴 Ponta Passiva (Paga)")
    type_b, params_b = configure_leg("B", "Passiva", cotacao_cliente_global, moeda_contrato)

st.divider()

# --- CALCULATION BUTTON ---
if st.button("🚀 Calcular Swap", type="primary", use_container_width=True):
    try:
        # Create legs
        leg_long = create_leg(type_a, params_a, notional, amortizacao, moeda_contrato, start_date, end_date)
        leg_short = create_leg(type_b, params_b, notional, amortizacao, moeda_contrato, start_date, end_date)
        
        if leg_long is None or leg_short is None:
            st.error("Erro ao criar pernas do swap")
            st.stop()
        
        # Calculate
        swap = Swap(leg_long, leg_short)
        du = calendar.business_days(start_date, end_date)
        dc = calendar.calendar_days(start_date, end_date)
        
        results = swap.calculate_net_value(calendar)
        net_val = results['net_value']
        
        st.divider()
        
        # Results
        st.markdown("### 📊 Resultado do Swap")
        
        col_info = st.columns([1, 1, 1, 1])
        col_info[0].metric("Dias Úteis (DU)", f"{du}")
        col_info[1].metric("Dias Corridos (DC)", f"{dc}")
        col_info[2].metric(f"Notional {moeda_contrato}", f"{moeda_contrato} {format_ptbr_number(notional, 2)}")
        col_info[3].metric(f"Amortização {moeda_contrato}", f"{moeda_contrato} {format_ptbr_number(amortizacao, 2)}")
        
        st.divider()
        
        # Metrics
        m1, m2, m3 = st.columns(3)
        
        with m1:
            st.markdown(f"""
            <div class="metric-card">
                <h4 style="margin: 0;">Ponta Ativa</h4>
                <h2 style="margin: 0.5rem 0;">R$ {results['fv_long']:,.2f}</h2>
                <p style="margin: 0; opacity: 0.9;">Fluxo: R$ {results['flow_long']:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <h4 style="margin: 0;">Ponta Passiva</h4>
                <h2 style="margin: 0.5rem 0;">R$ {results['fv_short']:,.2f}</h2>
                <p style="margin: 0; opacity: 0.9;">Fluxo: R$ {results['flow_short']:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with m3:
            card_class = "positive" if net_val > 0 else ("negative" if net_val < 0 else "")
            st.markdown(f"""
            <div class="metric-card {card_class}">
                <h4 style="margin: 0;">Ajuste Líquido</h4>
                <h2 style="margin: 0.5rem 0;">R$ {net_val:,.2f}</h2>
                <p style="margin: 0; opacity: 0.9;">
                    {'Resultado Positivo ✅' if net_val > 0 else 'Resultado Negativo ⚠️' if net_val < 0 else 'Neutro'}
                </p>
            </div>
            """, unsafe_allow_html=True)

        xlsx_memory = build_calculation_memory_xlsx(
            currency=moeda_contrato,
            notional=notional,
            amortizacao=amortizacao,
            start_date=start_date,
            end_date=end_date,
            du=du,
            dc=dc,
            type_active=type_a,
            params_active=params_a,
            leg_active=leg_long,
            type_passive=type_b,
            params_passive=params_b,
            leg_passive=leg_short,
            results=results,
        )

        st.download_button(
            "📥 Baixar memória de cálculo (.xlsx)",
            data=xlsx_memory,
            file_name=f"memoria_calculo_swap_{start_date}_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        
        # Details
        with st.expander("📋 Ver Detalhes do Cálculo"):
            st.write("### Metodologia")
            st.write(f"**Ponta Ativa ({type_a})**")
            st.write(f"- Valor Futuro: R$ {results['fv_long']:,.2f}")
            st.write(f"- Fluxo Líquido: R$ {results['flow_long']:,.2f}")
            
            # Special info for Duplo Indexador
            if type_a == "Duplo Indexador" and hasattr(leg_long, 'resultado'):
                res = leg_long.resultado
                st.write(f"- **Componente Escolhido**: {res['componente_escolhido']}")
                st.write(f"  - Componente Pré: R$ {res['componente_pre']:,.2f}")
                st.write(f"  - Componente VC antes do CAP: R$ {res['componente_vc_antes_cap']:,.2f}")
                st.write(f"  - Componente VC após CAP: R$ {res['componente_vc_apos_cap']:,.2f}")
                st.write(f"  - CAP aplicado: {res['cap_aplicado']:.4f}" if res['cap_aplicado'] > 0 else "  - CAP aplicado: Sem CAP")
            
            st.write(f"\n**Ponta Passiva ({type_b})**")
            st.write(f"- Valor Futuro: R$ {results['fv_short']:,.2f}")
            st.write(f"- Fluxo Líquido: R$ {results['flow_short']:,.2f}")
            
            if type_b == "Duplo Indexador" and hasattr(leg_short, 'resultado'):
                res = leg_short.resultado
                st.write(f"- **Componente Escolhido**: {res['componente_escolhido']}")
                st.write(f"  - Componente Pré: R$ {res['componente_pre']:,.2f}")
                st.write(f"  - Componente VC antes do CAP: R$ {res['componente_vc_antes_cap']:,.2f}")
                st.write(f"  - Componente VC após CAP: R$ {res['componente_vc_apos_cap']:,.2f}")
                st.write(f"  - CAP aplicado: {res['cap_aplicado']:.4f}" if res['cap_aplicado'] > 0 else "  - CAP aplicado: Sem CAP")
            
            st.write(f"\n**Resultado Final**")
            st.write(f"- Ajuste Líquido: R$ {net_val:,.2f}")
            st.write(f"- Período: {start_date} até {end_date}")
            st.write(f"- Dias Úteis: {du} | Dias Corridos: {dc}")
    
    except Exception as e:
        st.error(f"❌ Erro no cálculo: {str(e)}")
        st.exception(e)

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p>💼 <strong>Calculadora de Derivativos</strong></p>
    <p style="font-size: 0.9rem;">Desenvolvido por Wallace Santo | <a href="mailto:wlsant@im.ufrj.br">wlsant@im.ufrj.br</a></p>
</div>
""", unsafe_allow_html=True)
