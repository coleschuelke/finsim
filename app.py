import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import copy

from financial_structs import Portfolio, Asset, Liability, RealProperty
from simulation_core import Simulator
from analysis_engine import Analyzer

# --- PAGE CONFIG ---
st.set_page_config(page_title="Stochastic Financial Engine", layout="wide", initial_sidebar_state="expanded")
st.title("Monte Carlo Financial Engine")

# --- HELPERS ---
def calculate_pmt(principal, annual_rate, years):
    if principal <= 0 or years <= 0: return 0.0
    r = annual_rate / 12.0
    n = years * 12.0
    if r == 0: return principal / n
    return principal * (r * (1 + r)**n) / ((1 + r)**n - 1)

def init_session_state():
    if 'events_list' not in st.session_state:
        # Defaulting to the upcoming vehicle purchase 
        st.session_state.events_list = [{
            'month': 12, # Early next year
            'display_year': 1.0,
            'type': 'purchase_asset',
            'name': 'Toyota 4Runner',
            'value': 35000,
            'down_payment': 15000,
            'rate': 0.065,
            'monthly_payment': calculate_pmt(20000, 0.065, 5),
            'is_real_estate': False,
            'is_primary_home': False,
            'retains_value': False # Depreciate immediately
        }]
    if 'sim_run' not in st.session_state:
        st.session_state.sim_run = False

init_session_state()

# --- SIDEBAR: GLOBAL PHYSICS ---
with st.sidebar:
    st.header("Simulation Parameters")
    years = st.slider("Duration (Years)", 5, 40, 15)
    num_paths = st.slider("Monte Carlo Paths", 100, 2000, 500)
    seed = st.number_input("Random Seed", value=42)
    
    st.divider()
    st.header("Macro Economics")
    base_inflation = st.slider("Base Inflation (%)", 0.0, 10.0, 3.0) / 100
    exp_market_return = st.slider("Expected Mkt Return (%)", 0.0, 15.0, 8.0) / 100
    market_vol = st.slider("Market Volatility (%)", 5.0, 30.0, 15.0) / 100
    salary_growth_merit = st.slider("Salary Merit Increase (%)", 0.0, 5.0, 1.0) / 100

# --- MAIN UI TABS ---
tab_dash, tab_finances, tab_events, tab_analytics = st.tabs([
    "📊 Dashboard", "💰 Finances", "📅 Events", "🔬 Deep Analytics"
])

# --- TAB: FINANCES ---
with tab_finances:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Current Assets")
        cash = st.number_input("Cash & Checking (Liquid)", value=50000, step=5000)
        brokerage = st.number_input("Taxable Brokerage (Liquid)", value=25000, step=5000)
        retirement_401k = st.number_input("401k / IRA (Illiquid)", value=125000, step=5000)
        stock_alloc = st.slider("Stock Allocation %", 0.0, 1.0, 0.9)
        
        st.divider()
        home_value = st.number_input("Primary Home Value", value=0, step=10000)
        
    with col2:
        st.subheader("Current Liabilities")
        mortgage_bal = st.number_input("Mortgage Balance", value=0, step=10000)
        mortgage_rate = st.number_input("Mortgage Rate (%)", value=4.5, step=0.1) / 100
        mortgage_years = st.number_input("Remaining Term (Yrs)", value=30, step=1)
        mortgage_pmt = calculate_pmt(mortgage_bal, mortgage_rate, mortgage_years)
        if mortgage_bal > 0: st.metric("Est. Mortgage Payment", f"${mortgage_pmt:,.2f}")
        
        st.divider()
        st.write("**Other Loans**")
        loan_data = pd.DataFrame([{"Name": "Student Loan", "Balance": 20000.0, "Rate (%)": 6.0, "Years": 10.0}])
        other_loans_df = st.data_editor(loan_data, num_rows="dynamic", use_container_width=True)

    with col3:
        st.subheader("Income & Spend")
        st.info("Taxes auto-calculated via 2024 progressive brackets.")
        
        c3a, c3b = st.columns(2)
        with c3a:
            inc1_name = st.text_input("Income 1 Name", "Cole")
            inc1_val = st.number_input("Salary 1", value=120000, step=5000)
            inc1_401k = st.number_input("401k Contrib 1", value=23000, max_value=23000)
        with c3b:
            inc2_name = st.text_input("Income 2 Name", "Jenna")
            inc2_val = st.number_input("Salary 2", value=140000, step=5000)
            inc2_401k = st.number_input("401k Contrib 2", value=23000, max_value=23000)
            
        st.divider()
        monthly_spend = st.number_input("Monthly Living Spend", value=4000, step=500)
        current_rent = st.number_input("Monthly Rent", value=2200, step=100)

