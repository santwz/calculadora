# Calculadora de Derivativos

Calculadora de swaps e derivativos com suporte a pontas Pre, CDI, VC cambial, IPCA, SOFR e Duplo Indexador.

## Funcionalidades

1. **Pre-Fixado**
   - Linear e exponencial
   - Base DC/360 ou DU/252

2. **CDI**
   - CDI com spread
   - Percentual do CDI
   - Busca automatica de CDI via BCB

3. **Variacao Cambial (VC)**
   - Parte e contra-parte
   - Suporte a notional e amortizacao em USD ou EUR
   - Suporte a CAP
   - Principal reavaliado pela cotacao final
   - Busca automatica de PTAX via BCB para USD; EUR usa cotacao final manual

4. **IPCA**
   - Capitalizado e nao capitalizado
   - VNA automatico por numero-indice IPCA historico do IBGE/SIDRA
   - Se a data de vencimento ainda nao tiver IPCA divulgado, usa o ultimo mes disponivel
   - Fallback para ANBIMA/BCB quando o numero-indice SIDRA estiver indisponivel
   - Fallback para IPCA mensal BCB no calculo legado com VNA base manual

5. **SOFR**
   - SOFR Index oficial do New York Fed
   - Observacao T-2 baseada nas datas publicadas pela fonte oficial
   - Principal reavaliado pela cotacao final

6. **Duplo Indexador**
   - Maximo entre Pre exponencial e VC
   - VC considera variacao cambial do principal
   - CAP explicito: sem CAP ou aplicado ao componente VC
   - Detalhe separado de componente Pre, VC antes do CAP e VC apos CAP

## Instalacao

```bash
pip install -r requirements.txt
```

## Como Executar

```bash
streamlit run app.py
```

## Testes

Suite local, sem chamadas externas por padrao:

```bash
pytest -q
```

Testes de integracao com APIs externas:

```bash
$env:RUN_INTEGRATION_TESTS="1"
pytest test_bcb_integration.py -q
```

## Exportacao

Depois de calcular um swap, a aplicacao disponibiliza o botao
`Baixar memória de cálculo (.xlsx)`. O arquivo exportado contem:

- resumo executivo do swap;
- entradas informadas;
- memoria detalhada da Ponta Ativa e da Ponta Passiva;
- biblioteca textual das formulas usadas;
- dados resolvidos e fontes de mercado.

## Principais Convencoes Corrigidas

- Valores futuros e fluxos sao calculados em BRL.
- A interface usa Ponta Ativa e Ponta Passiva para os lados do swap.
- Notional e amortizacao sao informados na moeda do contrato, com suporte a USD e EUR.
- Fluxos subtraem o principal inicial convertido para BRL, nao o notional na moeda estrangeira.
- Amortizacao e calculada separadamente do notional e entra nos modelos como juros + amortizacao.
- Pontas VC e SOFR reavaliam o principal pela cotacao final.
- SOFR nao usa mais indice simulado; usa `SOFRAI.index` do New York Fed.
- CDI percentual manual usa taxa diaria equivalente antes de aplicar o percentual.
- IPCA capitalizado inclui principal corrigido pelo fator IPCA.
- Duplo Indexador mostra componentes Pre/VC e deixa explicito onde o CAP e aplicado.
- Calendario B3 usa `holidays.financial_holidays("B3")`, evitando listas hard-coded e cobrindo feriados moveis como Carnaval, Sexta-feira Santa e Corpus Christi.

## Estrutura

```text
calculadora/
├── app.py
├── models/
│   ├── leg.py
│   └── swap.py
├── utils/
│   ├── anbima.py
│   ├── calculations.py
│   ├── calendars.py
│   └── market_data.py
├── test_formulas.py
├── test_financials.py
├── test_model_regressions.py
└── test_bcb_integration.py
```
