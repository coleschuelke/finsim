import unittest
import numpy as np
import copy
from simulation_core import Simulator, Policies
from financial_structs import Portfolio, Asset, Liability, RealProperty

class TestFinancialSimulator(unittest.TestCase):
    
    def setUp(self):
        """
        Base configuration for all tests. 
        We use 1 path and 0 volatility to make tests deterministic.
        """
        self.base_config = {
            'years': 2, # Short duration for testing
            'num_paths': 1,
            'seed': 42,
            'tax_rate': 0.0, # Simplify math
            'monthly_spend': 1000,
            'initial_rent': 0,
            'base_inflation': 0.0,
            'base_interest_rate': 0.0,
            'market_params': {
                'expected_mkt_return': 0.0,
                'mkt_vol': 0.0, # NO NOISE
                'base_inflation': 0.0,
                'base_interest_rate': 0.0,
                'merit_increase': 0.0
            },
            'events': []
        }

        # Base Portfolio
        self.port = Portfolio()
        self.port.add_asset(Asset("Cash", 10000, allocation_to_market=0.0))
        # Zero income to test pure expense drain
        self.port.incomes = [{'name': 'Salary', 'amount': 0}] 

    def _force_scenarios(self, sim, market_ret=0.0, inflation=0.0, housing=0.0):
        """
        Helper to overwrite stochastic scenarios with flat constants.
        """
        shape = (sim.physics.months, sim.physics.paths)
        sim.scenarios['market_returns'] = np.full(shape, market_ret)
        sim.scenarios['inflation'] = np.full(shape, inflation) 
        sim.scenarios['housing_growth'] = np.full(shape, housing)
        sim.scenarios['salary_growth'] = np.full(shape, 0.0)
        sim.scenarios['unforseen_shocks'] = np.zeros(shape)
        sim.scenarios['interest_rates'] = np.zeros(shape)

    def test_basic_cash_drain(self):
        sim = Simulator(self.port, self.base_config)
        self._force_scenarios(sim)
        sim.run()
        
        # Start: 10,000. 5 months of $1000 spend.
        expected_nw = 10000 - (5 * 1000)
        actual_nw = sim.results['net_worth'][4, 0] # Index 4 is Month 5
        self.assertEqual(actual_nw, expected_nw)

    def test_inflation_compounding(self):
        self.base_config['monthly_spend'] = 1000
        sim = Simulator(self.port, self.base_config)
        
        # Force 12% annual inflation
        self._force_scenarios(sim, inflation=0.12)
        sim.run()
        
        # Month 0 spend: 1000 * (1 + 0.12/12) = 1010
        nw_0 = sim.results['net_worth'][0, 0]
        delta = 10000 - nw_0
        self.assertAlmostEqual(delta, 1010.0, places=1)

    def test_rent_stops_after_purchase(self):
        """
        Verify that paying rent stops exactly when 'is_primary_home' event triggers.
        """
        self.base_config['monthly_spend'] = 0 # Remove noise
        self.base_config['initial_rent'] = 1000
        
        # Buy house at Month 2 (Index 2)
        self.base_config['events'] = [{
            'month': 2,
            'type': 'purchase_asset',
            'name': 'Home',
            'value': 100000,
            'down_payment': 0, 
            'rate': 0.0,
            'monthly_payment': 0, 
            'is_real_estate': True,
            'is_primary_home': True
        }]
        
        sim = Simulator(self.port, self.base_config)
        self._force_scenarios(sim)
        
        # ** FIX: Mock RealProperty to have 0 maintenance for this test **
        # We cheat slightly by monkey-patching the class locally or just accepting the delta.
        # Better way: Let's adjust our expectation to include maintenance.
        # Maintenance = 1% of 100k / 12 = 83.333...
        
        sim.run()
        nw = sim.results['net_worth'][:, 0]
        
        # Month 0: Rent 1000. NW = 9000
        self.assertEqual(nw[0], 9000)
        # Month 1: Rent 1000. NW = 8000
        self.assertEqual(nw[1], 8000)
        
        # Month 2 (Event): Buy House. Rent stops. 
        # But Maintenance Starts! ($83.33)
        # NW = 8000 (Prev) - 0 (Rent) - 83.33 (Maint) = 7916.67
        
        expected_nw_m2 = 8000 - (100000 * 0.01 / 12)
        self.assertAlmostEqual(nw[2], expected_nw_m2, places=1, msg="Rent should stop, replaced by Maintenance")

    def test_liquidity_crisis(self):
        """
        Scenario: Cash runs out.
        1. Should sell Liquid Assets (Stocks).
        2. Should Fail if only Illiquid remain.
        """
        pf = Portfolio()
        pf.add_asset(Asset("Cash", 0, allocation_to_market=0.0))
        pf.add_asset(Asset("Stock", 2000, allocation_to_market=1.0))
        
        # FIX: Set maintenance to 0.0 so we don't lose $4.17/mo to upkeep
        pf.add_asset(RealProperty("House", 5000, maintenance_cost_annual=0.0))
        
        pf.incomes = [{'name': 'Job', 'amount': 0}]
        
        self.base_config['monthly_spend'] = 1000
        
        sim = Simulator(pf, self.base_config)
        self._force_scenarios(sim)
        sim.run()
        
        # Month 0: Spend 1000. Cash deficit covered by Stock.
        # Result: Net Worth should be valid (Original 7000 - 1000 = 6000)
        self.assertEqual(sim.results['net_worth'][0, 0], 6000, "Should survive Month 0 by selling stock")
        
        # Month 1: Spend 1000. Remaining Stock (1000) sold.
        # Result: Net Worth = 5000 (Just the house left).
        self.assertEqual(sim.results['net_worth'][1, 0], 5000, "Should survive Month 1 by draining stock")
        
        # Month 2: Spend 1000. No Cash, No Stock.
        # Result: Crash. Simulator sets NW to 0 upon failure.
        self.assertEqual(sim.results['net_worth'][2, 0], 0, "Should fail in Month 2")
        
        # Check failure flag
        self.assertEqual(sim.results['liquidity_failure'][0], 1)

    def test_investment_growth(self):
        self.base_config['monthly_spend'] = 0
        pf = Portfolio()
        pf.add_asset(Asset("Stock", 100, allocation_to_market=1.0))
        pf.incomes = [] 
        
        sim = Simulator(pf, self.base_config)
        self._force_scenarios(sim, market_ret=0.10) 
        sim.run()
        
        # Month 0: 100 * 1.10 = 110
        # Month 1: 110 * 1.10 = 121
        final_nw = sim.results['net_worth'][1, 0] 
        self.assertAlmostEqual(final_nw, 121.0)

    def test_mortgage_paydown(self):
        liab = Liability("Mortgage", 100000, 0.12, 2000)
        interest, principal = liab.step()
        self.assertEqual(interest, 1000)
        self.assertEqual(principal, 1000)
        self.assertEqual(liab.value, 99000)

    def test_spend_increase_event(self):
        self.base_config['monthly_spend'] = 1000
        self.base_config['events'] = [{
            'month': 1,
            'type': 'param_change',
            'param': 'monthly_spend',
            'value': 2000
        }]
        
        sim = Simulator(self.port, self.base_config)
        self._force_scenarios(sim)
        sim.run()
        
        nw = sim.results['net_worth'][:, 0]
        self.assertEqual(nw[0], 9000)
        self.assertEqual(nw[1], 7000)

    def test_salary_growth(self):
        self.port.incomes = [{'name': 'Job', 'amount': 1000}]
        self.base_config['monthly_spend'] = 0
        
        sim = Simulator(self.port, self.base_config)
        self._force_scenarios(sim)
        shape = (sim.physics.months, sim.physics.paths)
        sim.scenarios['salary_growth'] = np.full(shape, 0.10)
        
        sim.run()
        
        # Month 0: Income 1100. NW = 11100
        self.assertEqual(sim.results['net_worth'][0, 0], 11100)

if __name__ == '__main__':
    unittest.main()