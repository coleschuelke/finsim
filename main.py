from financial_state import FinancialState, Asset, Liability, RealEstate
from simulator import Simulator
from analysis import Analyzer

def input_wizard():
    # Hardcoded for demo, but this is where the CLI/API inputs go
    
    # 1. Liabilities
    mortgage = Liability("Home Mortgage", 400000, 0.035, 2500)
    car_loan = Liability("Tesla", 30000, 0.05, 600)
    
    # 2. Assets
    home = RealEstate("Main House", 600000, is_liquid=False, mortgage=mortgage)
    stocks = Asset("Vanguard", 150000, is_liquid=True)
    
    # 3. State
    state = FinancialState(
        cash=20000,
        investments=[stocks],
        salaries=[120000, 95000], # Two income
        liabilities=[mortgage, car_loan],
        essential_spend=6000, # Monthly
        real_estate=[home]
    )
    
    return state

if __name__ == "__main__":
    # Setup
    initial = input_wizard() # Defined in previous response
    sim = Simulator(initial, years=25)
    analyzer = Analyzer(sim)
    
    # 1. Forward Looking: Future Purchase
    # "Can I afford a $80k vacation home in 5 years?"
    # Note: is_equity=True means net worth doesn't drop immediately, just liquidity
    analyzer.purchase_impact_analysis(
        purchase_cost=80000, 
        purchase_year=5, 
        is_equity=True
    )
    
    print("-" * 30)
    
    # 2. Backward Looking: Multi-Goal Optimization
    # "I want $1M Net Worth in 15 years (90% prob) AND 
    #  I need $100k liquid Cash in 5 years for a business (80% prob)."
    goals = [
        {'metric': 'Net Worth', 'target': 1000000, 'year': 15, 'min_prob': 0.90},
        {'metric': 'Cash', 'target': 100000, 'year': 5, 'min_prob': 0.80}
    ]
    
    analyzer.optimize_for_goals(goals)