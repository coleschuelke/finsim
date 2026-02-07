import unittest
import numpy as np
import pandas as pd
from simulator import Simulator, ScheduledEvent
from financial_state import FinancialState, Asset, Liability, RealEstate
from market_engine import MarketEngine

class MockMarketEngine(MarketEngine):
    def __init__(self, years, inflation=0.0, mkt_return=0.0, steps_per_year=12):
        super().__init__(years, steps_per_year=steps_per_year)
        # FORCE steps to be integer to avoid any float rounding issues
        self.steps = int(years * steps_per_year)
        self.fixed_inflation = inflation
        self.fixed_mkt = mkt_return

    def generate_scenario(self):
        keys = list(self.params.keys())
        paths = {k: np.zeros(self.steps) for k in keys}
        paths['unforeseen_expense'] = np.zeros(self.steps)
        paths['inflation'][:] = self.fixed_inflation
        paths['mkt_return'][:] = self.fixed_mkt
        paths['salary_growth'][:] = 0.0
        paths['housing_growth'][:] = 0.0
        paths['interest_rate'][:] = 0.0
        return paths

class TestFinancialSimulator(unittest.TestCase):

    def setUp(self):
        self.cash = 10000
        self.stocks = Asset("Stocks", 50000, is_liquid=True)
        self.house = RealEstate("Home", 300000, is_liquid=False, 
                                mortgage=Liability("Mortgage", 200000, 0.0, 1000))
        self.state = FinancialState(
            cash=self.cash,
            investments=[self.stocks],
            salaries=[60000],
            liabilities=[self.house.mortgage],
            essential_spend=3000,
            real_estate=[self.house]
        )

    def test_01_basic_accounting_identity(self):
        """Income (5k) - Spend (3k) - Mortgage (1k) = +1k/mo. 12 months = +12k NW."""
        sim = Simulator(self.state, years=1)
        sim.market = MockMarketEngine(years=1, steps_per_year=12)
        _, failed, _, final_state = sim.run_single_simulation()
        
        self.assertFalse(failed)
        
        # We check Net Worth because PolicyEngine might convert Stock->Cash
        # Start NW: 10k(cash) + 50k(stock) + 100k(home equity) = 160k
        # Change: +12k (from surplus) + 12k (principal paydown) = +24k
        # Note: Principal paydown is a NW transfer (Cash down, Liability down), 
        # so purely operational surplus +1k/mo is +12k Cash.
        # Wait: The mortgage payment (1k) is 100% principal in Mock (0% rate).
        # So: Cash -1k, Debt -1k. NW change = 0 for the payment part.
        # Income (5k) - Spend (3k) = +2k Cash surplus.
        # Total NW change = +24k.
        
        initial_nw = 160000
        expected_nw = initial_nw + 24000 
        self.assertAlmostEqual(final_state.net_worth(), expected_nw, delta=1.0)

    def test_02_liquidity_crisis_policy(self):
        """High Wealth, Zero Cash. Should sell stocks to survive 1 month."""
        self.state.cash = -5000 
        self.state.essential_spend = 10000 
        
        # Run for only 1 month (1/12 years) to test immediate reaction
        # without running out of total assets
        sim = Simulator(self.state, years=1/12)
        sim.market = MockMarketEngine(years=1/12, steps_per_year=12)
        _, failed, _, final_state = sim.run_single_simulation()
        
        self.assertFalse(failed) 
        # Stocks should have decreased (sold to pay bills)
        final_stocks = final_state.investments[0].value
        self.assertLess(final_stocks, 50000)
        # Cash should be positive 
        self.assertGreater(final_state.cash, 0)

    def test_04_inflation_impact(self):
        sim = Simulator(self.state, years=1)
        sim.market = MockMarketEngine(years=1, inflation=0.10, steps_per_year=12)
        _, _, _, final_state = sim.run_single_simulation()
        self.assertGreater(final_state.essential_spend, 3000)

    def test_05_scheduled_event(self):
        """Buy a boat in Year 1."""
        def buy_boat(state):
            state.cash -= 50000

        event = ScheduledEvent(year=1, action=buy_boat, description="Boat")
        
        sim = Simulator(self.state, years=2, scheduled_events=[event])
        sim.market = MockMarketEngine(years=2, steps_per_year=12)
        
        results, _, _, _ = sim.run_single_simulation()
        
        # Event happens at t=12 (Start of Year 2/Month 13). 
        # We compare t=11 (Pre-Event) vs t=12 (Post-Event).
        nw_pre = results.iloc[11]['Net Worth']
        nw_post = results.iloc[12]['Net Worth']
        
        # Drop should be approx 50k.
        # (There is also 1 month of income +2k in step 12, so net drop ~48k)
        self.assertLess(nw_post, nw_pre - 40000)

    def test_06_real_estate_equity(self):
        sim = Simulator(self.state, years=1)
        sim.market = MockMarketEngine(years=1, steps_per_year=12)
        _, _, _, final_state = sim.run_single_simulation()
        
        initial_equity = 100000
        expected_equity = initial_equity + 12000
        self.assertAlmostEqual(final_state.real_estate[0].equity(), expected_equity, places=0)

if __name__ == '__main__':
    unittest.main()