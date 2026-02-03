import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# ==========================================
# 1. INPUT PARAMETERS
# ==========================================
# Financial Basics
CURRENT_SALARY = 250_000  # Annual gross salary
CURRENT_SAVINGS = 100_000  # Liquid savings / Investments

# Savings Rate Parameters (Stochastic)
SAVINGS_RATE_MEAN = 0.30  # Target savings rate (20%)
SAVINGS_RATE_STD = 0.1  # Fluctuation (e.g., unexpected expenses or lifestyle creep)

# The Purchase
TRUCK_COST = 40_000
TRUCK_O_M_DELTA = 1_500  # Annual increase in Gas/Ins/Maint vs current vehicle
VEHICLE_LIFESPAN = 20

# Stochastic Variables
N_SIMULATIONS = 10_000
YEARS = 20
INFLATION_MEAN = 0.030
INFLATION_STD = 0.010
MARKET_RETURN_MEAN = 0.08
MARKET_RETURN_STD = 0.16
RAISE_MEAN = 0.04
RAISE_STD = 0.015


# ==========================================
# 2. SIMULATION LOGIC
# ==========================================
def run_simulation():
    np.random.seed(42)

    # --- Generate Stochastic Rates [Simulations, Years] ---

    # 1. Market Returns
    market_returns = np.random.normal(
        MARKET_RETURN_MEAN, MARKET_RETURN_STD, (N_SIMULATIONS, YEARS)
    )

    # 2. Salary Growth
    salary_growth = np.random.normal(RAISE_MEAN, RAISE_STD, (N_SIMULATIONS, YEARS))

    # 3. Inflation
    inflation_rates = np.random.normal(
        INFLATION_MEAN, INFLATION_STD, (N_SIMULATIONS, YEARS)
    )
    cumulative_inflation = np.cumprod(1 + inflation_rates, axis=1)

    # 4. Savings Rate (New Perturbed Parameter)
    # We clip this between 0.0 (0%) and 0.6 (60%) to prevent unrealistic outliers
    raw_savings = np.random.normal(
        SAVINGS_RATE_MEAN, SAVINGS_RATE_STD, (N_SIMULATIONS, YEARS)
    )
    savings_rates = np.clip(raw_savings, 0.0, 0.6)

    # --- Initialize State Matrices ---
    nw_truck = np.zeros((N_SIMULATIONS, YEARS))
    nw_invest = np.zeros((N_SIMULATIONS, YEARS))

    # Initial Conditions
    nw_truck[:, 0] = CURRENT_SAVINGS - TRUCK_COST
    nw_invest[:, 0] = CURRENT_SAVINGS

    current_salary_vec = np.ones(N_SIMULATIONS) * CURRENT_SALARY

    # --- Time Propagation ---
    for t in range(1, YEARS):
        # Update Salary
        current_salary_vec *= 1 + salary_growth[:, t]

        # Calculate Savings for this specific year/sim based on the perturbed rate
        annual_savings = current_salary_vec * savings_rates[:, t]

        # Scenario A (Truck)
        is_owning_truck = 1 if t <= VEHICLE_LIFESPAN else 0
        nw_truck[:, t] = (
            (nw_truck[:, t - 1] * (1 + market_returns[:, t]))
            + annual_savings
            - (TRUCK_O_M_DELTA * is_owning_truck)
        )

        # Scenario B (Invest)
        nw_invest[:, t] = (
            nw_invest[:, t - 1] * (1 + market_returns[:, t])
        ) + annual_savings

    # Adjust for Inflation (Real Dollars)
    nw_truck_real = nw_truck / cumulative_inflation
    nw_invest_real = nw_invest / cumulative_inflation

    return nw_truck_real, nw_invest_real


# ==========================================
# 3. VISUALIZATION
# ==========================================
def plot_results(nw_truck, nw_invest):
    years_range = np.arange(YEARS)

    # Calculate Percentiles
    p10_truck = np.percentile(nw_truck, 10, axis=0)
    p50_truck = np.percentile(nw_truck, 50, axis=0)
    p90_truck = np.percentile(nw_truck, 90, axis=0)

    p50_invest = np.percentile(nw_invest, 50, axis=0)

    # Plot Setup
    plt.style.use("bmh")  # Using a cleaner style for engineering plots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12))

    # --- Plot 1: Net Worth Trajectory ---
    ax1.fill_between(
        years_range,
        p10_truck,
        p90_truck,
        color="#3498db",
        alpha=0.3,
        label="Truck Scenario (10th-90th %ile)",
    )
    ax1.plot(
        years_range,
        p50_truck,
        color="#2980b9",
        linewidth=2.5,
        label="Truck Scenario (Median)",
    )
    ax1.plot(
        years_range,
        p50_invest,
        color="#27ae60",
        linestyle="--",
        linewidth=2.5,
        label="No Truck (Median)",
    )

    ax1.set_title(
        f"Real Net Worth Projection (Savings Rate $\mu={SAVINGS_RATE_MEAN}, \sigma={SAVINGS_RATE_STD}$)",
        fontsize=14,
    )
    ax1.set_ylabel("Real Net Worth ($)", fontsize=12)
    ax1.set_xlabel("Years from Now", fontsize=12)
    ax1.legend(loc="upper left")
    ax1.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))

    # --- Plot 2: Opportunity Cost Distribution ---
    final_diff = nw_invest[:, -1] - nw_truck[:, -1]

    # Dynamic bin sizing
    ax2.hist(final_diff, bins=50, color="#e74c3c", alpha=0.75, edgecolor="white")
    ax2.axvline(
        np.mean(final_diff),
        color="black",
        linestyle="--",
        linewidth=2,
        label=f"Mean Opp. Cost: ${np.mean(final_diff):,.0f}",
    )

    ax2.set_title(f"Distribution of Opportunity Cost at Year {YEARS}", fontsize=14)
    ax2.set_xlabel("Net Worth Difference (Wealth Lost to Truck)", fontsize=12)
    ax2.set_ylabel("Frequency", fontsize=12)
    ax2.legend()
    ax2.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    truck_data, invest_data = run_simulation()
    plot_results(truck_data, invest_data)