# --- TAB: EVENTS ---
with tab_events:
    ev_col1, ev_col2 = st.columns([1, 2])
    
    with ev_col1:
        st.subheader("Add New Event")
        ev_type = st.selectbox("Type", ["Purchase Asset", "Change Spend"])
        ev_year = st.number_input("Year of Event (e.g., 1.5)", min_value=0.1, value=3.0, step=0.5)
        ev_month_idx = int(ev_year * 12)
        
        if ev_type == "Purchase Asset":
            ev_name = st.text_input("Asset Name", "Vehicle / House")
            ev_cost = st.number_input("Total Cost", value=50000)
            ev_down = st.number_input("Down Payment", value=10000)
            ev_retains_val = st.checkbox("Retains Value (Counts toward Net Worth)", value=False, help="Uncheck to write off as a sunk cost immediately.")
            ev_is_re = st.checkbox("Is Real Estate?", value=False)
            ev_is_primary = st.checkbox("Is Primary Home? (Zeroes out rent)", value=False)
            ev_loan_rate = st.number_input("Loan Rate (%)", value=7.0) / 100
            ev_loan_term = st.number_input("Loan Term (Yrs)", value=5)
            
            calc_pmt = calculate_pmt(ev_cost - ev_down, ev_loan_rate, ev_loan_term)
            st.metric("Est. Monthly Payment", f"${calc_pmt:,.2f}")
            
            if st.button("➕ Add Purchase", use_container_width=True):
                st.session_state.events_list.append({
                    'month': ev_month_idx, 'display_year': ev_year, 'type': 'purchase_asset',
                    'name': ev_name, 'value': ev_cost, 'down_payment': ev_down,
                    'rate': ev_loan_rate, 'monthly_payment': calc_pmt,
                    'is_real_estate': ev_is_re, 'is_primary_home': ev_is_primary, 'retains_value': ev_retains_val
                })
                st.rerun()
                
        elif ev_type == "Change Spend":
            ev_new_spend = st.number_input("New Monthly Spend", value=6000)
            if st.button("➕ Add Spend Change", use_container_width=True):
                st.session_state.events_list.append({
                    'month': ev_month_idx, 'display_year': ev_year, 'type': 'param_change',
                    'param': 'monthly_spend', 'value': ev_new_spend
                })
                st.rerun()

    with ev_col2:
        st.subheader("Scheduled Events")
        if st.session_state.events_list:
            df_events = pd.DataFrame([{
                "Year": e['display_year'], 
                "Action": f"Buy {e['name']}" if e['type'] == 'purchase_asset' else "Change Spend",
                "Value": f"${e['value']:,.0f}",
                "Sunk Cost": "Yes" if not e.get('retains_value', True) else "No"
            } for e in st.session_state.events_list])
            st.dataframe(df_events, use_container_width=True, hide_index=True)
            if st.button("🗑️ Clear All Schedule"):
                st.session_state.events_list = []
                st.rerun()
        else:
            st.info("No events scheduled.")

