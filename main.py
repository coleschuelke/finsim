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
    current_state = input_wizard()
    sim = Simulator(current_state, years=20)
    analyzer = Analyzer(sim)
    
    print("--- Forward Looking ---")
    # "With my current situation, if I made this purchase (50k boat)?"
    analyzer.purchase_impact_analysis(50000, is_equity=False)
    
    print("\n--- Backward Looking ---")
    # "What would it require to make probability of hitting $2M > 90%?"
    analyzer.required_savings_for_goal(2000000, 0.90)
    
    print("\n--- Sensitivity ---")
    analyzer.sensitivity_analysis()