import numpy as np
import scipy.optimize as opt
from simulator import Simulator, ScheduledEvent
from financial_state import Asset
import copy

class Analyzer:
    def __init__(self, base_simulator):
        self.sim = base_simulator

    # --- Paradigm 1: Forward Looking (Time-Dependent) ---
    def purchase_impact_analysis(self, purchase_cost, purchase_year, is_equity=False):
        print(f"Analyzing purchase of ${purchase_cost:,.0f} in Year {purchase_year}...")

        def execute_purchase(state):
            state.cash -= purchase_cost
            if is_equity:
                state.investments.append(Asset(f"Purchase_Y{purchase_year}", purchase_cost, is_liquid=False))

        sim_a = Simulator(self.sim.initial_state, years=self.sim.years)
        
        event = ScheduledEvent(year=purchase_year, action=execute_purchase, description="Major Purchase")
        sim_b = Simulator(self.sim.initial_state, years=self.sim.years, scheduled_events=[event])

        results_a, fail_a = sim_a.run_monte_carlo(n_sims=100)
        results_b, fail_b = sim_b.run_monte_carlo(n_sims=100)

        median_nw_a = np.median([r['final_nw'] for r in results_a])
        median_nw_b = np.median([r['final_nw'] for r in results_b])
        
        print(f"  Baseline Median NW: ${median_nw_a:,.0f} (Fail Rate: {fail_a}%)")
        print(f"  Purchase Median NW: ${median_nw_b:,.0f} (Fail Rate: {fail_b}%)")
        print(f"  Delta: ${median_nw_b - median_nw_a:,.0f}")

    # --- Paradigm 2: Backward Looking (Multi-Goal) ---
    def optimize_for_goals(self, goals):
        print(f"Optimizing input inputs for {len(goals)} simultaneous goals...")

        def objective_function(x):
            # FIX: x is a scalar (float), not an array, when using minimize_scalar
            spend_delta = x
            
            # Temporary State
            temp_state = copy.deepcopy(self.sim.initial_state)
            temp_state.essential_spend += spend_delta
            
            temp_sim = Simulator(temp_state, years=self.sim.years)
            results, _ = temp_sim.run_monte_carlo(n_sims=40) 
            
            penalty = 0
            for goal in goals:
                target_year = goal['year']
                target_val = goal['target']
                metric = goal['metric']
                required_prob = goal['min_prob']
                
                successes = 0
                for r in results:
                    hist = r['history']
                    row = hist[hist['year'] == target_year]
                    if not row.empty:
                        val = row.iloc[0][metric]
                        if val >= target_val:
                            successes += 1
                
                actual_prob = successes / len(results)
                shortfall = max(0, required_prob - actual_prob)
                penalty += shortfall * 100 
                
            penalty += abs(spend_delta) * 0.0001
            return penalty

        # Optimization
        res = opt.minimize_scalar(objective_function, bounds=(-10000, 10000), method='bounded')
        
        required_change = res.x
        print(f"Optimization Complete.")
        if res.fun > 1.0: 
            print("  WARNING: Could not find a solution to meet all goals with high probability.")
            print(f"  Best effort: Change spend by ${required_change:,.2f}/mo")
        else:
            print(f"  Solution Found: Adjust monthly spend by ${required_change:,.2f}")
            if required_change < 0:
                print(f"  (You need to SAVE ${abs(required_change):,.2f} more per month)")
            else:
                print(f"  (You have wiggle room to SPEND ${required_change:,.2f} more per month)")

    def analyze_goal_probability(self, target_nw, years, variable_name='essential_spend', 
                               start=-2000, end=2000, steps=10):
        print(f"Sweeping {variable_name} to map probability of reaching ${target_nw:,.0f} in {years} years...")
        
        x_values = np.linspace(start, end, steps)
        probs = []
        original_spend = self.sim.initial_state.essential_spend
        
        for delta in x_values:
            self.sim.initial_state.essential_spend = original_spend + delta
            results, _ = self.sim.run_monte_carlo(n_sims=50)
            success_count = 0
            for r in results:
                if not r['history'].empty:
                    val = r['history'].iloc[-1]['Net Worth']
                    if val >= target_nw:
                        success_count += 1
            probs.append(success_count / 50)
            
        self.sim.initial_state.essential_spend = original_spend
        plot_x = -x_values 
        return plot_x, probs