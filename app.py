import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from financial_structs import Portfolio, Asset, Liability, RealProperty
from simulation_core import Simulator
from analysis_engine import Analyzer

# Page Config
st.set_page_config(page_title="Financial Simulator", layout="wide")
st.title("Monte Carlo Financial Simulator")

# --- SIDEBAR: Global Settings ---
st.sidebar.header("Simulation Settings")
years = st.sidebar.slider("Duration (Years)", 5, 40, 15)
num_paths = st.sidebar.slider("Monte Carlo Paths", 100, 2000, 500)
seed = st.sidebar.number_input("Random Seed", value=42)

# --- TABS: Input Data ---
tab_finances, tab_economics, tab_events, tab_goals = st.tabs([
    "Current Finances", "Economic Assumptions", "Future Events", "Goal Seek"
])

with tab_finances:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Assets")
        cash = st.number_input("Cash Savings", value=50000)
        investments = st.number_input("Invested Assets (Stocks/Bonds)", value=150000)
        stock_allocation = st.slider("Stock Allocation %", 0.0, 1.0, 0.9)
        
        st.divider()
        st.subheader("Real Estate")
        home_value = st.number_input("Current Home Value (0 if renting)", value=0)
        
    with col2:
        st.subheader("Liabilities")
        mortgage_bal = st.number_input("Mortgage Balance", value=0)
        mortgage_rate = st.number_input("Mortgage Rate (%)", value=4.5) / 100
        mortgage_pmt = st.number_input("Mortgage Monthly P&I", value=0)
        
        st.divider()
        other_loan_bal = st.number_input("Other Loans (Student/Car)", value=20000)
        other_loan_rate = st.number_input("Loan Rate (%)", value=6.0) / 100
        other_loan_pmt = st.number_input("Loan Monthly Payment", value=300)

    with col3:
        st.subheader("Income & Spend")
        # IMPORTANT: Explicit Annual to Monthly conversion for user clarity
        annual_income_1 = st.number_input("Annual Salary 1", value=120000)
        annual_income_2 = st.number_input("Annual Salary 2", value=0)
        tax_rate = st.slider("Effective Tax Rate (%)", 10, 50, 28) / 100
        
        st.divider()
        monthly_spend = st.number_input("Monthly Essential Spend (Food/Life)", value=4000)
        current_rent = st.number_input("Current Monthly Rent", value=2200)

with tab_economics:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Market Factors")
        base_inflation = st.slider("Base Inflation (%)", 0.0, 10.0, 3.0) / 100
        exp_market_return = st.slider("Expected Market Return (%)", 0.0, 15.0, 8.0) / 100
        market_vol = st.slider("Market Volatility (%)", 5.0, 30.0, 15.0) / 100
    
    with col2:
        st.markdown("### Growth Factors")
        housing_growth_mean = base_inflation + 0.01 # Default 1% over inflation
        salary_growth_merit = st.slider("Salary Merit Increase (Above Inflation) %", 0.0, 5.0, 1.0) / 100

