# market_physics.py
import numpy as np
import pandas as pd

class MarketEngine:
    def __init__(self, simulation_years, num_paths, seed=42):
        self.years = simulation_years
        self.months = int(simulation_years * 12)
        self.paths = num_paths
        self.dt = 1/12.0
        self.rng = np.random.default_rng(seed)

    def generate_scenarios(self, config):
        """
        Generates correlated economic factors using Cholesky decomposition.
        
        Variables: 
        0: Equity Market Returns (Log-normal)
        1: Inflation (Mean Reverting)
        2: Interest Rates (Mean Reverting - CIR process approximation)
        3: Housing Market Appreciation (Correlated)
        4: Salary Growth (Correlated to Inflation)
        """
        
        # 1. Define Correlation Matrix
        # [Mkt, Inf, Rates, Housing, Salary]
        corr_matrix = np.array([
            [1.0, -0.2, -0.3,  0.4,  0.1],  # Market
            [-0.2, 1.0,  0.6,  0.3,  0.7],  # Inflation
            [-0.3, 0.6,  1.0, -0.2,  0.2],  # Rates
            [ 0.4, 0.3, -0.2,  1.0,  0.2],  # Housing
            [ 0.1, 0.7,  0.2,  0.2,  1.0]   # Salary
        ])
        
        L = np.linalg.cholesky(corr_matrix)
        
        # Generate uncorrelated random shocks (N variables x Months x Paths)
        uncorrelated_shocks = self.rng.standard_normal((5, self.months, self.paths))
        
        # Apply Cholesky to get correlated shocks
        # Reshape for broadcasting: (5, Months*Paths)
        reshaped_shocks = uncorrelated_shocks.reshape(5, -1)
        correlated_shocks = (L @ reshaped_shocks).reshape(5, self.months, self.paths)
        
        # Extract individual shock streams
        z_mkt, z_inf, z_rate, z_house, z_sal = correlated_shocks
        
        # 2. Simulate Paths
        
        # Pre-allocate
        market_returns = np.zeros((self.months, self.paths))
        inflation = np.zeros((self.months, self.paths))
        interest_rates = np.zeros((self.months, self.paths))
        housing_growth = np.zeros((self.months, self.paths))
        salary_growth = np.zeros((self.months, self.paths))
        
        # Initial Conditions
        curr_rate = config['base_interest_rate']
        curr_inf = config['base_inflation']
        
        # Parameters (Mean Reversion Speed, Volatility, Long-run Mean)
        # Using simplified discrete approximation
        kappa_inf, theta_inf, vol_inf = 0.5, 0.03, 0.01
        kappa_rate, theta_rate, vol_rate = 0.3, 0.04, 0.015
        
        for t in range(self.months):
            # Market (GBM) - Vectorized
            market_returns[t] = (config['expected_mkt_return'] * self.dt + 
                                 config['mkt_vol'] * np.sqrt(self.dt) * z_mkt[t])
            
            # Inflation (Ornstein-Uhlenbeck)
            d_inf = kappa_inf * (theta_inf - curr_inf) * self.dt + vol_inf * np.sqrt(self.dt) * z_inf[t]
            curr_inf += d_inf
            inflation[t] = curr_inf
            
            # Interest Rates (CIR - ensures non-negative roughly, simplified here to OU for stability)
            d_rate = kappa_rate * (theta_rate - curr_rate) * self.dt + vol_rate * np.sqrt(self.dt) * z_rate[t]
            curr_rate += d_rate
            interest_rates[t] = np.maximum(curr_rate, 0.0) # Floor at 0
            
            # Housing (Correlated with Inflation + local variance)
            housing_growth[t] = (curr_inf * self.dt + # Base appreciation is inflation
                                 0.01 * self.dt + # Real growth
                                 0.05 * np.sqrt(self.dt) * z_house[t])
            
            # Salary (Inflation + Merit Increase + noise)
            salary_growth[t] = (curr_inf * self.dt + 
                                config['merit_increase'] * self.dt + 
                                0.02 * np.sqrt(self.dt) * z_sal[t])

        return {
            'market_returns': market_returns,
            'inflation': inflation,
            'interest_rates': interest_rates,
            'housing_growth': housing_growth,
            'salary_growth': salary_growth,
            'unforseen_shocks': self.rng.binomial(1, 0.01, (self.months, self.paths)) # 1% chance per month of shock
        }