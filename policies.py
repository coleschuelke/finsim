class PolicyEngine:
    @staticmethod
    def manage_liquidity(state):
        """
        Policy 1: Liquidity Logic
        If cash is negative, sell liquid assets.
        If cash is excessive (> 6 months expenses), invest surplus.
        """
        monthly_burn = state.essential_spend + sum(l.monthly_payment for l in state.liabilities)
        min_cash = 3 * monthly_burn
        max_cash = 6 * monthly_burn
        
        if state.cash < min_cash:
            deficit = min_cash - state.cash
            # Liquidation logic (simplistic: pro-rata across liquid assets)
            liquid_assets = [a for a in state.investments if a.is_liquid]
            total_liquid = sum(a.value for a in liquid_assets)
            
            if total_liquid > 0:
                for asset in liquid_assets:
                    amount_to_sell = min(asset.value, deficit * (asset.value / total_liquid))
                    asset.value -= amount_to_sell
                    state.cash += amount_to_sell
        
        elif state.cash > max_cash:
            surplus = state.cash - max_cash
            # Investment logic: dump into first liquid asset (e.g., Index Fund)
            if state.investments:
                state.investments[0].value += surplus
                state.cash -= surplus

    @staticmethod
    def check_failure(state):
        """Policy 2: Bankruptcy Detection"""
        if state.cash < 0:
            state.failed = True
            state.failure_reason = "Insolvency: Ran out of cash and liquid assets."