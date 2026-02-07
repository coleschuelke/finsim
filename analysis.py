import numpy as np
import scipy.optimize as opt
from simulator import Simulator
import copy

class Analyzer:
    def __init__(self, base_simulator):
        self.sim = base_simulator

    # --- Paradigm 1: Forward Looking ---
    def purchase_impact_analysis(self, purchase_cost, is_equity=False):
        """
        Runs simulations with and without a purchase.
        If is_equity=True, converts cash to asset (Net Worth neutral initially).
        If is_equity=False, cash disappears (Expense).
        """
        # Scenario A: Do nothing
        res_a, fail_a = self.sim.run_monte_carlo(n_sims=100)
        
        # Scenario B: Purchase
        state_b = copy.deepcopy(self.sim.initial_state)
        state_b.cash -= purchase_cost
        if is_equity:
            # Add to investments (simplification for this snippet)
            from financial_state import Asset
            state_b.investments.append(Asset("New Purchase", purchase_cost, is_liquid=False))
            
        sim_b = Simulator(state_b, years=self.sim.years)
        res_b, fail_b = sim_b.run_monte_carlo(n_sims=100)
        
        print(f"Base Case Median NW: ${np.median(res_a):,.2f} (Fail Rate: {fail_a/100:.1%})")
        print(f"Purchase Case Median NW: ${np.median(res_b):,.2f} (Fail Rate: {fail_b/100:.1%})")

    # --- Paradigm 2: Backward Looking (Goal Seeking) ---
    def required_savings_for_goal(self, target_nw, probability_threshold=0.9):
        """
        Backward looking: Solves for required monthly savings reduction (or addition)
        to hit a Net Worth goal with X% probability.
        """
        print(f"Solving for inputs to achieve ${target_nw:,.0f} with {probability_threshold*100}% probability...")
        
        def objective(savings_delta):
            # Clone state
            temp_state = copy.deepcopy(self.sim.initial_state)
            # Adjust essential spend (inverse of savings)
            temp_state.essential_spend -= savings_delta 
            
            temp_sim = Simulator(temp_state, years=self.sim.years)
            results, _ = temp_sim.run_monte_carlo(n_sims=50) # Low N for speed in optimization loop
            
            # Calculate probability of hitting target
            success_count = sum(1 for r in results if r >= target_nw)
            prob = success_count / len(results)
            
            return prob - probability_threshold

        # Bisect method to find the zero crossing
        # Range: Reduce spend by 5k (save more) to Increase spend by 5k
        try:
            optimal_delta = opt.bisect(objective, -5000, 5000, xtol=100)
            print(f"Result: You need to change your monthly spend by ${-optimal_delta:,.2f}")
        except ValueError:
            print("Goal unreachable within constraints (+/- $5k/mo spend adjustment).")

    # --- Sensitivity Analysis ---
    def sensitivity_analysis(self):
        """
        Perturbs input factors to see which drives outcome variance most.
        """
        base_median = np.median(self.sim.run_monte_carlo(n_sims=50)[0])
        
        factors = ['inflation', 'mkt_return']
        impacts = {}
        
        # Access the market engine params inside the sim (conceptual)
        original_params = copy.deepcopy(self.sim.market.params)
        
        for factor in factors:
            # Shock up
            self.sim.market.params[factor]['mu'] *= 1.2
            high_res = np.median(self.sim.run_monte_carlo(n_sims=50)[0])
            
            # Shock down
            self.sim.market.params[factor]['mu'] = original_params[factor]['mu'] * 0.8
            low_res = np.median(self.sim.run_monte_carlo(n_sims=50)[0])
            
            # Reset
            self.sim.market.params[factor] = copy.deepcopy(original_params[factor])
            
            impacts[factor] = high_res - low_res
            
        print("Sensitivity (Net Worth Delta):", impacts)

    # --- Cost of Living Comparator ---
    def col_comparison(self, other_city_col_index, current_city_col_index=100):
        """
        Adjusts Spend but NOT Savings. 
        Most online calcs multiply your whole salary by the CoL index, which is wrong.
        If you move to a cheaper city, your savings rate effectively explodes.
        """
        ratio = other_city_col_index / current_city_col_index
        new_spend = self.sim.initial_state.essential_spend * ratio
        savings_delta = self.sim.initial_state.essential_spend - new_spend
        
        print(f"Moving to city with CoL {other_city_col_index}:")
        print(f"  Monthly Spend: ${new_spend:,.2f}")
        print(f"  Effective Monthly Savings Increase: ${savings_delta:,.2f}")