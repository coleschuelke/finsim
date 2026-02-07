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
        """
        Simulates a purchase occurring in the future.
        """
        print(f"Analyzing purchase of ${purchase_cost:,.0f} in Year {purchase_year}...")

        # Define the action to take at purchase_year
        def execute_purchase(state):
            state.cash -= purchase_cost
            if is_equity:
                # Add asset (assume strictly illiquid initially, like a home or private equity)
                state.investments.append(Asset(f"Purchase_Y{purchase_year}", purchase_cost, is_liquid=False))
            # Note: If cash goes negative here, PolicyEngine.manage_liquidity 
            # will trigger in the next line of the simulator to sell stocks/cover debt.

        # Create simulators
        # Case A: No Event
        sim_a = Simulator(self.sim.initial_state, years=self.sim.years)
        
        # Case B: With Event
        event = ScheduledEvent(year=purchase_year, action=execute_purchase, description="Major Purchase")
        sim_b = Simulator(self.sim.initial_state, years=self.sim.years, scheduled_events=[event])

        # Run
        results_a, fail_a = sim_a.run_monte_carlo(n_sims=100)
        results_b, fail_b = sim_b.run_monte_carlo(n_sims=100)

        # Extract Medians
        median_nw_a = np.median([r['final_nw'] for r in results_a])
        median_nw_b = np.median([r['final_nw'] for r in results_b])
        
        print(f"  Baseline Median NW: ${median_nw_a:,.0f} (Fail Rate: {fail_a}%)")
        print(f"  Purchase Median NW: ${median_nw_b:,.0f} (Fail Rate: {fail_b}%)")
        print(f"  Delta: ${median_nw_b - median_nw_a:,.0f}")

    # --- Paradigm 2: Backward Looking (Multi-Goal) ---
    def optimize_for_goals(self, goals):
        """
        Solves for the required CHANGE in monthly spend to meet multiple probability goals.
        goals = [
            {'metric': 'Net Worth', 'target': 1e6, 'year': 10, 'min_prob': 0.90},
            {'metric': 'Cash', 'target': 50000, 'year': 5, 'min_prob': 0.95}
        ]
        """
        print(f"Optimizing input inputs for {len(goals)} simultaneous goals...")

        def objective_function(x):
            """
            x[0] = change in monthly essential spend (negative = saving more)
            Returns: Penalty score (0 = all goals met)
            """
            spend_delta = x[0]
            
            # Temporary State
            temp_state = copy.deepcopy(self.sim.initial_state)
            temp_state.essential_spend += spend_delta
            
            # Run fast simulation (fewer sims for optimization speed)
            temp_sim = Simulator(temp_state, years=self.sim.years)
            results, _ = temp_sim.run_monte_carlo(n_sims=40) 
            
            penalty = 0
            for goal in goals:
                # Filter results for the specific year
                target_year = goal['year']
                target_val = goal['target']
                metric = goal['metric'] # 'Net Worth' or 'Cash'
                required_prob = goal['min_prob']
                
                successes = 0
                for r in results:
                    # Get value at specific year from history
                    # history is a DataFrame, index is steps
                    hist = r['history']
                    row = hist[hist['year'] == target_year]
                    if not row.empty:
                        val = row.iloc[0][metric] # Take the first month of that year
                        if val >= target_val:
                            successes += 1
                
                actual_prob = successes / len(results)
                
                # Penalty: Square of the shortfall probability
                # If we need 90% and get 80%, penalty is high. If we get 95%, penalty is 0.
                shortfall = max(0, required_prob - actual_prob)
                penalty += shortfall * 100 # Weighting factor
                
            # Add a small regularization term to prefer smaller lifestyle changes
            penalty += abs(spend_delta) * 0.0001
            
            return penalty

        # Optimization: Minimize penalty
        # Bound: Can reduce spend by 10k or increase by 10k
        res = opt.minimize_scalar(objective_function, bounds=(-10000, 10000), method='bounded')
        
        required_change = res.x
        print(f"Optimization Complete.")
        if res.fun > 1.0: # Arbitrary threshold implying goals weren't fully met
            print("  WARNING: Could not find a solution to meet all goals with high probability.")
            print(f"  Best effort: Change spend by ${required_change:,.2f}/mo")
        else:
            print(f"  Solution Found: Adjust monthly spend by ${required_change:,.2f}")
            if required_change < 0:
                print(f"  (You need to SAVE ${abs(required_change):,.2f} more per month)")
            else:
                print(f"  (You have wiggle room to SPEND ${required_change:,.2f} more per month)")