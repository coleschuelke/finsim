# financial_structs.py
import numpy as np

class FinancialEntity:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.history = []

    def snapshot(self):
        self.history.append(self.value)

class Asset(FinancialEntity):
    def __init__(self, name, value, allocation_to_market=1.0):
        super().__init__(name, value)
        self.allocation = allocation_to_market # 0.0 to 1.0 (Cash to Stocks)

    def grow(self, market_return, risk_free_rate):
        # Weighted growth based on allocation
        rate = (market_return * self.allocation) + (risk_free_rate/12 * (1 - self.allocation))
        self.value *= (1 + rate)

class RealProperty(FinancialEntity):
    def __init__(self, name, value, maintenance_cost_annual=0.01):
        super().__init__(name, value)
        self.maintenance_rate = maintenance_cost_annual

    def grow(self, housing_growth_rate):
        self.value *= (1 + housing_growth_rate)
        
    def get_maintenance_cost(self):
        return (self.value * self.maintenance_rate) / 12.0

class Liability(FinancialEntity):
    def __init__(self, name, principal, interest_rate, monthly_payment, is_mortgage=False):
        super().__init__(name, principal)
        self.rate = interest_rate
        self.payment = monthly_payment
        self.is_mortgage = is_mortgage
    
    def step(self, variable_rate_adjuster=0):
        # Allow for variable rates (floating rate debt)
        effective_rate = self.rate + variable_rate_adjuster
        interest = self.value * (effective_rate / 12.0)
        
        # Amortization
        principal_pay = self.payment - interest
        if principal_pay > self.value:
            principal_pay = self.value
            
        self.value -= principal_pay
        return interest, principal_pay # Return expenses

class Portfolio:
    def __init__(self):
        self.assets = []
        self.liabilities = []
        self.incomes = []
        
    def add_asset(self, asset): self.assets.append(asset)
    def add_liability(self, liab): self.liabilities.append(liab)
    
    @property
    def total_assets(self): return sum(a.value for a in self.assets)
    
    @property
    def total_liabilities(self): return sum(l.value for l in self.liabilities)
    
    @property
    def net_worth(self): return self.total_assets - self.total_liabilities

    def snapshot_all(self):
        for item in self.assets + self.liabilities:
            item.snapshot()