# --- EXECUTION LOGIC ---
def build_engine():
    pf = Portfolio()
    pf.add_asset(Asset("Cash", cash, allocation_to_market=0.0, is_liquid=True))
    if brokerage > 0: pf.add_asset(Asset("Brokerage", brokerage, allocation_to_market=stock_alloc, is_liquid=True))
    if retirement_401k > 0: pf.add_asset(Asset("401k", retirement_401k, allocation_to_market=stock_alloc, is_liquid=False))
    if home_value > 0: pf.add_asset(RealProperty("Primary Home", home_value))
        
    if mortgage_bal > 0: pf.add_liability(Liability("Mortgage", mortgage_bal, mortgage_rate, mortgage_pmt, is_mortgage=True))
    
    if not other_loans_df.empty:
        for _, row in other_loans_df.iterrows():
            if row["Balance"] > 0:
                l_pmt = calculate_pmt(row["Balance"], row["Rate (%)"] / 100.0, row["Years"])
                pf.add_liability(Liability(row["Name"], row["Balance"], row["Rate (%)"] / 100.0, l_pmt))
        
    pf.incomes.append({'name': inc1_name, 'amount': inc1_val / 12.0, 'annual_401k_contribution': inc1_401k})
    if inc2_val > 0: pf.incomes.append({'name': inc2_name, 'amount': inc2_val / 12.0, 'annual_401k_contribution': inc2_401k})
        
    config = {
        'years': years, 'num_paths': num_paths, 'seed': int(seed),
        'monthly_spend': monthly_spend, 'initial_rent': current_rent,
        'base_inflation': base_inflation, 'base_interest_rate': 0.04,
        'market_params': {
            'expected_mkt_return': exp_market_return, 'mkt_vol': market_vol,
            'base_inflation': base_inflation, 'base_interest_rate': 0.04, 'merit_increase': salary_growth_merit
        },
        'events': copy.deepcopy(st.session_state.events_list)
    }
    return pf, config

# --- FLOATING RUN BUTTON ---
st.sidebar.divider()
if st.sidebar.button("🚀 RUN SIMULATION", type="primary", use_container_width=True):
    with st.spinner("Calculating stochastic paths..."):
        pf, config = build_engine()
        sim = Simulator(pf, config)
        sim.run()
        st.session_state.sim_results = sim.results
        st.session_state.sim_obj = sim # Store for Analyzer
        st.session_state.sim_run = True