with tab_events:
    col_header, col_reset = st.columns([3, 1])
    with col_header:
        st.info("Add major future financial events here (e.g., buying a house, car, or having a child).")
    with col_reset:
        if st.button("🗑️ Clear All Events", type="secondary"):
            st.session_state.events_list = []
            st.rerun()

    if 'events_list' not in st.session_state:
        st.session_state.events_list = []
    
    # --- NEW: "Year" based Input (No more Month math) ---
    with st.expander("Add New Event", expanded=True):
        ev_type = st.selectbox("Event Type", ["Purchase Asset (Car/House)", "Change Monthly Spend"])
        
        # User inputs YEAR (e.g. 3.5), we convert to MONTH internally
        ev_year = st.number_input("Year of Event (e.g., 1.0 = 1 year from now)", min_value=0.1, value=3.0, step=0.5)
        ev_month_idx = int(ev_year * 12) # Conversion logic
        
        if ev_type == "Purchase Asset (Car/House)":
            ev_name = st.text_input("Asset Name", "Dream House")
            ev_cost = st.number_input("Total Cost", value=500000)
            ev_down = st.number_input("Down Payment", value=100000)
            ev_is_re = st.checkbox("Is Real Estate?", value=True)
            ev_is_primary = st.checkbox("Is Primary Home? (Stops Rent)", value=True)
            
            # Loan details
            c1, c2 = st.columns(2)
            with c1:
                ev_loan_rate = st.number_input("Loan Rate (%)", value=6.0, key="ev_loan_rate") / 100
            with c2:
                ev_loan_term_years = st.number_input("Loan Term (Years)", value=30, key="ev_loan_term")
            
            # Auto-calc payment
            if ev_cost > ev_down and ev_loan_rate > 0:
                n = ev_loan_term_years * 12
                r = ev_loan_rate / 12
                loan = ev_cost - ev_down
                calc_pmt = loan * (r * (1 + r)**n) / ((1 + r)**n - 1)
            else:
                calc_pmt = 0
            
            ev_pmt = st.number_input("Monthly Payment (Auto-Calc)", value=float(f"{calc_pmt:.2f}"), key="ev_pmt")

            if st.button("Add Purchase Event"):
                new_ev = {
                    'month': ev_month_idx, # Store the calculated month index
                    'display_year': ev_year, # Store year for display
                    'type': 'purchase_asset',
                    'name': ev_name,
                    'value': ev_cost,
                    'down_payment': ev_down,
                    'rate': ev_loan_rate,
                    'monthly_payment': ev_pmt,
                    'is_real_estate': ev_is_re,
                    'is_primary_home': ev_is_primary
                }
                st.session_state.events_list.append(new_ev)
                st.success(f"Added '{ev_name}' at Year {ev_year} (Month {ev_month_idx})")

        elif ev_type == "Change Monthly Spend":
            ev_new_spend = st.number_input("New Monthly Spend Amount", value=6000, key="ev_spend_amt")
            if st.button("Add Spend Change"):
                new_ev = {
                    'month': ev_month_idx,
                    'display_year': ev_year,
                    'type': 'param_change',
                    'param': 'monthly_spend',
                    'value': ev_new_spend
                }
                st.session_state.events_list.append(new_ev)
                st.success(f"Added Spend Change at Year {ev_year}")

    # --- Display Current Events Table ---
    if st.session_state.events_list:
        st.write("### Active Events Schedule")
        
        # Create a cleaner view for the user
        display_data = []
        for i, e in enumerate(st.session_state.events_list):
            # Calculate Year if it wasn't stored previously (for backward compatibility)
            y = e.get('display_year', e['month'] / 12.0)
            
            summary = f"{e['type']}"
            if e['type'] == 'purchase_asset':
                summary = f"Buy {e['name']} (${e['value']:,.0f})"
            elif e['type'] == 'param_change':
                summary = f"New Spend: ${e['value']:,.0f}/mo"
                
            display_data.append({
                "Year": f"{y:.1f}",
                "Event": summary,
                "Month Index": e['month']
            })
            
        st.table(pd.DataFrame(display_data))

# --- EXECUTION LOGIC ---

def build_config_and_portfolio():
    # 1. Build Portfolio Object
    pf = Portfolio()
    
    # Assets
    pf.add_asset(Asset("Cash", cash, allocation_to_market=0.0))
    if investments > 0:
        pf.add_asset(Asset("Investments", investments, allocation_to_market=stock_allocation))
    if home_value > 0:
        pf.add_asset(RealProperty("Primary Home", home_value))
        
    # Liabilities
    if mortgage_bal > 0:
        pf.add_liability(Liability("Mortgage", mortgage_bal, mortgage_rate, mortgage_pmt, is_mortgage=True))
    if other_loan_bal > 0:
        pf.add_liability(Liability("Loan", other_loan_bal, other_loan_rate, other_loan_pmt))
        
    # Income
    pf.incomes.append({'name': 'Salary 1', 'amount': annual_income_1 / 12.0})
    if annual_income_2 > 0:
        pf.incomes.append({'name': 'Salary 2', 'amount': annual_income_2 / 12.0})
        
    # 2. Build Config Dict
    config = {
        'years': years,
        'num_paths': num_paths,
        'seed': int(seed),
        'tax_rate': tax_rate,
        'monthly_spend': monthly_spend,
        'initial_rent': current_rent,
        'base_inflation': base_inflation, # This is annual
        'base_interest_rate': 0.04,
        'market_params': {
            'expected_mkt_return': exp_market_return,
            'mkt_vol': market_vol,
            'base_inflation': base_inflation,
            'base_interest_rate': 0.04,
            'merit_increase': salary_growth_merit
        },
        'events': st.session_state.events_list
    }
    
    return pf, config

