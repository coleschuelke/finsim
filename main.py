# main_interface.py
from financial_structs import Portfolio, Asset, Liability, RealProperty
from simulation_core import Simulator
from analysis_engine import Analyzer

def main():
    # 1. Define Current Financial State
    my_portfolio = Portfolio()
    
    # Assets
    my_portfolio.add_asset(Asset("Cash Savings", 50000, allocation_to_market=0.0))
    my_portfolio.add_asset(Asset("401k/Brokerage", 150000, allocation_to_market=0.9))
    
    # Real Estate (Equity handled implicitly via Value - Debt)
    my_portfolio.add_asset(RealProperty("Primary Home", 500000))
    
    # Liabilities
    my_portfolio.add_liability(Liability("Mortgage", 400000, 0.045, 2026, is_mortgage=True))
    my_portfolio.add_liability(Liability("Student Loan", 20000, 0.06, 300))
    
    # Income
    cole_annual = 120000
    jenna_annual = 140000
    
    my_portfolio.incomes.append({
        'name': 'Cole Salary', 
        'amount': cole_annual / 12.0  # Monthly
    })
    
    my_portfolio.incomes.append({
        'name': 'Jenna Salary', 
        'amount': jenna_annual / 12.0 # Monthly
    })

    # 2. Simulation Configuration
    config = {
        'years': 15,
        'num_paths': 500, # Monte Carlo iterations
        'seed': 12345,    # Consistent seeding
        
        'tax_rate': 0.28,
        'monthly_spend': 6000, # Essential spend EXCLUDING housing (mortgage handled in logic)
        'initial_rent': 1200,
        
        # Economic Assumptions
        'base_inflation': 0.03,
        'base_interest_rate': 0.04,
        'market_params': {
            'expected_mkt_return': 0.08,
            'mkt_vol': 0.15,
            'base_inflation': 0.03,
            'base_interest_rate': 0.04,
            'merit_increase': 0.01 # Salary growth above inflation
        },
        
        # Scheduled Events
        'events': [
            {
                'month': 36, # In 3 years
                'type': 'purchase_asset',
                'name': 'Luxury Car',
                'value': 60000,
                'down_payment': 10000,
                'rate': 0.07,
                'monthly_payment': 900,
                'is_real_estate': False
            },
            {
                'month': 60,
                'type': 'param_change',
                'param': 'monthly_spend',
                'value': 7000 # Lifestyle creep
            }
        ]
    }

    # 3. Run Forward Analysis
    print("Running Forward Simulation...")
    sim = Simulator(my_portfolio, config)
    sim.run()
    
    analyzer = Analyzer(sim)
    analyzer.report_outlook()
    analyzer.sensitivity_analysis()
    
    # 4. Run Backward Analysis (Goal Seeking)
    # Goal: $2M Net Worth in 10 years
    analyzer.backward_goal_seek(target_nw=1_500_000, target_probability=0.80)

    # 5. Visuals
    analyzer.plot_summary() # Uncomment to view plot

if __name__ == "__main__":
    main()