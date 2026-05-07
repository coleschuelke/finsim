# simulation_core.py
import numpy as np
import copy
from market_physics import MarketEngine
from financial_structs import Portfolio, Asset, Liability, RealProperty
from taxes import TaxEngine

class Policies:
    @staticmethod
    def standard_solvency(portfolio, cash_deficit):
        """
        Policy: If cash is negative, sell LIQUID investments to cover.
        """
        # NEW: Added the a.is_liquid check
        liquid_assets = [
            a for a in portfolio.assets 
            if isinstance(a, Asset) and a.allocation > 0 and getattr(a, 'is_liquid', True)
        ]
        
        remaining_deficit = cash_deficit
        
        # Simple policy: Sell first available liquid asset.
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

        self.tax_engine = TaxEngine()
        
        # In simulation_core.py -> Simulator.__init__
        self.results = {
            'net_worth': np.zeros((self.physics.months, self.physics.paths)),
            'liquidity_failure': np.zeros(self.physics.paths),
            # NEW: Telemetry arrays
            'liquid_assets': np.zeros((self.physics.months, self.physics.paths)),
            'cash_balance': np.zeros((self.physics.months, self.physics.paths)),
            'cf_gross': np.zeros((self.physics.months, self.physics.paths)),
            'cf_tax': np.zeros((self.physics.months, self.physics.paths)),
            'cf_spend': np.zeros((self.physics.months, self.physics.paths)),
            'cf_debt': np.zeros((self.physics.months, self.physics.paths)),
            'cf_invested': np.zeros((self.physics.months, self.physics.paths))
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
            
            # --- Inflation Pre-calculation ---
            # Convert Annual Inflation to Monthly for Expense compounding
            monthly_inflation_factors = 1 + (path_inf / 12.0)
            cumulative_inflation_arr = np.cumprod(monthly_inflation_factors)

            # --- Initialize Rent from Config ---
            current_rent_base = self.config.get('initial_rent', 0.0)

            for t in range(months):
                if failed:
                    self.results['net_worth'][t, p] = 0
                    continue

                # 1. Process Income, Taxes, and 401k Contributions
                monthly_net_income = 0
                total_pre_tax_investments = 0
                monthly_gross_income = 0 # NEW
                
                for inc in port.incomes:
                    # Apply salary growth
                    inc['amount'] *= (1 + path_sal[t])
                    
                    monthly_gross_income += inc['amount'] # NEW
                    
                    # Calculate net income and 401k contribution per stream
                    net, pre_tax = self.tax_engine.calculate_monthly_net(
                        inc['amount'], 
                        inc.get('annual_401k_contribution', 0.0) 
                    )
                    
                    monthly_net_income += net
                    total_pre_tax_investments += pre_tax

                # NEW: Calculate actual taxes paid
                taxes_paid = monthly_gross_income - monthly_net_income - total_pre_tax_investments

                # Route the aggregated 401k contributions directly to the brokerage asset
                if total_pre_tax_investments > 0:
                    brokerage = next((a for a in port.assets if "401k" in a.name), None)
                    if brokerage:
                        brokerage.value += total_pre_tax_investments

                # 2. Process Scheduled Events
                if t in event_schedule:
                    for event in event_schedule[t]:
                        current_rent_base = self._apply_event(port, event, path_house[t], current_rent_base)

                # 3. Process Expenses
                
                # A. Essential Spend (Food, Utilities) - Grows with Inflation
                current_monthly_spend = self.config['monthly_spend'] * cumulative_inflation_arr[t]
                
                # B. Rent - Grows with Inflation (if base is > 0)
                if current_rent_base > 0:
                    current_rent_payment = current_rent_base * cumulative_inflation_arr[t]
                else:
                    current_rent_payment = 0
                
                # C. Housing Maintenance (for owned properties)
                maint_costs = sum(a.get_maintenance_cost() for a in port.assets if isinstance(a, RealProperty))
                
                # D. Liability Payments (Mortgages, Loans)
                debt_service = 0
                for liab in port.liabilities:
                    interest, principal = liab.step(variable_rate_adjuster=0)
                    debt_service += (interest + principal)
                
                # Total Outflow
                total_outflow = current_monthly_spend + current_rent_payment + maint_costs + debt_service
                
                # Unforseen Shock?
                if path_shock[t] == 1:
                    total_outflow += 5000 * cumulative_inflation_arr[t]

                # 4. Net Cash Flow Logic
                # The flat tax_rate config is gone; we use the calculated monthly_net_income
                net_cash = monthly_net_income - total_outflow
                
                # 5. Asset Growth & Rebalancing
                for asset in port.assets:
                    if isinstance(asset, RealProperty):
                        asset.grow(path_house[t])
                    elif isinstance(asset, Asset):
                        # Grow financial assets
                        asset.grow(path_mkt[t], path_rates[t])
                
                # 6. Cash Management (Deficit/Surplus)
                # BUG FIX: Use centralized method instead of inline logic
                cash_asset = port.get_liquid_cash_asset()
                
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

                # Record (End of monthly loop)
                if failed:
                    self.results['net_worth'][t, p] = 0
                    self.results['liquid_assets'][t, p] = 0
                    self.results['cash_balance'][t, p] = 0
                else:
                    self.results['net_worth'][t, p] = port.net_worth
                    
                    cash_obj = port.get_liquid_cash_asset()
                    self.results['cash_balance'][t, p] = cash_obj.value
                    
                    # NEW: Only sum Assets where is_liquid is True
                    self.results['liquid_assets'][t, p] = sum(
                        a.value for a in port.assets 
                        if isinstance(a, Asset) and getattr(a, 'is_liquid', True)
                    )
                    
                    self.results['cf_gross'][t, p] = monthly_gross_income
                    self.results['cf_tax'][t, p] = taxes_paid
                    self.results['cf_spend'][t, p] = total_outflow - debt_service # Isolate living spend
                    self.results['cf_debt'][t, p] = debt_service
                    
                    # Total capital put to work (Net cash added to savings + 401k contributions)
                    self.results['cf_invested'][t, p] = net_cash + total_pre_tax_investments

    def _map_events(self, total_months):
        schedule = {}
        for event in self.config.get('events', []):
            start_m_idx = event['month']
            freq = event.get('frequency', 0)
            
            if freq > 0:
                # Recurring event
                curr_m = start_m_idx
                while curr_m < total_months:
                    if curr_m not in schedule: schedule[curr_m] = []
                    schedule[curr_m].append(event)
                    curr_m += freq
            else:
                # One-time event
                if start_m_idx < total_months:
                    if start_m_idx not in schedule: schedule[start_m_idx] = []
                    schedule[start_m_idx].append(event)
                    
        return schedule

    def _apply_event(self, portfolio, event, current_housing_factor, current_rent):
        """
        Applies a financial event to the portfolio.
        Returns: The updated base rent.
        """
        new_rent = current_rent

        if event['type'] == 'purchase_asset':
            cost = event['value']
            down_payment = event.get('down_payment', cost)
            loan_amount = cost - down_payment
            
            cash_asset = portfolio.get_liquid_cash_asset()
            cash_asset.value -= down_payment
            
            if event.get('retains_value', True):
                if event.get('is_real_estate', False):
                    new_asset = RealProperty(event['name'], cost)
                    if event.get('is_primary_home', False):
                        new_rent = 0
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
            elif event['param'] == 'rent':
                new_rent = event['value']
                
        elif event['type'] == 'change_income':
            target_name = event['income_name']
            for inc in portfolio.incomes:
                if inc['name'] == target_name:
                    inc['amount'] = event['new_salary'] / 12.0
                    if 'new_401k' in event:
                        inc['annual_401k_contribution'] = event['new_401k']
                    break
                    
        elif event['type'] == 'rsu_vest':
            # Simulate sell-to-cover for taxes
            gross_vest = event['value']
            net_vest = gross_vest * (1 - event.get('tax_withholding', 0.22))
            
            # Find the stock asset bucket, or create it if it doesn't exist
            target_asset_name = event.get('asset_name', 'Company Stock')
            stock_asset = next((a for a in portfolio.assets if a.name == target_asset_name), None)
            
            if stock_asset:
                stock_asset.value += net_vest
            else:
                # Defaults to liquid, 100% market allocation (equity)
                new_stock = Asset(target_asset_name, net_vest, allocation_to_market=1.0, is_liquid=True)
                portfolio.add_asset(new_stock)
        
        return new_rent