# --- RUN BUTTON ---
if st.button("Run Simulation", type="primary"):
    with st.spinner("Running Monte Carlo Simulation..."):
        pf, config = build_config_and_portfolio()
        sim = Simulator(pf, config)
        sim.run()
        
        # Store results in session state to persist
        st.session_state.sim_results = sim.results
        st.session_state.sim_config = config
        st.session_state.sim_pf = pf

# --- RESULTS DISPLAY ---
if 'sim_results' in st.session_state:
    results = st.session_state.sim_results
    nw = results['net_worth']
    failures = results['liquidity_failure']
    
    # 1. Metrics
    final_nw = nw[-1, :]
    success_rate = 100 * (1 - np.sum(failures) / len(failures))
    median_nw = np.median(final_nw)
    
    st.divider()
    st.subheader("Simulation Results")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Success Rate", f"{success_rate:.1f}%")
    m2.metric("Median Net Worth", f"${median_nw:,.0f}")
    m3.metric("Pessimistic (5th %)", f"${np.percentile(final_nw, 5):,.0f}")
    m4.metric("Optimistic (95th %)", f"${np.percentile(final_nw, 95):,.0f}")
    
    # 2. Charts
    # Calculate percentiles over time
    num_months = nw.shape[0]
    years = np.arange(num_months) / 12.0 # <--- CONVERT TO YEARS HERE
    
    p5 = np.percentile(nw, 5, axis=1)
    p25 = np.percentile(nw, 25, axis=1)
    p50 = np.median(nw, axis=1)
    p75 = np.percentile(nw, 75, axis=1)
    p95 = np.percentile(nw, 95, axis=1)
    
    fig = go.Figure()
    
    # Add traces (Fans) - Note we use x=years now
    fig.add_trace(go.Scatter(x=years, y=p95, mode='lines', line=dict(width=0), showlegend=False, name='95%'))
    fig.add_trace(go.Scatter(x=years, y=p5, mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(0,100,255,0.1)', name='5th-95th Range'))
    
    fig.add_trace(go.Scatter(x=years, y=p75, mode='lines', line=dict(width=0), showlegend=False, name='75%'))
    fig.add_trace(go.Scatter(x=years, y=p25, mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(0,100,255,0.2)', name='25th-75th Range'))
    
    fig.add_trace(go.Scatter(x=years, y=p50, mode='lines', line=dict(color='blue', width=2), name='Median'))
    
    # Update title to say "Years"
    fig.update_layout(title="Net Worth Projection", xaxis_title="Years", yaxis_title="Net Worth ($)", height=500)
    st.plotly_chart(fig, use_container_width=True) 

    # 3. Goal Seek (in dedicated tab or below)
    with tab_goals:
        st.subheader("Backward Looking Goal Seek")
        target_amount = st.number_input("Target Net Worth ($)", value=2000000)
        target_prob = st.slider("Required Probability (%)", 50, 99, 80) / 100
        
        if st.button("Run Goal Seek"):
            pf_gs, config_gs = build_config_and_portfolio()
            # Re-instantiate a fresh simulator for the analyzer
            sim_gs = Simulator(pf_gs, config_gs)
            analyzer = Analyzer(sim_gs)
            
            # We need to capture the print output or refactor Analyzer to return string
            # For now, let's just create a custom solver loop here for the UI
            with st.spinner("Optimizing Spending..."):
                # Simplified Binary Search for UI
                original_spend = config_gs['monthly_spend']
                low = 0
                high = original_spend * 2
                best = None
                
                for _ in range(8): # Fast iterations
                    mid = (low + high) / 2
                    config_gs['monthly_spend'] = mid
                    temp_sim = Simulator(pf_gs, config_gs)
                    temp_sim.run()
                    res = temp_sim.results['net_worth'][-1, :]
                    prob = np.sum(res >= target_amount) / len(res)
                    
                    if prob >= target_prob:
                        best = mid
                        low = mid # Can we spend more?
                    else:
                        high = mid # Spend less
                
                if best:
                    delta = original_spend - best
                    if delta > 0:
                        st.warning(f"Goal Unmet! You need to reduce monthly spend by **${delta:,.2f}** (New Limit: ${best:,.2f})")
                    else:
                        st.success(f"Goal Met! You can actually increase spend by **${abs(delta):,.2f}** (New Limit: ${best:,.2f})")
                else:
                    st.error("Goal Unreachable even with $0 spend. Try increasing income or extending years.")