# --- DASHBOARD RENDERING ---
if st.session_state.sim_run:
    results = st.session_state.sim_results
    analyzer = Analyzer(st.session_state.sim_obj)
    
    with tab_dash:
        nw = results['net_worth']
        failures = results['liquidity_failure']
        final_nw = nw[-1, :]
        success_rate = 100 * (1 - np.sum(failures) / len(failures))
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Solvency Success", f"{success_rate:.1f}%")
        m2.metric("Median Net Worth", f"${np.median(final_nw):,.0f}")
        m3.metric("5th % (Pessimistic)", f"${np.percentile(final_nw, 5):,.0f}")
        m4.metric("95th % (Optimistic)", f"${np.percentile(final_nw, 95):,.0f}")
        
        time_axis = np.arange(nw.shape[0]) / 12.0
        
        # Main Plot
        fig_main = go.Figure()
        fig_main.add_trace(go.Scatter(x=time_axis, y=np.percentile(nw, 95, axis=1), mode='lines', line=dict(width=0), showlegend=False))
        fig_main.add_trace(go.Scatter(x=time_axis, y=np.percentile(nw, 5, axis=1), mode='lines', fill='tonexty', fillcolor='rgba(0,100,255,0.1)', name='5th-95th Range'))
        fig_main.add_trace(go.Scatter(x=time_axis, y=np.median(nw, axis=1), mode='lines', line=dict(color='blue', width=3), name='Median Total NW'))
        
        # Overlay Liquid Assets
        fig_main.add_trace(go.Scatter(x=time_axis, y=np.median(results['liquid_assets'], axis=1), mode='lines', line=dict(color='green', width=2, dash='dash'), name='Median Liquid Assets'))
        
        fig_main.update_layout(title="Wealth Trajectory", xaxis_title="Years", yaxis_title="USD ($)", hovermode="x unified", height=500)
        st.plotly_chart(fig_main, use_container_width=True)

    with tab_analytics:
        st.header("Advanced Scenario Analysis")
        
        with st.expander("📍 Cost of Living Compare", expanded=False):
            st.write("Compare the baseline simulation against a temporary or permanent relocation.")
            col_a, col_b = st.columns(2)
            with col_a:
                alt_spend = st.number_input("Alt Monthly Spend", value=6000)
            with col_b:
                alt_rent = st.number_input("Alt Monthly Rent", value=3500)
                
            if st.button("Run CoL Comparison"):
                with st.spinner("Running alternate reality..."):
                    col_results = analyzer.compare_city_col(alt_spend, alt_rent)
                    
                    st.metric("Baseline Final NW", f"${col_results['base_median_nw']:,.0f}")
                    delta = col_results['alt_median_nw'] - col_results['base_median_nw']
                    st.metric("Alternate Final NW", f"${col_results['alt_median_nw']:,.0f}", delta=f"{delta:,.0f} Opportunity Cost")
        
        with st.expander("⚖️ A/B Comparator (True Opportunity Cost)", expanded=False):
            st.write("Compare the baseline simulation against an alternate reality where you make a specific purchase. This reveals the true cost of consumption over time (purchase price + lost compound growth).")
            
            ab_col1, ab_col2 = st.columns(2)
            with ab_col1:
                ab_name = st.text_input("Hypothetical Purchase", "Sports Car")
                ab_cost = st.number_input("Total Purchase Price", value=60000, step=5000)
                ab_down = st.number_input("Down Payment", value=15000, step=5000)
                ab_retains = st.checkbox("Retains Value?", value=False, help="Uncheck to write off immediately as a sunk cost.")
            with ab_col2:
                ab_year_execute = st.number_input("Execute Purchase in Year:", value=2.0, step=0.5)
                ab_year_eval = st.number_input("Evaluate Cost at Year:", value=10.0, step=1.0, help="The future year to measure the difference in net worth.")
                ab_rate = st.number_input("Loan Rate (%)", value=6.0, key='ab_rate') / 100.0
                ab_term = st.number_input("Loan Term (Years)", value=5, key='ab_term')

            if st.button("Run A/B Test"):
                with st.spinner(f"Comparing timelines at Year {ab_year_eval}..."):
                    ab_pmt = calculate_pmt(ab_cost - ab_down, ab_rate, ab_term)
                    
                    hypothetical_event = {
                        'month': int(ab_year_execute * 12),
                        'type': 'purchase_asset',
                        'name': ab_name,
                        'value': ab_cost,
                        'down_payment': ab_down,
                        'rate': ab_rate,
                        'monthly_payment': ab_pmt,
                        'is_real_estate': False,
                        'retains_value': ab_retains
                    }
                    
                    ab_results = analyzer.opportunity_cost_delta(hypothetical_event, evaluation_year=ab_year_eval)
                    
                    st.divider()
                    st.markdown(f"### The Reality of Buying the '{ab_name}'")
                    
                    # Formatting the output to highlight the delta
                    res_c1, res_c2 = st.columns(2)
                    
                    # Net Worth Impact
                    res_c1.metric(
                        "Baseline Net Worth", 
                        f"${ab_results['baseline_nw']:,.0f}"
                    )
                    res_c1.metric(
                        "Alternate Net Worth", 
                        f"${ab_results['alternate_nw']:,.0f}", 
                        delta=f"-${ab_results['net_worth_cost']:,.0f} True Cost", 
                        delta_color="inverse"
                    )
                    
                    # Liquidity Impact
                    res_c2.metric(
                        "Baseline Liquid Assets", 
                        f"${ab_results['baseline_liq']:,.0f}" # Note: Ensure you extract base_liq in the Analyzer backend if you haven't
                    )
                    res_c2.metric(
                        "Alternate Liquid Assets", 
                        f"${ab_results['liquidity_cost']:,.0f}", # Using the cost variable just to display the delta below
                        delta=f"-${ab_results['liquidity_cost']:,.0f} Liquidity Hit", 
                        delta_color="inverse"
                    )
                    
                    st.info(f"**Interpretation:** By Year {ab_year_eval}, buying this ${ab_cost:,.0f} asset actually costs you **${ab_results['net_worth_cost']:,.0f}** in total wealth due to the purchase price, loan interest, and lost compound growth.")

        with st.expander("⏱️ Purchase Timing Optimizer", expanded=False):
            st.write("Find the earliest month you can make a purchase while maintaining an 85% solvency confidence.")
            opt_name = st.text_input("Purchase Name", "Vehicle")
            opt_cost = st.number_input("Target Price", value=40000)
            opt_down = st.number_input("Target Down Payment", value=40000)
            
            if st.button("Optimize Timing"):
                with st.spinner("Solving..."):
                    template = {
                        'type': 'purchase_asset', 'name': opt_name, 'value': opt_cost, 
                        'down_payment': opt_down, 'rate': 0.0, 'monthly_payment': 0, 
                        'is_real_estate': False, 'retains_value': False
                    }
                    best_month = analyzer.optimize_purchase_timing(template)
                    if best_month:
                        st.success(f"**Optimal Timing:** You can safely pull the trigger in **Month {best_month}** (Year {best_month/12:.1f}).")
                    else:
                        st.error("This purchase breaks the 85% confidence threshold at any point in the simulation.")

        with st.expander("🌊 Cash Flow & Drawdown Metrics", expanded=True):
            cf_tax = np.mean(results['cf_tax'], axis=1)
            cf_spend = np.mean(results['cf_spend'], axis=1)
            cf_debt = np.mean(results['cf_debt'], axis=1)
            cf_invested = np.mean(results['cf_invested'], axis=1)
            
            fig_cf = go.Figure()
            fig_cf.add_trace(go.Scatter(x=time_axis, y=cf_spend, mode='lines', stackgroup='one', name='Living Expenses'))
            fig_cf.add_trace(go.Scatter(x=time_axis, y=cf_debt, mode='lines', stackgroup='one', name='Debt Service'))
            fig_cf.add_trace(go.Scatter(x=time_axis, y=cf_tax, mode='lines', stackgroup='one', name='Taxes'))
            fig_cf.add_trace(go.Scatter(x=time_axis, y=cf_invested, mode='lines', stackgroup='one', name='Invested'))
            fig_cf.update_layout(title="Average Monthly Cash Flow", height=400)
            st.plotly_chart(fig_cf, use_container_width=True)
            
            # Drawdown
            successful_paths = results['liquidity_failure'] == 0
            if np.any(successful_paths):
                min_cash = np.min(results['cash_balance'][:, successful_paths], axis=0)
                fig_hist = go.Figure(data=[go.Histogram(x=min_cash, nbinsx=50, marker_color='orange')])
                fig_hist.add_vline(x=0, line_dash="dash", line_color="red")
                fig_hist.update_layout(title="Minimum Cash Hit per Path (Stress Test)", height=300)
                st.plotly_chart(fig_hist, use_container_width=True)

        with st.expander("🦅 Financial Independence (FI) Tracker", expanded=False):
            st.write("Tracks the probability of reaching FI over time. FI is triggered when the safe yield from your liquid assets exceeds your inflation-adjusted living expenses.")
            
            swr_input = st.number_input("Safe Withdrawal Rate (%)", value=4.0, step=0.1, help="The percentage of your liquid portfolio you can safely withdraw annually.") / 100.0
            
            if st.button("Calculate FI Trajectory"):
                with st.spinner("Analyzing withdrawal rates across all paths..."):
                    years_fi, fi_prob, crossover_months = analyzer.calculate_fi_crossover(swr=swr_input)
                    
                    # 1. Plot the Probability Curve
                    fig_fi = go.Figure()
                    fig_fi.add_trace(go.Scatter(
                        x=years_fi, 
                        y=fi_prob,
                        mode='lines',
                        fill='tozeroy',
                        fillcolor='rgba(128, 0, 128, 0.2)',
                        line=dict(color='purple', width=3),
                        name='Probability of FI'
                    ))
                    
                    fig_fi.update_layout(
                        title=f"Cumulative Probability of Reaching FI (SWR: {swr_input*100:.1f}%)",
                        xaxis_title="Years from Now",
                        yaxis_title="Probability (%)",
                        yaxis_range=[0, 105],
                        height=400,
                        hovermode="x unified"
                    )
                    st.plotly_chart(fig_fi, use_container_width=True)
                    
                    # 2. Extract the Median Timeline
                    successful_fi_paths = crossover_months[crossover_months >= 0]
                    if len(successful_fi_paths) > 0:
                        median_fi_month = np.median(successful_fi_paths)
                        st.success(f"**Median FI Timeline:** Year {median_fi_month / 12:.1f} (Month {int(median_fi_month)})")
                    else:
                        st.warning("FI is not reached in any of the simulated paths within the current timeframe. Consider increasing the simulation duration or adjusting savings rates.")