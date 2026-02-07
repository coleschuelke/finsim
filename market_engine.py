import numpy as np

class MarketEngine:
    def __init__(self, years, steps_per_year=12):
        self.dt = 1 / steps_per_year
        self.steps = years * steps_per_year
        self.years = years
        
        # Mean Reversion Parameters (Ornstein-Uhlenbeck)
        # theta: speed of reversion, mu: long-term mean, sigma: volatility
        self.params = {
            'inflation': {'theta': 0.5, 'mu': 0.03, 'sigma': 0.01},
            'mkt_return': {'theta': 0.0, 'mu': 0.07, 'sigma': 0.15}, # GBM usually, but we treat returns as stationary
            'interest_rate': {'theta': 0.3, 'mu': 0.04, 'sigma': 0.015},
            'salary_growth': {'theta': 0.5, 'mu': 0.03, 'sigma': 0.02},
            'housing_growth': {'theta': 0.2, 'mu': 0.04, 'sigma': 0.05}
        }
        
        # Correlation Matrix (Order: inflation, mkt, rates, salary, housing)
        self.corr_matrix = np.array([
            [1.0, -0.2,  0.6,  0.4,  0.3], # Inflation
            [-0.2, 1.0, -0.1,  0.5,  0.4], # Market
            [0.6, -0.1,  1.0,  0.1, -0.3], # Rates
            [0.4,  0.5,  0.1,  1.0,  0.5], # Salary
            [0.3,  0.4, -0.3,  0.5,  1.0]  # Housing
        ])
        
        # Cholesky Decomposition for correlated shocks
        self.L = np.linalg.cholesky(self.corr_matrix)

    def generate_scenario(self):
        """Generates a full time-series for all variables."""
        n_vars = len(self.params)
        keys = list(self.params.keys())
        
        # Generate uncorrelated standard normals
        dw = np.random.normal(0, np.sqrt(self.dt), (self.steps, n_vars))
        # Correlate them
        correlated_dw = dw @ self.L.T
        
        paths = {k: np.zeros(self.steps) for k in keys}
        
        # Initialize with means
        current_vals = np.array([self.params[k]['mu'] for k in keys])
        
        for t in range(self.steps):
            # Calculate deltas using OU Process: dX = theta*(mu - X)*dt + sigma*dW
            # Note: For geometric growth (stocks), this return is applied exponentially later
            
            mus = np.array([self.params[k]['mu'] for k in keys])
            thetas = np.array([self.params[k]['theta'] for k in keys])
            sigmas = np.array([self.params[k]['sigma'] for k in keys])
            
            dx = thetas * (mus - current_vals) * self.dt + sigmas * correlated_dw[t]
            current_vals += dx
            
            for i, k in enumerate(keys):
                paths[k][t] = current_vals[i]
                
        # Unforeseen expenses (Poisson process modeling rare shocks)
        # 10% chance per year of a 5k-20k expense
        shock_prob = 0.1 * self.dt
        shocks = np.random.binomial(1, shock_prob, self.steps) * np.random.uniform(5000, 20000, self.steps)
        paths['unforeseen_expense'] = shocks
        
        return paths