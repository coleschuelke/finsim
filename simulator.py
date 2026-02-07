import pandas as pd
import copy
from market_engine import MarketEngine
from policies import PolicyEngine

class Simulator:
    def __init__(self, initial_state, years=30):
        self.initial_state = initial_state
        self.years = years
        self.market = MarketEngine(years)
    
    def step(self, state, market_data):
        dt = 1/12 # Monthly steps
        
        # 1. Update Market Vars
        inflation = market_data['inflation']
        mkt_ret = market_data['mkt_return']
        salary_growth = market_data['salary_growth']
        housing_growth = market_data['housing_growth']
        
        # 2. Income & Spend
        monthly_income = sum(s/12 for s in state.salaries) * (1 + salary_growth * dt)
        state.salaries = [s * (1 + salary_growth * dt) for s in state.salaries]
        
        state.essential_spend *= (1 + inflation * dt)
        state.cash += monthly_income - state.essential_spend - market_data['unforeseen_expense']
        
        # 3. Debt Service
        for debt in state.liabilities:
            interest = debt.balance * (debt.interest_rate or market_data['interest_rate']) * dt
            payment = debt.monthly_payment
            
            # If payment covers more than balance
            if payment > debt.balance + interest:
                payment = debt.balance + interest
            
            state.cash -= payment
            debt.balance += interest - payment
            if debt.balance < 0: debt.balance = 0
            
        # 4. Asset Growth
        for asset in state.investments:
            # Simple geometric brownian approximation
            asset.value *= (1 + mkt_ret * dt * asset.growth_beta)
            
        for prop in state.real_estate:
            prop.value *= (1 + housing_growth * dt)
            
        # 5. Policies
        PolicyEngine.manage_liquidity(state)
        PolicyEngine.check_failure(state)
        
    def run_single_simulation(self):
        state = copy.deepcopy(self.initial_state)
        market_paths = self.market.generate_scenario()
        steps = self.market.steps
        
        history = []
        
        for t in range(steps):
            if state.failed: break
            
            # Slice market data for this step
            current_market = {k: v[t] for k, v in market_paths.items()}
            self.step(state, current_market)
            
            rec = state.snapshot()
            rec['step'] = t
            history.append(rec)
            
        return pd.DataFrame(history), state.failed, state.failure_reason

    def run_monte_carlo(self, n_sims=500):
        results = []
        failures = 0
        
        for _ in range(n_sims):
            df, failed, reason = self.run_single_simulation()
            final_nw = df['Net Worth'].iloc[-1] if not df.empty else 0
            results.append(final_nw)
            if failed: failures += 1
            
        return results, failures