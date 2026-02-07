import matplotlib.pyplot as plt
import numpy as np

class Visualizer:
    @staticmethod
    def plot_monte_carlo_paths(results, title="Net Worth Projection"):
        """
        Plots the 'cone of uncertainty' for Net Worth over time.
        Gray lines: Individual simulation traces (subset).
        Blue line: Median outcome.
        Shaded region: 90% Confidence Interval (5th to 95th percentile).
        """
        plt.figure(figsize=(12, 7))
        
        # 1. Plot individual traces (alpha-blended for density effect)
        # Limit to 50 traces to keep rendering fast and clean
        for res in results[:50]:
            df = res['history']
            if not df.empty:
                plt.plot(df['year'], df['Net Worth'], color='gray', alpha=0.15, linewidth=1)
        
        # 2. Calculate Statistics across all sims
        # Align all time series (handle potential failures where series stop early)
        max_steps = max(len(r['history']) for r in results)
        
        # Stack data: shape (n_sims, n_steps)
        # Note: In production, use efficient padding for varying lengths
        valid_series = [r['history']['Net Worth'].values for r in results if len(r['history']) == max_steps]
        if valid_series:
            data_stack = np.vstack(valid_series)
            median = np.median(data_stack, axis=0)
            p05 = np.percentile(data_stack, 5, axis=0)
            p95 = np.percentile(data_stack, 95, axis=0)
            years = np.linspace(0, max_steps/12, max_steps)
            
            plt.plot(years, median, color='#007acc', linewidth=2.5, label='Median Projection')
            plt.fill_between(years, p05, p95, color='#007acc', alpha=0.15, label='90% Confidence Interval')
        
        plt.title(title, fontsize=14, pad=15)
        plt.xlabel("Years", fontsize=12)
        plt.ylabel("Net Worth ($)", fontsize=12)
        plt.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.7)
        plt.legend(loc='upper left')
        plt.tight_layout()
        plt.savefig(f"{title.replace(' ', '_')}.png", dpi=100)
        plt.close()

    @staticmethod
    def plot_scenario_comparison(results_a, results_b, label_a="Baseline", label_b="Scenario"):
        """
        Comparing two distributions of Final Net Worth.
        Useful for answering: "Does buying this house significantly increase my risk of ruin?"
        """
        final_a = [r['final_nw'] for r in results_a]
        final_b = [r['final_nw'] for r in results_b]
        
        plt.figure(figsize=(10, 6))
        
        # Histograms as probability density
        plt.hist(final_a, bins=30, alpha=0.5, color='gray', label=label_a, density=True)
        plt.hist(final_b, bins=30, alpha=0.5, color='#d62728', label=label_b, density=True)
        
        # Medians
        plt.axvline(np.median(final_a), color='black', linestyle='--', linewidth=1.5, label=f'{label_a} Median')
        plt.axvline(np.median(final_b), color='red', linestyle='--', linewidth=1.5, label=f'{label_b} Median')
        
        plt.title(f"Outcome Distribution: {label_a} vs {label_b}", fontsize=14)
        plt.xlabel("Final Net Worth ($)", fontsize=12)
        plt.ylabel("Probability Density", fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig("Scenario_Comparison.png", dpi=100)
        plt.close()

    @staticmethod
    def plot_sensitivity(impacts):
        """
        Tornado plot showing which factors drive the most variance.
        impacts: dict {factor_name: delta_in_net_worth}
        """
        factors = list(impacts.keys())
        values = list(impacts.values())
        
        plt.figure(figsize=(10, 5))
        y_pos = np.arange(len(factors))
        
        colors = ['green' if v > 0 else 'red' for v in values]
        plt.barh(y_pos, values, align='center', color=colors, alpha=0.7)
        plt.yticks(y_pos, factors)
        plt.xlabel('Impact on Median Net Worth ($)', fontsize=12)
        plt.title('Sensitivity Analysis (Variable Shock +/- 20%)', fontsize=14)
        plt.axvline(0, color='black', linewidth=0.8)
        plt.grid(True, axis='x', alpha=0.3)
        plt.tight_layout()
        plt.savefig("Sensitivity_Analysis.png", dpi=100)
        plt.close()

    @staticmethod
    def plot_probability_curve(x_values, probabilities, x_label="Monthly Savings ($)", title="Probability of Goal Achievement"):
        """
        Plots a sigmoid-like curve showing how probability of success changes with an input.
        Useful for finding the 'knee' where diminishing returns set in.
        """
        plt.figure(figsize=(10, 6))
        
        # Plot the curve
        plt.plot(x_values, probabilities, marker='o', linestyle='-', color='#2ca02c', linewidth=2, label='Success Probability')
        
        # Add a reference line at 90% (Common engineering confidence interval)
        plt.axhline(0.90, color='red', linestyle='--', alpha=0.5, label='90% Confidence Target')
        
        # Interpolate to find the exact X value for 90%
        try:
            # Simple linear interpolation for the crossing point
            target_x = np.interp(0.90, probabilities, x_values)
            plt.axvline(target_x, color='red', linestyle=':', alpha=0.5)
            plt.text(target_x, 0.5, f" Required: ${target_x:,.0f}", rotation=90, verticalalignment='center', color='red')
        except:
            pass # 90% not reached or already exceeded
            
        plt.title(title, fontsize=14)
        plt.xlabel(x_label, fontsize=12)
        plt.ylabel("Probability of Success (0-1)", fontsize=12)
        plt.grid(True, which='both', linestyle='--', alpha=0.7)
        plt.ylim(0, 1.05)
        plt.legend()
        plt.tight_layout()
        plt.savefig("Probability_Curve.png", dpi=100)
        plt.close()