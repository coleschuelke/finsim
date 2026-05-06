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
        
    def get_probability_sweep(self, target_nw, steps=15):
        """
        Calculates the probability of reaching target_nw for a range of 
        monthly spending values.
        """
        base_spend = self.sim.config['monthly_spend']
        # Sweep from $0 to 2x current spend
        spend_range = np.linspace(0, base_spend * 2.0, steps)
        probabilities = []
        
        # Store original config to restore later if needed (though we use deepcopy below)
        
        for spend_val in spend_range:
            # 1. Create temporary config with new spend
            test_config = copy.deepcopy(self.sim.config)
            test_config['monthly_spend'] = spend_val
            
            # 2. Run Simulation (Fast run)
            # We reuse the initial portfolio structure
            test_sim = Simulator(self.sim.initial_portfolio, test_config)
            test_sim.run()
            
            # 3. Calculate Success %
            final_nws = test_sim.results['net_worth'][-1, :]
            success_count = np.sum(final_nws >= target_nw)
            prob = (success_count / len(final_nws)) * 100
            probabilities.append(prob)
            
        return spend_range, probabilities

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
        years = months / 12
        plt.plot(years, median, label='Median', color='blue')
        plt.fill_between(years, p5, p95, color='blue', alpha=0.1, label='5th-95th Percentile')
        plt.title("Net Worth Projection")
        plt.xlabel("Years")
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

    def opportunity_cost_delta(self, hypothetical_event, evaluation_year=10):
        """
        A/B tests a specific financial event (e.g. buying a vehicle) against the baseline.
        Returns the exact dollar delta in Median Net Worth and Liquid Assets at year X.
        """
        # Create alternate universe config
        alt_config = copy.deepcopy(self.sim.config)
        alt_config['events'].append(hypothetical_event)
        
        # Run alternate simulation
        alt_sim = Simulator(self.sim.initial_portfolio, alt_config)
        alt_sim.run()
        
        target_month = min(int(evaluation_year * 12) - 1, self.sim.physics.months - 1)
        
        # Extract Medians
        base_nw = np.median(self.results['net_worth'][target_month, :])
        base_liq = np.median(self.results['liquid_assets'][target_month, :])
        
        alt_nw = np.median(alt_sim.results['net_worth'][target_month, :])
        alt_liq = np.median(alt_sim.results['liquid_assets'][target_month, :])
        
        delta_nw = base_nw - alt_nw
        delta_liq = base_liq - alt_liq
        
        return {
            'baseline_nw': base_nw,
            'alternate_nw': alt_nw,
            'net_worth_cost': delta_nw,
            'liquidity_cost': delta_liq
        }

    def compare_city_col(self, alt_spend, alt_rent, alt_salary_scalars=None):
        """
        Compares baseline trajectory against a temporary or permanent relocation.
        Example: Evaluating an Austin baseline against a move to Hawthorne, CA.
        alt_salary_scalars: list of multipliers corresponding to the portfolio incomes.
        """
        alt_config = copy.deepcopy(self.sim.config)
        alt_config['monthly_spend'] = alt_spend
        alt_config['initial_rent'] = alt_rent
        
        alt_port = copy.deepcopy(self.sim.initial_portfolio)
        
        if alt_salary_scalars and len(alt_salary_scalars) == len(alt_port.incomes):
            for i, inc in enumerate(alt_port.incomes):
                inc['amount'] *= alt_salary_scalars[i]
                
        alt_sim = Simulator(alt_port, alt_config)
        alt_sim.run()
        
        base_end_nw = self.results['net_worth'][-1, :]
        alt_end_nw = alt_sim.results['net_worth'][-1, :]
        
        return {
            'base_median_nw': np.median(base_end_nw),
            'alt_median_nw': np.median(alt_end_nw),
            'base_success_rate': 100 * (1 - np.mean(self.results['liquidity_failure'])),
            'alt_success_rate': 100 * (1 - np.mean(alt_sim.results['liquidity_failure']))
        }

    def optimize_purchase_timing(self, event_template, target_confidence=0.85):
        """
        Solves for the earliest month an event (like a $40k Toyota 4Runner cash purchase) 
        can occur while maintaining a target solvency confidence.
        """
        total_months = self.sim.physics.months
        
        for test_month in range(12, total_months, 6): # Step by 6 months to save compute
            test_config = copy.deepcopy(self.sim.config)
            test_event = copy.deepcopy(event_template)
            test_event['month'] = test_month
            test_config['events'].append(test_event)
            
            test_sim = Simulator(self.sim.initial_portfolio, test_config)
            test_sim.run()
            
            success_rate = 1 - np.mean(test_sim.results['liquidity_failure'])
            
            if success_rate >= target_confidence:
                return test_month
                
        return None # Target confidence unreachable within simulation timeframe

    def calculate_fi_crossover(self, swr=0.04):
        """
        Identifies the month where the Safe Withdrawal Rate of liquid investments 
        exceeds essential monthly spend (Financial Independence threshold).
        Returns the probability of reaching FI by year.
        """
        months = self.sim.physics.months
        paths = self.sim.physics.paths
        
        crossover_months = np.full(paths, -1) # -1 indicates FI not reached
        
        for p in range(paths):
            for t in range(months):
                # Calculate required monthly spend for this path/month (Spend + Rent)
                inf_factor = 1 + (self.sim.scenarios['inflation'][t, p] / 12.0)
                # Note: Approximation using current t inflation. 
                # For exact matching, track cumulative inflation in the main loop and store it.
                current_spend = self.sim.results['cf_spend'][t, p] 
                
                # Calculate monthly yield from liquid assets at SWR
                liquid_assets = self.sim.results['liquid_assets'][t, p]
                monthly_safe_yield = (liquid_assets * swr) / 12.0
                
                if monthly_safe_yield >= current_spend and current_spend > 0:
                    crossover_months[p] = t
                    break
                    
        # Calculate cumulative probability over time
        years = np.arange(1, (months // 12) + 1)
        fi_prob = []
        
        for y in years:
            target_m = y * 12
            reached_count = np.sum((crossover_months >= 0) & (crossover_months <= target_m))
            fi_prob.append((reached_count / paths) * 100)
            
        return years, fi_prob, crossover_months