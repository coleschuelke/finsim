class TaxEngine:
    def __init__(self, brackets=None, standard_deduction=14600):
        # Default to Single Filer brackets (upper_bound, marginal_rate)
        self.brackets = brackets or [
            (11600, 0.10),
            (47150, 0.12),
            (100525, 0.22),
            (191950, 0.24),
            (243725, 0.32),
            (609350, 0.35),
            (float('inf'), 0.37)
        ]
        self.standard_deduction = standard_deduction
        
    def calculate_monthly_net(self, monthly_gross, annual_pre_tax_contribution=0.0):
            """
            Takes gross monthly income and a fixed annual 401k contribution amount.
            Returns the net monthly cash (post-tax, post-401k) and the 401k contribution amount.
            """
            # 1. Annualize values
            annual_gross = monthly_gross * 12
            
            # 2. Safety Cap: Ensure 401k contribution doesn't exceed gross income
            actual_annual_401k = min(annual_pre_tax_contribution, annual_gross)
            
            # 3. Calculate Taxable Income (Gross - 401k - Standard Deduction)
            taxable_income = max(0, annual_gross - actual_annual_401k - self.standard_deduction)
            
            # 4. Apply Progressive Brackets
            annual_tax = 0.0
            previous_bound = 0.0
            
            for upper_bound, rate in self.brackets:
                if taxable_income > previous_bound:
                    taxable_amount_in_bracket = min(taxable_income, upper_bound) - previous_bound
                    annual_tax += taxable_amount_in_bracket * rate
                    previous_bound = upper_bound
                else:
                    break
                    
            # 5. Convert back to monthly flows
            monthly_tax = annual_tax / 12.0
            monthly_pre_tax = actual_annual_401k / 12.0
            monthly_net = monthly_gross - monthly_tax - monthly_pre_tax
            
            return monthly_net, monthly_pre_tax