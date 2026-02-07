# simulation_core.py
import numpy as np
import copy
from market_physics import MarketEngine
from financial_structs import Portfolio, Asset, Liability, RealProperty

class Policies:
    @staticmethod
    def standard_solvency(portfolio, cash_deficit):
        """
        Policy: If cash is negative, sell LIQUID investments to cover.
        Ignores RealProperty (illiquid).
        """
        # Filter for Financial Assets only (exclude Real Estate)
        liquid_assets = [
            a for a in portfolio.assets 
            if isinstance(a, Asset) and a.allocation > 0
        ]
        
        remaining_deficit = cash_deficit
        
        # Sort liquid assets by value to drain smaller accounts first? 
        # Or drain largest? Let's just iterate order.
        for asset in liquid_assets:
            if remaining_deficit <= 0:
                break
                
            if asset.value >= remaining_deficit:
                asset.value -= remaining_deficit
                remaining_deficit = 0
            else:
                remaining_deficit -= asset.value
                asset.value = 0
        
        return remaining_deficit # If > 0, simulation failed (bankruptcy)

class Simulator:
    def __init__(self, initial_portfolio, config):
        self.initial_portfolio = initial_portfolio
        self.config = config
        self.physics = MarketEngine(config['years'], config['num_paths'], config.get('seed', 42))
        self.scenarios = self.physics.generate_scenarios(config['market_params'])
        
        # Results storage
        self.results = {
            'net_worth': np.zeros((self.physics.months, self.physics.paths)),
            'liquidity_failure': np.zeros(self.physics.paths)
        }

    def run(self):
        months = self.physics.months
        paths = self.physics.paths
        
        # Pre-process scheduled events into a dict: {month_idx: [Event, ...]}
        event_schedule = self._map_events(months)

        for p in range(paths):
            # Deep copy portfolio for this path
            port = copy.deepcopy(self.initial_portfolio)
            
            # Path specific economic data
            path_mkt = self.scenarios['market_returns'][:, p] # Monthly returns
            path_inf = self.scenarios['inflation'][:, p]      # Annual Rate
            path_house = self.scenarios['housing_growth'][:, p] # Monthly Rate
            path_sal = self.scenarios['salary_growth'][:, p]    # Monthly Rate
            path_shock = self.scenarios['unforseen_shocks'][:, p]
            path_rates = self.scenarios['interest_rates'][:, p] # Annual Rate
            
            failed = False
            
            # --- FIX: Convert Annual Inflation to Monthly for Expense compounding ---
            monthly_inflation_factors = 1 + (path_inf / 12.0)
            cumulative_inflation_arr = np.cumprod(monthly_inflation_factors)

            for t in range(months):
                if failed:
                    # If failed, we flatline at 0 to indicate ruin
                    self.results['net_worth'][t, p] = 0
                    continue

                # 1. Process Income (Salary Growth)
                monthly_income = 0
                for inc in port.incomes:
                    # Apply salary growth
                    inc['amount'] *= (1 + path_sal[t])
                    monthly_income += inc['amount']

                # 2. Process Scheduled Events
                if t in event_schedule:
                    for event in event_schedule[t]:
                        self._apply_event(port, event, path_house[t])

                # 3. Process Expenses
                # Adjust Essential Spend for Inflation using corrected array
                current_monthly_spend = self.config['monthly_spend'] * cumulative_inflation_arr[t]
                
                # Housing Maintenance
                maint_costs = sum(a.get_maintenance_cost() for a in port.assets if isinstance(a, RealProperty))
                
                # Liability Payments
                debt_service = 0
                for liab in port.liabilities:
                    interest, principal = liab.step(variable_rate_adjuster=0) 
                    debt_service += liab.payment 
                
                total_outflow = current_monthly_spend + maint_costs + debt_service
                
                # Unforseen Shock?
                if path_shock[t] == 1:
                    total_outflow += 5000 * cumulative_inflation_arr[t]

                # 4. Net Cash Flow Logic
                net_cash = monthly_income * (1 - self.config['tax_rate']) - total_outflow
                
                # 5. Asset Growth & Rebalancing
                for asset in port.assets:
                    if isinstance(asset, RealProperty):
                        asset.grow(path_house[t])
                    elif isinstance(asset, Asset):
                        # Grow financial assets
                        # path_mkt is already monthly. path_rates is Annual (grow method expects Annual for risk-free)
                        asset.grow(path_mkt[t], path_rates[t])
                
                # 6. Cash Management (Deficit/Surplus)
                cash_asset = port.assets[0] 
                
                if net_cash >= 0:
                    cash_asset.value += net_cash
                else:
                    # Deficit: draw from cash first
                    cash_asset.value += net_cash 
                    if cash_asset.value < 0:
                        deficit = abs(cash_asset.value)
                        cash_asset.value = 0
                        # Trigger Solvency Policy
                        remaining_deficit = Policies.standard_solvency(port, deficit)
                        if remaining_deficit > 100: # Threshold for failure ($100 tolerance)
                            failed = True
                            self.results['liquidity_failure'][p] = 1

                # Record
                self.results['net_worth'][t, p] = port.net_worth

    def _map_events(self, total_months):
        schedule = {}
        for event in self.config.get('events', []):
            m_idx = event['month']
            if m_idx < total_months:
                if m_idx not in schedule: schedule[m_idx] = []
                schedule[m_idx].append(event)
        return schedule

    def _apply_event(self, portfolio, event, current_housing_factor):
        if event['type'] == 'purchase_asset':
            cost = event['value']
            down_payment = event.get('down_payment', cost)
            loan_amount = cost - down_payment
            
            # Pay Downpayment
            portfolio.assets[0].value -= down_payment
            
            # Add Asset
            if event.get('is_real_estate', False):
                new_asset = RealProperty(event['name'], cost)
            else:
                new_asset = Asset(event['name'], cost, allocation_to_market=0) 
            
            portfolio.add_asset(new_asset)
            
            if loan_amount > 0:
                new_liab = Liability(f"Loan-{event['name']}", loan_amount, 
                                     event['rate'], event['monthly_payment'], 
                                     is_mortgage=event.get('is_real_estate', False))
                portfolio.add_liability(new_liab)
                
        elif event['type'] == 'param_change':
            if event['param'] == 'monthly_spend':
                self.config['monthly_spend'] = event['value']