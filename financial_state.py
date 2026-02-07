from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Liability:
    name: str
    balance: float
    interest_rate: float # Fixed, or if None, floats with market
    monthly_payment: float

@dataclass
class Asset:
    name: str
    value: float
    is_liquid: bool
    growth_beta: float = 1.0 # Multiplier on market return (e.g., 1.0 for SP500, 0.0 for cash)

@dataclass
class RealEstate(Asset):
    mortgage: Liability = None
    
    def equity(self):
        debt = self.mortgage.balance if self.mortgage else 0
        return self.value - debt

class FinancialState:
    def __init__(self, cash, investments, salaries, liabilities, essential_spend, real_estate=None):
        self.cash = cash
        self.investments = investments # Dict of Assets
        self.salaries = salaries # List of annual amounts (two-income support)
        self.liabilities = liabilities # List of Liabilities
        self.essential_spend = essential_spend # Monthly
        self.real_estate = real_estate # List of RealEstate objects
        
        self.failed = False
        self.failure_reason = ""
        self.history = []

    def net_worth(self):
        assets = self.cash + sum(a.value for a in self.investments)
        real_estate_equity = sum(h.equity() for h in self.real_estate)
        debts = sum(l.balance for l in self.liabilities if l not in [h.mortgage for h in self.real_estate if h.mortgage])
        return assets + real_estate_equity - debts

    def snapshot(self):
        return {
            "Net Worth": self.net_worth(),
            "Cash": self.cash,
            "Investments": sum(a.value for a in self.investments),
            "Debt": sum(l.balance for l in self.liabilities)
        }