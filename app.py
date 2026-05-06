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

# Helper for payment calculation
def calculate_pmt(principal, annual_rate, years):
    if principal <= 0 or years <= 0:
        return 0.0
    
    r = annual_rate / 12.0 # Monthly rate
    n = years * 12.0       # Total months
    
    if r == 0:
        return principal / n
    
    # Standard Amortization Formula
    return principal * (r * (1 + r)**n) / ((1 + r)**n - 1)

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
        
        # NEW: Split investments into liquid and illiquid
        brokerage = st.number_input("Taxable Brokerage (Liquid)", value=50000)
        retirement_401k = st.number_input("401k / IRA (Illiquid)", value=100000)
        
        stock_allocation = st.slider("Stock Allocation %", 0.0, 1.0, 0.9)
        
        st.divider()
        st.subheader("Real Estate")
        home_value = st.number_input("Current Home Value (0 if renting)", value=0)
        
    with col2:
        st.subheader("Liabilities")
        
        # --- Mortgage Section (Auto-Calc) ---
        mortgage_bal = st.number_input("Mortgage Balance", value=0, step=1000)
        mortgage_rate = st.number_input("Mortgage Rate (%)", value=4.5, step=0.1) / 100
        mortgage_years = st.number_input("Remaining Term (Years)", value=30, step=1)
        
        # Auto-calculate and display
        mortgage_pmt = calculate_pmt(mortgage_bal, mortgage_rate, mortgage_years)
        if mortgage_bal > 0:
            st.metric("Estimated Mortgage Payment", f"${mortgage_pmt:,.2f}")
        
        st.divider()
        
        # --- Other Loans (Dynamic Table) ---
        st.subheader("Other Loans")
        st.caption("Add multiple loans below. Payment is auto-calculated.")
        
        # Default Data Structure
        default_data = pd.DataFrame(
            [{"Name": "Student Loan", "Balance": 20000.0, "Rate (%)": 6.0, "Years": 10.0}],
        )
        
        # Editable Table
        other_loans_df = st.data_editor(
            default_data, 
            num_rows="dynamic",
            column_config={
                "Name": st.column_config.TextColumn("Loan Name", required=True),
                "Balance": st.column_config.NumberColumn("Balance ($)", min_value=0, step=1000, format="$%d"),
                "Rate (%)": st.column_config.NumberColumn("Rate (%)", min_value=0, max_value=100, step=0.1, format="%.1f%%"),
                "Years": st.column_config.NumberColumn("Term (Years)", min_value=0.1, max_value=50, step=1)
            },
            use_container_width=True
        )
        
        # Optional: Show Total Monthly Debt Service from these loans
        total_other_pmt = 0
        for _, row in other_loans_df.iterrows():
            total_other_pmt += calculate_pmt(row["Balance"], row["Rate (%)"]/100, row["Years"])
            
        if total_other_pmt > 0:
            st.metric("Total Other Loan Payments", f"${total_other_pmt:,.2f}")

    with col3:
        st.subheader("Income & Spend")
        st.info("Taxes are auto-calculated using progressive single-filer brackets.")
        
        st.markdown("**Person 1**")
        annual_income_1 = st.number_input("Annual Salary 1", value=120000, step=5000)
        pretax_401k_1 = st.number_input("Annual 401k Contrib 1 ($)", value=23000, step=500, max_value=23000)
        
        st.markdown("**Person 2**")
        annual_income_2 = st.number_input("Annual Salary 2", value=140000, step=5000)
        pretax_401k_2 = st.number_input("Annual 401k Contrib 2 ($)", value=23000, step=500, max_value=23000)
        
        st.divider()
        monthly_spend = st.number_input("Monthly Essential Spend (Food/Life)", value=4000, step=500)
        current_rent = st.number_input("Current Monthly Rent", value=2200, step=100)

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
            
            # --- NEW: Toggle for Sunk Cost / Depreciation ---
            ev_retains_value = st.checkbox("Asset Retains Value (Counts towards Net Worth)", value=True, 
                                           help="Uncheck this for cars or toys to immediately write off the purchase price as a sunk expense.")
            
            # Loan details
            c1, c2 = st.columns(2)
            with c1:
                ev_loan_rate = st.number_input("Loan Rate (%)", value=6.0, key="ev_loan_rate") / 100
            with c2:
                ev_loan_term_years = st.number_input("Loan Term (Years)", value=30, key="ev_loan_term")
            
            calc_pmt = 0.0
            if ev_cost > ev_down and ev_loan_rate > 0:
                n = ev_loan_term_years * 12
                r = ev_loan_rate / 12
                loan = ev_cost - ev_down
                if loan > 0:
                    calc_pmt = loan * (r * (1 + r)**n) / ((1 + r)**n - 1)
            
            st.metric("Calculated Monthly Payment", f"${calc_pmt:,.2f}")

            if st.button("Add Purchase Event"):
                new_ev = {
                    'month': ev_month_idx,
                    'display_year': ev_year,
                    'type': 'purchase_asset',
                    'name': ev_name,
                    'value': ev_cost,
                    'down_payment': ev_down,
                    'rate': ev_loan_rate,
                    'monthly_payment': calc_pmt,
                    'is_real_estate': ev_is_re,
                    'is_primary_home': ev_is_primary,
                    'retains_value': ev_retains_value # --- NEW: Append flag to dict ---
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
    pf.add_asset(Asset("Cash", cash, allocation_to_market=0.0, is_liquid=True))
    
    # NEW: Construct the split assets with correct liquidity flags
    if brokerage > 0:
        pf.add_asset(Asset("Brokerage", brokerage, allocation_to_market=stock_allocation, is_liquid=True))
    if retirement_401k > 0:
        pf.add_asset(Asset("401k", retirement_401k, allocation_to_market=stock_allocation, is_liquid=False))
        
    # Liabilities
    # 1. Mortgage (Calculated above)
    if mortgage_bal > 0:
        # Note: mortgage_pmt is now calculated in the UI section
        pf.add_liability(Liability("Mortgage", mortgage_bal, mortgage_rate, mortgage_pmt, is_mortgage=True))
    
    # 2. Other Loans (From DataFrame)
    if not other_loans_df.empty:
        for index, row in other_loans_df.iterrows():
            l_name = row["Name"]
            l_bal = row["Balance"]
            l_rate = row["Rate (%)"] / 100.0
            l_years = row["Years"]
            
            if l_bal > 0:
                # Auto-calc payment for simulation
                l_pmt = calculate_pmt(l_bal, l_rate, l_years)
                pf.add_liability(Liability(l_name, l_bal, l_rate, l_pmt))
        
    # Income
    pf.incomes.append({
        'name': 'Salary 1', 
        'amount': annual_income_1 / 12.0,
        'annual_401k_contribution': pretax_401k_1
    })
    
    if annual_income_2 > 0:
        pf.incomes.append({
            'name': 'Salary 2', 
            'amount': annual_income_2 / 12.0,
            'annual_401k_contribution': pretax_401k_2
        })
        
    # 2. Build Config Dict
    config = {
        'years': years,
        'num_paths': num_paths,
        'seed': int(seed),
        # Removed the flat 'tax_rate' key entirely
        'monthly_spend': monthly_spend,
        'initial_rent': current_rent,
        'base_inflation': base_inflation, 
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

    st.subheader("Deep Dive Analytics")
    tab_liquid, tab_drawdown, tab_cashflow = st.tabs([
        "Liquidity vs Total Net Worth", 
        "Stress Test (Cash Drawdown)", 
        "Cash Flow Waterfall"
    ])
    
    with tab_liquid:
        st.info("Tracks total Net Worth against Liquid Assets (Cash + Brokerage). Wide gaps indicate wealth is locked in illiquid assets like real estate.")
        liq = results['liquid_assets']
        p50_liq = np.median(liq, axis=1)
        
        fig_liq = go.Figure()
        fig_liq.add_trace(go.Scatter(x=years, y=p50, mode='lines', line=dict(color='blue', width=2), name='Median Total Net Worth'))
        fig_liq.add_trace(go.Scatter(x=years, y=p50_liq, mode='lines', line=dict(color='green', width=2), name='Median Liquid Assets'))
        
        fig_liq.update_layout(xaxis_title="Years", yaxis_title="USD ($)", height=450, hovermode="x unified")
        st.plotly_chart(fig_liq, use_container_width=True)

    with tab_drawdown:
        st.info("Shows the absolute lowest cash balance hit during each successful simulation path. If many paths cluster near $0, your cash buffer is too thin.")
        
        # Filter for successful paths only, then find the minimum cash balance each path ever hit
        successful_paths = results['liquidity_failure'] == 0
        if np.any(successful_paths):
            cash_history_success = results['cash_balance'][:, successful_paths]
            min_cash_per_path = np.min(cash_history_success, axis=0)
            
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Histogram(
                x=min_cash_per_path, 
                nbinsx=50,
                marker_color='orange',
                name='Paths'
            ))
            
            # Add a vertical line indicating $0 bankruptcy threshold
            fig_hist.add_vline(x=0, line_width=2, line_dash="dash", line_color="red", annotation_text="Bankruptcy Limit")
            
            fig_hist.update_layout(
                title="Minimum Cash Balance Reached (Successful Paths)",
                xaxis_title="Lowest Cash Balance ($)",
                yaxis_title="Number of Paths",
                height=450
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.error("No successful paths to analyze. 100% failure rate.")

    with tab_cashflow:
        st.info("The average breakdown of where your gross income goes over time.")
        
        # Calculate mean across all paths to get the 'expected' cash flow
        cf_tax = np.mean(results['cf_tax'], axis=1)
        cf_spend = np.mean(results['cf_spend'], axis=1)
        cf_debt = np.mean(results['cf_debt'], axis=1)
        cf_invested = np.mean(results['cf_invested'], axis=1)
        
        fig_cf = go.Figure()
        
        # Stacked Area Chart (Order matters for stacking: bottom to top)
        fig_cf.add_trace(go.Scatter(x=years, y=cf_spend, mode='lines', stackgroup='one', name='Living Expenses', fillcolor='rgba(255, 165, 0, 0.7)', line=dict(width=0)))
        fig_cf.add_trace(go.Scatter(x=years, y=cf_debt, mode='lines', stackgroup='one', name='Debt Service', fillcolor='rgba(255, 99, 71, 0.7)', line=dict(width=0)))
        fig_cf.add_trace(go.Scatter(x=years, y=cf_tax, mode='lines', stackgroup='one', name='Taxes', fillcolor='rgba(169, 169, 169, 0.7)', line=dict(width=0)))
        fig_cf.add_trace(go.Scatter(x=years, y=cf_invested, mode='lines', stackgroup='one', name='Saved & Invested', fillcolor='rgba(60, 179, 113, 0.7)', line=dict(width=0)))
        
        fig_cf.update_layout(
            title="Monthly Cash Flow Allocation (Average)",
            xaxis_title="Years",
            yaxis_title="Monthly Outflow ($)",
            height=450,
            hovermode="x unified"
        )
        st.plotly_chart(fig_cf, use_container_width=True)

# 3. Goal Seek (in dedicated tab or below)
with tab_goals:
    st.subheader("Trade-Off Analysis: Spending vs. Success")
    st.info("See how increasing or decreasing your monthly spend affects the chance of hitting your Net Worth goal.")
    
    target_amount = st.number_input("Target Net Worth ($)", value=2_000_000, step=100_000)
    
    if st.button("Generate Trade-Off Curve"):
        pf_gs, config_gs = build_config_and_portfolio()
        
        # Initialize simulator purely to pass to Analyzer
        sim_gs = Simulator(pf_gs, config_gs) 
        analyzer = Analyzer(sim_gs)
        
        with st.spinner("Running simulations for various spending levels..."):
            # Run the sweep
            spends, probs = analyzer.get_probability_sweep(target_amount, steps=20)
            
            # Plot with Plotly
            fig_tradeoff = go.Figure()
            
            fig_tradeoff.add_trace(go.Scatter(
                x=spends, 
                y=probs, 
                mode='lines+markers',
                name='Success Probability',
                line=dict(color='green', width=3),
                marker=dict(size=8)
            ))
            
            # Add a vertical line for Current Spend
            current_spend = config_gs['monthly_spend']
            fig_tradeoff.add_vline(x=current_spend, line_width=1, line_dash="dash", annotation_text="Current Spend")
            
            fig_tradeoff.update_layout(
                title=f"Probability of Reaching ${target_amount:,.0f}",
                xaxis_title="Monthly Spend ($)",
                yaxis_title="Probability of Success (%)",
                yaxis_range=[0, 105], # 0 to 100%
                height=500
            )
            
            st.plotly_chart(fig_tradeoff, use_container_width=True)
            
            # Interpretation
            # Find the spend that gives ~80% success (simple approximation)
            over_80 = [s for s, p in zip(spends, probs) if p >= 80]
            if over_80:
                max_safe_spend = max(over_80)
                st.success(f"To have at least **80% confidence**, keep monthly spend below **${max_safe_spend:,.0f}**.")
            else:
                st.error("Even with $0 spend, 80% confidence is not reachable in this timeframe.")