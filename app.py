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
tab_dash, tab_finances, tab_events, tab_liquid, tab_analytics = st.tabs([
    "📊 Dashboard", "💰 Finances", "📅 Events", "💧 Liquid Wealth & FI", "🔬 Deep Analytics"
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
        ev_type = st.selectbox("Type", ["Purchase Asset", "Change Spend", "Change Rent", "Change Income", "Recurring RSU Vest"])
        ev_year = st.number_input("Year of Event (e.g., 1.5)", min_value=0.1, value=3.0, step=0.5)
        ev_month_idx = int(ev_year * 12)
        
        if ev_type == "Purchase Asset":
            ev_name = st.text_input("Asset Name", "Vehicle / House")
            ev_cost = st.number_input("Total Cost", value=50000)
            ev_down = st.number_input("Down Payment", value=10000)
            ev_retains_val = st.checkbox("Retains Value (Counts toward Net Worth)", value=False)
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
                
        elif ev_type == "Change Rent":
            ev_new_rent = st.number_input("New Monthly Rent", value=2500, step=100)
            if st.button("➕ Add Rent Change", use_container_width=True):
                st.session_state.events_list.append({
                    'month': ev_month_idx, 'display_year': ev_year, 'type': 'param_change',
                    'param': 'rent', 'value': ev_new_rent
                })
                st.rerun()
                
        elif ev_type == "Change Income":
            st.info("Income Name must exactly match the name in the Finances tab.")
            ev_inc_name = st.text_input("Income Name", "Cole")
            ev_new_salary = st.number_input("New Annual Salary", value=150000, step=5000)
            ev_new_401k = st.number_input("New Annual 401k Contrib", value=23000, max_value=23000)
            
            if st.button("➕ Add Income Change", use_container_width=True):
                st.session_state.events_list.append({
                    'month': ev_month_idx, 'display_year': ev_year, 'type': 'change_income',
                    'income_name': ev_inc_name, 'new_salary': ev_new_salary, 'new_401k': ev_new_401k
                })
                st.rerun()
                
        elif ev_type == "Recurring RSU Vest":
            st.info("Simulates recurring stock vests. Taxes are withheld immediately before the net equity hits your portfolio.")
            ev_rsu_name = st.text_input("Asset Bucket Name", "Company Stock")
            ev_rsu_val = st.number_input("Gross Vest Value ($)", value=25000, step=5000)
            ev_rsu_freq = st.number_input("Vest Frequency (Months)", value=6, step=1, help="6 = Bi-annually, 3 = Quarterly")
            ev_rsu_tax = st.slider("Estimated Tax Withholding (%)", 10, 50, 30) / 100.0
            
            if st.button("➕ Add Recurring Vest", use_container_width=True):
                st.session_state.events_list.append({
                    'month': ev_month_idx, 'display_year': ev_year, 'type': 'rsu_vest',
                    'asset_name': ev_rsu_name, 'value': ev_rsu_val, 'frequency': ev_rsu_freq,
                    'tax_withholding': ev_rsu_tax
                })
                st.rerun()

    with ev_col2:
        st.subheader("Scheduled Events")
        if st.session_state.events_list:
            display_data = []
            for e in st.session_state.events_list:
                freq_str = f" (Every {e['frequency']} mo)" if e.get('frequency', 0) > 0 else ""
                
                if e['type'] == 'purchase_asset':
                    action_str = f"Buy {e['name']}"
                    val_str = f"${e['value']:,.0f}"
                    sunk_str = "Yes" if not e.get('retains_value', True) else "No"
                elif e['type'] == 'change_income':
                    action_str = f"Change Salary ({e['income_name']})"
                    val_str = f"${e['new_salary']:,.0f}/yr"
                    sunk_str = "N/A"
                elif e['type'] == 'param_change' and e['param'] == 'monthly_spend':
                    action_str = "Change Spend"
                    val_str = f"${e['value']:,.0f}/mo"
                    sunk_str = "N/A"
                elif e['type'] == 'param_change' and e['param'] == 'rent':
                    action_str = "Change Rent"
                    val_str = f"${e['value']:,.0f}/mo"
                    sunk_str = "N/A"
                elif e['type'] == 'rsu_vest':
                    action_str = f"RSU Vest: {e['asset_name']}{freq_str}"
                    val_str = f"${e['value']:,.0f} gross"
                    sunk_str = "N/A"
                    
                display_data.append({
                    "Start Year": e['display_year'], 
                    "Action": action_str,
                    "Amount": val_str,
                    "Sunk Cost": sunk_str
                })
                
            df_events = pd.DataFrame(display_data)
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
    
    with tab_liquid:
        st.header("Liquid Wealth & Financial Independence")
        st.info("These metrics strictly exclude primary home equity and illiquid retirement accounts (401k/IRA).")
        
        liq = results['liquid_assets']
        final_liq = liq[-1, :]
        
        l1, l2, l3 = st.columns(3)
        l1.metric("Median Liquid Wealth (End)", f"${np.median(final_liq):,.0f}")
        l2.metric("Pessimistic Liquid (5th %)", f"${np.percentile(final_liq, 5):,.0f}")
        l3.metric("Optimistic Liquid (95th %)", f"${np.percentile(final_liq, 95):,.0f}")
        
        # 1. Pure Liquid Fan Chart
        fig_liq = go.Figure()
        fig_liq.add_trace(go.Scatter(x=time_axis, y=np.percentile(liq, 95, axis=1), mode='lines', line=dict(width=0), showlegend=False))
        fig_liq.add_trace(go.Scatter(x=time_axis, y=np.percentile(liq, 5, axis=1), mode='lines', fill='tonexty', fillcolor='rgba(34, 139, 34, 0.1)', name='5th-95th Range'))
        fig_liq.add_trace(go.Scatter(x=time_axis, y=np.median(liq, axis=1), mode='lines', line=dict(color='green', width=3), name='Median Liquid Assets'))
        
        fig_liq.update_layout(title="Liquid Wealth Trajectory (No House/401k)", xaxis_title="Years", yaxis_title="USD ($)", hovermode="x unified", height=400)
        st.plotly_chart(fig_liq, use_container_width=True)
        
        st.divider()
        st.subheader("Accelerating Financial Independence")
        
        c_swr, c_run = st.columns([1, 4])
        with c_swr:
            swr_input = st.number_input("Target SWR (%)", value=4.0, step=0.1) / 100.0
            
        with c_run:
            st.write("Calculate how adjusting your baseline monthly spend moves your FI date. The line represents the year your safe withdrawal yield eclipses your living expenses.")
            if st.button("Run FI Spend Sweep", use_container_width=True):
                with st.spinner("Solving FI crossover for spending matrix..."):
                    spends, fi_years = analyzer.optimize_fi_spend(swr=swr_input)
                    
                    # Filter out None values for plotting
                    plot_spends = [s for s, y in zip(spends, fi_years) if y is not None]
                    plot_years = [y for y in fi_years if y is not None]
                    
                    if plot_years:
                        fig_accel = go.Figure()
                        fig_accel.add_trace(go.Scatter(
                            x=plot_spends, y=plot_years, mode='lines+markers',
                            line=dict(color='purple', width=3), marker=dict(size=8),
                            name="FI Year"
                        ))
                        
                        # Add a vertical marker for current spend
                        current_spend = config['monthly_spend']
                        fig_accel.add_vline(x=current_spend, line_width=2, line_dash="dash", line_color="red", annotation_text="Current Spend")
                        
                        fig_accel.update_layout(
                            title="Time-Cost of Lifestyle (Spend vs. FI Year)",
                            xaxis_title="Baseline Monthly Spend ($)",
                            yaxis_title="Years to FI",
                            height=400,
                            hovermode="x unified"
                        )
                        st.plotly_chart(fig_accel, use_container_width=True)
                        
                        # Calculate the slope to give a direct time/cost metric
                        if len(plot_spends) > 1:
                            delta_spend = plot_spends[-1] - plot_spends[0]
                            delta_years = plot_years[-1] - plot_years[0]
                            years_per_1k = (delta_years / delta_spend) * 1000
                            st.success(f"**Optimization Metric:** At your current trajectory, every **$1,000/mo** added to your baseline lifestyle delays FI by approximately **{years_per_1k:.1f} years**.")
                    else:
                        st.error("FI is not reachable within the simulation timeframe at any of these spending levels.")

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