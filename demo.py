import numpy as np
import copy
from financial_state import FinancialState, Asset, Liability, RealEstate
from simulator import Simulator, ScheduledEvent
from analysis import Analyzer
from visualizer import Visualizer

def input_wizard():
    print("--- 1. Setting up Financial State ---")
    # Liabilities
    mortgage = Liability("Home Mortgage", balance=400000, interest_rate=0.04, monthly_payment=2200)
    car_loan = Liability("Tesla", balance=30000, interest_rate=0.05, monthly_payment=600)
    
    # Assets
    home = RealEstate("Main House", value=600000, is_liquid=False, mortgage=mortgage)
    stocks = Asset("Vanguard Index", value=150000, is_liquid=True, growth_beta=1.0)
    bonds = Asset("Bonds", value=50000, is_liquid=True, growth_beta=0.4)
    
    # State
    state = FinancialState(
        cash=25000,
        investments=[stocks, bonds],
        salaries=[140000, 95000], # Two income household
        liabilities=[mortgage, car_loan],
        essential_spend=7000,     # Monthly burn
        real_estate=[home]
    )
    print(f"Initial Net Worth: ${state.net_worth():,.0f}")
    return state

def run_test_drive():
    # A. Setup
    initial_state = input_wizard()
    sim = Simulator(initial_state, years=25)
    analyzer = Analyzer(sim)
    
    print("\n--- 2. Forward Looking Analysis (The 'What If') ---")
    # Scenario: Can we afford an $80k vacation home down payment in Year 5?
    # is_equity=True means we convert Cash -> Asset, we don't just burn it.
    analyzer.purchase_impact_analysis(
        purchase_cost=80000, 
        purchase_year=5, 
        is_equity=True
    )
    
    print("\n--- 3. Backward Looking Optimization (The 'How To') ---")
    # Goal: $3M Net Worth in 20 years (80% confidence)
    # Goal: $100k Liquid Cash in 5 years (90% confidence)
    goals = [
        {'metric': 'Net Worth', 'target': 3000000, 'year': 20, 'min_prob': 0.80},
        {'metric': 'Cash', 'target': 100000, 'year': 5, 'min_prob': 0.90}
    ]
    analyzer.optimize_for_goals(goals)

    print("\n--- 4. Generating Visualization Assets ---")
    # Re-run simulations to capture data for plotting
    
    # 4a. Baseline Cone
    print("Generating: Baseline_Net_Worth_Projection.png")
    results_base, _ = sim.run_monte_carlo(n_sims=200)
    Visualizer.plot_monte_carlo_paths(results_base, "Baseline Net Worth Projection")
    
    # 4b. Scenario Comparison (Purchase Decision)
    print("Generating: Scenario_Comparison.png")
    def buy_vacation_home(state):
        state.cash -= 80000
        # Add illiquid asset
        state.real_estate.append(RealEstate("Vacation Home", 80000, is_liquid=False))
        
    event = ScheduledEvent(year=5, action=buy_vacation_home, description="Buy Vacation Home")
    sim_purchase = Simulator(initial_state, years=25, scheduled_events=[event])
    results_purchase, _ = sim_purchase.run_monte_carlo(n_sims=200)
    
    Visualizer.plot_scenario_comparison(results_base, results_purchase, "Baseline", "With Vacation Home")
    
    # 4c. Sensitivity Analysis (Tornado Plot)
    print("Generating: Sensitivity_Analysis.png")
    factors = ['inflation', 'mkt_return', 'salary_growth']
    impacts = {}
    
    base_median = np.median([r['final_nw'] for r in results_base])
    
    for f in factors:
        orig = sim.market.params[f]['mu']
        
        # Shock Up 20%
        sim.market.params[f]['mu'] = orig * 1.2
        res_up, _ = sim.run_monte_carlo(50)
        
        # Shock Down 20%
        sim.market.params[f]['mu'] = orig * 0.8
        res_down, _ = sim.run_monte_carlo(50)
        
        # Calculate Delta
        med_up = np.median([r['final_nw'] for r in res_up])
        med_down = np.median([r['final_nw'] for r in res_down])
        impacts[f] = med_up - med_down
        
        # Reset
        sim.market.params[f]['mu'] = orig
        
    Visualizer.plot_sensitivity(impacts)
    
    # 4d. Probability S-Curve
    print("Generating: Probability_Curve.png")
    # "How much extra savings do I need for a 90% chance of $3M?"
    savings_deltas, probabilities = analyzer.analyze_goal_probability(
        target_nw=3000000, 
        years=20, 
        variable_name='essential_spend',
        start=-3000, # Save 3k more
        end=1000,    # Spend 1k more
        steps=15
    )
    Visualizer.plot_probability_curve(
        savings_deltas, 
        probabilities, 
        x_label="Additional Monthly Savings ($)", 
        title="Probability of Reaching $3M Net Worth"
    )

    print("\n--- Test Drive Complete. Check your folder for PNG files. ---")

if __name__ == "__main__":
    run_test_drive()