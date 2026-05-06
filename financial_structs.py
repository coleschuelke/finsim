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
    # NEW: Added is_liquid flag
    def __init__(self, name, value, allocation_to_market=1.0, is_liquid=True):
        super().__init__(name, value)
        self.allocation = allocation_to_market 
        self.is_liquid = is_liquid 

    def grow(self, market_return, risk_free_rate):
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
        # BUG FIX: Prevent zombie debts from calculating negative interest
        if self.value <= 0:
            self.value = 0.0
            return 0.0, 0.0

        effective_rate = self.rate + variable_rate_adjuster
        interest = self.value * (effective_rate / 12.0)
        
        # Calculate what we *want* to pay
        intended_payment = self.payment
        
        # Calculate total required to clear debt
        total_due = self.value + interest
        
        # Cap payment
        actual_payment = min(intended_payment, total_due)
        
        # Derive principal reduction (will be negative if payment < interest, causing balance to grow)
        principal_pay = actual_payment - interest
        
        # Update Balance
        self.value -= principal_pay
        
        return interest, principal_pay

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

    # BUG FIX: Centralized cash retrieval logic
    def get_liquid_cash_asset(self):
        cash_asset = next((a for a in self.assets if isinstance(a, Asset) and a.allocation == 0), None)
        if cash_asset is None:
            raise ValueError("Portfolio must contain at least one Cash asset (Asset with allocation=0).")
        return cash_asset

    def snapshot_all(self):
        for item in self.assets + self.liabilities:
            item.snapshot()