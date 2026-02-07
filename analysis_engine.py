# analysis_engine.py
import numpy as np
import matplotlib.pyplot as plt
from simulation_core import Simulator
import copy

class Analyzer:
    def __init__(self, simulator):
        self.sim = simulator
        self.results = simulator.results
    
    def report_outlook(self):
        nw_end = self.results['net_worth'][-1, :]
        failures = np.sum(self.results['liquidity_failure'])
        total_runs = len(nw_end)
        
        print(f"--- Simulation Report ---")
        print(f"Success Rate: {100 * (1 - failures/total_runs):.1f}%")
        print(f"Median Net Worth: ${np.median(nw_end):,.2f}")
        print(f"5th Percentile (Pessimistic): ${np.percentile(nw_end, 5):,.2f}")
        print(f"95th Percentile (Optimistic): ${np.percentile(nw_end, 95):,.2f}")
        
    def backward_goal_seek(self, target_nw, target_probability=0.90):
        """
        Solves: What monthly savings (reduction in spend) is required to hit 
        target_nw with target_probability?
        """
        print(f"Running Goal Seek: Target ${target_nw:,.0f} with {target_probability*100}% certainty...")
        
        # Binary search on monthly_spend
        original_spend = self.sim.config['monthly_spend']
        low_spend = 0
        high_spend = original_spend * 2
        
        best_spend = None
        
        for _ in range(10): # 10 iterations of binary search
            mid_spend = (low_spend + high_spend) / 2
            
            # Update config and re-run
            # Note: In a real app, we'd optimize this to not re-init the whole physics engine
            test_config = copy.deepcopy(self.sim.config)
            test_config['monthly_spend'] = mid_spend
            
            test_sim = Simulator(self.sim.initial_portfolio, test_config)
            test_sim.run()
            
            final_nws = test_sim.results['net_worth'][-1, :]
            prob_success = np.sum(final_nws >= target_nw) / len(final_nws)
            
            if prob_success >= target_probability:
                best_spend = mid_spend
                low_spend = mid_spend # Can we spend more?
            else:
                high_spend = mid_spend # Need to spend less
                
        if best_spend:
            delta = original_spend - best_spend
            if delta > 0:
                print(f"Required Action: Reduce monthly spend by ${delta:,.2f} (New Limit: ${best_spend:,.2f})")
            else:
                print(f"You can increase spend by ${abs(delta):,.2f} and still meet the goal.")
        else:
            print("Goal unreachable even with 0 spend.")

    def sensitivity_analysis(self):
        # Determine correlation between final Net Worth and average economic factors per path
        nw = self.results['net_worth'][-1, :]
        
        factors = {
            'Market Return': np.mean(self.sim.scenarios['market_returns'], axis=0),
            'Inflation': np.mean(self.sim.scenarios['inflation'], axis=0),
            'Housing': np.mean(self.sim.scenarios['housing_growth'], axis=0)
        }
        
        print("\n--- Sensitivity Analysis (Correlation to Outcome) ---")
        for name, factor_data in factors.items():
            corr = np.corrcoef(nw, factor_data)[0, 1]
            print(f"{name}: {corr:.3f}")

    def plot_summary(self):
        nw = self.results['net_worth']
        median = np.median(nw, axis=1)
        p5 = np.percentile(nw, 5, axis=1)
        p95 = np.percentile(nw, 95, axis=1)
        
        plt.figure(figsize=(10, 6))
        months = np.arange(len(median))
        plt.plot(months, median, label='Median', color='blue')
        plt.fill_between(months, p5, p95, color='blue', alpha=0.1, label='5th-95th Percentile')
        plt.title("Net Worth Projection")
        plt.xlabel("Months")
        plt.ylabel("Net Worth ($)")
        plt.legend()
        plt.grid(True)
        plt.show()

    def compare_city_col(self, city1_spend, city2_spend, city2_inv_power_factor=1.0):
        """
        Compares CoL.
        city2_inv_power_factor: If city 2 has higher salaries, use this scalar.
        Crucial: Savings are not impacted by CoL, only spend is.
        """
        # This would wrap two simulation runs with different 'monthly_spend' and 'income' configs
        pass