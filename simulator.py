import pandas as pd
import copy
from dataclasses import dataclass
from typing import Callable, List
from market_engine import MarketEngine
from policies import PolicyEngine

@dataclass
class ScheduledEvent:
    year: int
    action: Callable[[object], None]  # Function taking 'state' as input
    description: str

class Simulator:
    def __init__(self, initial_state, years=30, scheduled_events: List[ScheduledEvent] = None):
        self.initial_state = initial_state
        self.years = years
        self.market = MarketEngine(years)
        self.scheduled_events = scheduled_events if scheduled_events else []
    
    def step(self, state, market_data, current_year):
        dt = 1/12 # Monthly steps
        
        # ... [Previous Market/Income/Debt Logic remains identical] ...
        # (Assuming the logic from previous turn is here)
        
        # 1. Update Market Vars
        inflation = market_data['inflation']
        mkt_ret = market_data['mkt_return']
        salary_growth = market_data['salary_growth']
        housing_growth = market_data['housing_growth']
        
        monthly_income = sum(s/12 for s in state.salaries) * (1 + salary_growth * dt)
        state.salaries = [s * (1 + salary_growth * dt) for s in state.salaries]
        
        state.essential_spend *= (1 + inflation * dt)
        state.cash += monthly_income - state.essential_spend - market_data['unforeseen_expense']
        
        # Debt Service
        for debt in state.liabilities:
            interest = debt.balance * (debt.interest_rate or market_data['interest_rate']) * dt
            payment = debt.monthly_payment
            if payment > debt.balance + interest: payment = debt.balance + interest
            state.cash -= payment
            debt.balance += interest - payment
            if debt.balance < 0: debt.balance = 0
            
        # Asset Growth
        for asset in state.investments:
            asset.value *= (1 + mkt_ret * dt * asset.growth_beta)
        for prop in state.real_estate:
            prop.value *= (1 + housing_growth * dt)
            
        # 2. Check for Scheduled Events (Triggered once at the start of the target year)
        # We assume this step runs monthly, so check if we are in month 1 of the target year
        # (This logic requires the main loop to pass current_step, here simplified to 'current_year' check)
        pass 

    def run_single_simulation(self):
        state = copy.deepcopy(self.initial_state)
        market_paths = self.market.generate_scenario()
        steps = self.market.steps
        
        history = []
        
        for t in range(steps):
            if state.failed: break
            
            # Check for events
            current_year = t // 12
            current_month = t % 12
            if current_month == 0: # Check events at start of year
                for event in self.scheduled_events:
                    if event.year == current_year:
                        # Execute the custom action on the state
                        event.action(state)

            current_market = {k: v[t] for k, v in market_paths.items()}
            self.step(state, current_market, current_year)
            
            # Policies run AFTER events to handle immediate liquidity needs
            PolicyEngine.manage_liquidity(state)
            PolicyEngine.check_failure(state)
            
            rec = state.snapshot()
            rec['step'] = t
            rec['year'] = current_year
            history.append(rec)
            
        return pd.DataFrame(history), state.failed, state.failure_reason

    def run_monte_carlo(self, n_sims=500):
        results = []
        failures = 0
        
        for _ in range(n_sims):
            df, failed, reason = self.run_single_simulation()
            # Store the full dataframe for complex analysis, or just key metrics
            results.append({'final_nw': df['Net Worth'].iloc[-1] if not df.empty else 0, 'history': df})
            if failed: failures += 1
            
        return results, failures