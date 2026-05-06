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
        0: Equity Market Returns (Exact GBM)
        1: Inflation (Mean Reverting)
        2: Interest Rates (Mean Reverting)
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
        reshaped_shocks = uncorrelated_shocks.reshape(5, -1)
        correlated_shocks = (L @ reshaped_shocks).reshape(5, self.months, self.paths)
        
        # Extract individual shock streams
        z_mkt, z_inf, z_rate, z_house, z_sal = correlated_shocks
        
        # 2. Simulate Paths
        market_returns = np.zeros((self.months, self.paths))
        inflation = np.zeros((self.months, self.paths))
        interest_rates = np.zeros((self.months, self.paths))
        housing_growth = np.zeros((self.months, self.paths))
        salary_growth = np.zeros((self.months, self.paths))
        
        # Initial Conditions
        curr_rate = config['base_interest_rate']
        curr_inf = config['base_inflation']
        
        # Parameters (Mean Reversion Speed, Volatility, Long-run Mean)
        kappa_inf, theta_inf, vol_inf = 0.5, 0.03, 0.01
        kappa_rate, theta_rate, vol_rate = 0.3, 0.04, 0.015
        
        # --- NEW: Pre-calculate Exact GBM Constants ---
        mu = config['expected_mkt_return']
        sigma = config['mkt_vol']
        # The drift includes the -0.5 * sigma^2 correction term
        gbm_drift = (mu - 0.5 * sigma**2) * self.dt
        gbm_diffusion_scalar = sigma * np.sqrt(self.dt)
        
        for t in range(self.months):
            # Market (Exact GBM Solution) - Vectorized
            market_returns[t] = np.exp(gbm_drift + gbm_diffusion_scalar * z_mkt[t]) - 1.0
            
            # Inflation (Ornstein-Uhlenbeck)
            d_inf = kappa_inf * (theta_inf - curr_inf) * self.dt + vol_inf * np.sqrt(self.dt) * z_inf[t]
            curr_inf += d_inf
            inflation[t] = curr_inf
            
            # Interest Rates 
            d_rate = kappa_rate * (theta_rate - curr_rate) * self.dt + vol_rate * np.sqrt(self.dt) * z_rate[t]
            curr_rate += d_rate
            interest_rates[t] = np.maximum(curr_rate, 0.0) # Floor at 0
            
            # Housing (Correlated with Inflation + local variance)
            housing_growth[t] = (curr_inf * self.dt + 
                                 0.01 * self.dt + 
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
            'unforseen_shocks': self.rng.binomial(1, 0.01, (self.months, self.paths)) 
        }