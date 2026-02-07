import pandas as pd
import copy
from dataclasses import dataclass
from typing import Callable, List
from market_engine import MarketEngine
from policies import PolicyEngine

@dataclass
class ScheduledEvent:
    year: int
    action: Callable[[object], None]
    description: str

class Simulator:
    def __init__(self, initial_state, years=30, scheduled_events: List[ScheduledEvent] = None):
        self.initial_state = initial_state
        self.years = years
        self.market = MarketEngine(years, steps_per_year=12)
        self.scheduled_events = scheduled_events if scheduled_events else []
    
    def step(self, state, market_data):
        dt = 1/12
        inflation = market_data['inflation']
        mkt_ret = market_data['mkt_return']
        salary_growth = market_data['salary_growth']
        housing_growth = market_data['housing_growth']
        
        # Income & Spend
        monthly_income = sum(s/12 for s in state.salaries) * (1 + salary_growth * dt)
        state.salaries = [s * (1 + salary_growth * dt) for s in state.salaries]
        
        state.essential_spend *= (1 + inflation * dt)
        state.cash += monthly_income - state.essential_spend - market_data['unforeseen_expense']
        
        # Debt
        for debt in state.liabilities:
            rate = debt.interest_rate if debt.interest_rate is not None else market_data['interest_rate']
            interest = debt.balance * rate * dt
            payment = debt.monthly_payment
            if payment > debt.balance + interest: payment = debt.balance + interest
            state.cash -= payment
            debt.balance += interest - payment
            if debt.balance < 0: debt.balance = 0
            
        # Assets
        for asset in state.investments:
            asset.value *= (1 + mkt_ret * dt * asset.growth_beta)
        for prop in state.real_estate:
            prop.value *= (1 + housing_growth * dt)

    def run_single_simulation(self):
        state = copy.deepcopy(self.initial_state)
        market_paths = self.market.generate_scenario()
        steps = self.market.steps
        
        history = []
        
        for t in range(steps):
            if state.failed: break
            
            # Events check (Year Start)
            current_year = t // 12
            if t % 12 == 0:
                for event in self.scheduled_events:
                    if event.year == current_year:
                        event.action(state)

            current_market = {k: v[t] for k, v in market_paths.items()}
            self.step(state, current_market)
            
            PolicyEngine.manage_liquidity(state)
            PolicyEngine.check_failure(state)
            
            rec = state.snapshot()
            rec['step'] = t
            rec['year'] = t / 12
            history.append(rec)
            
        return pd.DataFrame(history), state.failed, state.failure_reason, state

    def run_monte_carlo(self, n_sims=500):
        results = []
        failures = 0
        for _ in range(n_sims):
            df, failed, _, _ = self.run_single_simulation()
            nw = df['Net Worth'].iloc[-1] if not df.empty else 0
            results.append({'final_nw': nw, 'history': df})
            if failed: failures += 1
        return results, failures