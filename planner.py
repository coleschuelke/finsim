import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# ==========================================
# 0. INPUTS (HOUSEHOLD CONFIG)
# ==========================================
# Income Streams (Annual Gross)
P1_SALARY = 140_000  # User
P2_SALARY = 160_000  # Partner

# Tax Logic (Simplified Effective Rates)
# You can set these individually if one person is 1099 vs W2, or filing separately
P1_TAX_RATE = 0.22
P2_TAX_RATE = 0.20

# Shared Finances
JOINT_SAVINGS = 100_000  # Total Liquid Cash across all accounts
JOINT_MONTHLY_ESSENTIALS = 5_000  # Rent, Food, Utilities, Shared Bills

# Life Events & Purchases
# 'gross_salary_delta': Change in annual gross income (can be P1 or P2, math is the same)
LIFE_EVENTS = [
    {
        "name": "Truck Purchase",
        "year": 1,
        "cost": 40_000,
        "monthly_expense_delta": 150,  # Gas/Ins increase
    },
    {
        "name": "P1 Promotion",
        "year": 2.5,
        "gross_salary_delta": 15_000,
        "tax_rate_for_delta": 0.24,  # Marginal tax rate on this new income
    },
    {
        "name": "P2 Promotion",
        "year": 3,
        "gross_salary_delta": 20_000,
        "tax_rate_for_delta": 0.24,  # Marginal tax rate on this new income
    },
    {
        "name": "House Purchase",
        "year": 5,
        "cost": 300_000,
        "monthly_expense_delta": 1800,  # Mortgage vs Rent differential
    },
]

# Simulation Constants
N_SIMULATIONS = 5_000
MARKET_MEAN = 0.07  # Real Return
MARKET_STD = 0.15
MAX_SAVINGS_PCT = 0.80  # Couples can often save higher % due to shared overhead

# ==========================================
# 1. TAX ENGINE (New Module)
# ==========================================
# 2026 Est. Federal Brackets (Rate, Income Cap)
# Note: The last bracket cap is float('inf')
TAX_BRACKETS = {
    "single": [
        (0.10, 11_925),
        (0.12, 48_475),
        (0.22, 103_350),
        (0.24, 197_300),
        (0.32, 250_525),
        (0.35, 626_350),
        (0.37, float("inf")),
    ],
    "joint": [
        (0.10, 23_850),
        (0.12, 96_950),
        (0.22, 206_700),
        (0.24, 394_600),
        (0.32, 501_050),
        (0.35, 751_600),
        (0.37, float("inf")),
    ],
}

STANDARD_DEDUCTION = {"single": 14_600, "joint": 29_200}
FICA_RATE = 0.0765  # SS + Medicare (Flat for simplicity, ignores SS cap)


def calculate_annual_net(gross_income, filing_status="single"):
    """
    Returns Annual Net Income after Federal Tax + FICA.
    Does not include State tax (add a flat % if needed).
    """
    # 1. Apply Deductions
    taxable_income = max(0, gross_income - STANDARD_DEDUCTION[filing_status])

    # 2. Calculate Federal Tax
    federal_tax = 0
    previous_cap = 0

    for rate, cap in TAX_BRACKETS[filing_status]:
        if taxable_income > previous_cap:
            # Income in this specific bracket
            taxable_in_bracket = min(taxable_income, cap) - previous_cap
            federal_tax += taxable_in_bracket * rate
            previous_cap = cap
        else:
            break

    # 3. Calculate FICA (Social Security + Medicare)
    # (Technically SS caps at ~$176k, but keeping it flat is a safe conservative estimate)
    fica_tax = gross_income * FICA_RATE

    return gross_income - federal_tax - fica_tax


# ==========================================
# 2. LOGIC ENGINE
# ==========================================
def calculate_household_baseline():
    # Calculate net monthly income for each person
    p1_net = (P1_SALARY * (1 - P1_TAX_RATE)) / 12
    p2_net = (P2_SALARY * (1 - P2_TAX_RATE)) / 12

    total_monthly_net = p1_net + p2_net
    max_household_save = total_monthly_net - JOINT_MONTHLY_ESSENTIALS

    return total_monthly_net, max_household_save


def process_events(events):
    """
    Calculates Net Monthly Cash Flow impact.
    Now supports specific tax rates for specific income changes (Marginal Tax concept).
    """
    processed_events = []
    for e in events:
        net_flow_change = 0

        # 1. Income Changes
        if "gross_salary_delta" in e:
            # If a specific tax rate is provided for this change, use it.
            # Otherwise default to an average of P1/P2 rates (0.21 approx)
            rate = e.get("tax_rate_for_delta", 0.22)
            monthly_gross_diff = e["gross_salary_delta"] / 12
            net_flow_change += monthly_gross_diff * (1 - rate)

        # 2. Expense Changes
        if "monthly_expense_delta" in e:
            net_flow_change -= e["monthly_expense_delta"]

        e["calculated_net_flow"] = net_flow_change
        processed_events.append(e)
    return processed_events


def process_events_dynamic_tax(events, start_p1_gross, start_p2_gross):
    """
    Iterates through events chronologically.
    Tracks the 'Current Gross Salary' state to calculate
    exact marginal net impact of any raises/cuts.
    """
    # Sort events by year to ensure we track salary evolution correctly
    sorted_events = sorted(events, key=lambda x: x["year"])

    processed = []

    # State Variables
    curr_p1 = start_p1_gross
    curr_p2 = start_p2_gross

    # We assume 'joint' if both exist, otherwise 'single'
    # You could make this a parameter if you aren't married yet
    status = "joint" if (start_p2_gross > 0) else "single"

    for e in sorted_events:
        net_flow_change = 0

        # 1. Handle Salary Changes with Progressive Tax
        if "gross_salary_delta" in e:
            # Who is getting the raise? (Default to P1 if not specified)
            person = e.get("person", "p1")

            # Calculate Net Income BEFORE the change
            # Note: We sum incomes for Joint filing
            old_household_gross = curr_p1 + curr_p2
            old_household_net = calculate_annual_net(old_household_gross, status)

            # Apply the Raise/Cut
            delta = e["gross_salary_delta"]
            if person == "p1":
                curr_p1 += delta
            else:
                curr_p2 += delta

            # Calculate Net Income AFTER the change
            new_household_gross = curr_p1 + curr_p2
            new_household_net = calculate_annual_net(new_household_gross, status)

            # The Monthly Cash Flow impact is the difference
            annual_net_delta = new_household_net - old_household_net
            net_flow_change += annual_net_delta / 12

        # 2. Handle Expense Changes
        if "monthly_expense_delta" in e:
            net_flow_change -= e["monthly_expense_delta"]

        e["calculated_net_flow"] = net_flow_change
        processed.append(e)

    return processed


def run_monte_carlo(initial_save_target, horizon_years, processed_events):
    months = int(horizon_years * 12)
    dt = 1 / 12

    monthly_mu = MARKET_MEAN / 12
    monthly_sigma = MARKET_STD * np.sqrt(dt)
    returns = np.random.normal(monthly_mu, monthly_sigma, (N_SIMULATIONS, months))

    nw = np.zeros((N_SIMULATIONS, months + 1))
    nw[:, 0] = JOINT_SAVINGS

    # Schedule mapping
    cf_impact_schedule = np.zeros(months + 1)
    lump_sum_schedule = np.zeros(months + 1)

    for e in processed_events:
        m_idx = int(e["year"] * 12)
        if m_idx < months:
            lump_sum_schedule[m_idx] += e.get("cost", 0)
            cf_impact_schedule[m_idx] += e["calculated_net_flow"]

    cumulative_cf_delta = np.cumsum(cf_impact_schedule)
    success_vector = np.ones(N_SIMULATIONS, dtype=bool)

    for t in range(1, months + 1):
        current_savings = initial_save_target + cumulative_cf_delta[t - 1]

        # Grow Wealth
        nw[:, t] = nw[:, t - 1] * (1 + returns[:, t - 1]) + current_savings

        # Apply Lump Sums
        if lump_sum_schedule[t] != 0:
            nw[:, t] -= lump_sum_schedule[t]

        # Failure Check
        failed_now = nw[:, t] < 0
        success_vector[failed_now] = False

    return np.mean(success_vector), nw


def automated_planner():
    monthly_net, max_possible_save = calculate_household_baseline()
    events = process_events_dynamic_tax(LIFE_EVENTS, P1_SALARY, P2_SALARY)

    max_event_year = max([e["year"] for e in events]) if events else 5
    sim_horizon = max_event_year + 3

    # Sweep Savings (Household Level)
    savings_amounts = np.linspace(0, max_possible_save * MAX_SAVINGS_PCT, 30)
    success_probs = []

    print(f"Simulating Household Finances over {sim_horizon} years...")
    print(f"Baseline Household Net Income: ${monthly_net:,.0f}/mo")

    rec_nw_traj = None
    rec_amt = 0

    for save_amt in savings_amounts:
        prob, trajectories = run_monte_carlo(save_amt, sim_horizon, events)
        success_probs.append(prob)
        if prob >= 0.90 and rec_nw_traj is None:
            rec_nw_traj = trajectories
            rec_amt = save_amt

    if rec_nw_traj is None:
        rec_nw_traj = trajectories
        rec_amt = savings_amounts[-1]

    return savings_amounts, success_probs, rec_nw_traj, rec_amt, sim_horizon, events


# ==========================================
# 3. VISUALIZATION
# ==========================================
def plot_analysis(save_amts, probs, best_traj, best_amt, horizon, events):
    plt.style.use("bmh")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 12))

    # --- Plot 1: Safety Curve ---
    ax1.plot(save_amts, [p * 100 for p in probs], "o-", color="#e67e22", linewidth=2)
    ax1.axhline(90, color="green", linestyle="--", label="90% Safety Threshold")
    ax1.set_title("Household Solvency Probability vs. Joint Savings")
    ax1.set_ylabel("Success Probability (%)")
    ax1.set_xlabel("Initial Joint Monthly Savings ($)")
    ax1.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax1.legend()

    # --- Plot 2: Trajectory ---
    months = np.arange(best_traj.shape[1])
    years = months / 12
    p10 = np.percentile(best_traj, 10, axis=0)
    p50 = np.percentile(best_traj, 50, axis=0)
    p90 = np.percentile(best_traj, 90, axis=0)

    ax2.plot(
        years,
        p50,
        color="#2c3e50",
        linewidth=2,
        label=f"Median (Start Save: ${best_amt:,.0f})",
    )
    ax2.fill_between(
        years, p10, p90, color="#95a5a6", alpha=0.3, label="10th-90th Percentile"
    )

    # Annotate Events
    total_flow_delta = 0
    for e in events:
        year = e["year"]
        cost = e.get("cost", 0)
        net_flow = e["calculated_net_flow"]
        total_flow_delta += net_flow

        ax2.axvline(year, color="black", linestyle=":", alpha=0.3)

        text_color = "#27ae60" if (net_flow > 0 or cost < 0) else "#c0392b"
        label_parts = [f"{e['name']}"]

        if cost != 0:
            label_parts.append(f"Lump: ${-cost/1000:+.0f}k")
        if net_flow != 0:
            label_parts.append(f"Flow: ${net_flow:+.0f}/mo")

        label = "\n".join(label_parts)
        y_pos = np.max(p90) * (0.85 if year % 2 == 0 else 0.65)

        ax2.text(
            year + 0.1,
            y_pos,
            label,
            color=text_color,
            fontsize=8,
            fontweight="bold",
            verticalalignment="top",
        )

    ax2.set_title(
        f"Household Net Worth (Final Cash Flow Delta: ${total_flow_delta:+.0f}/mo)"
    )
    ax2.set_xlabel("Years")
    ax2.set_ylabel("Net Worth (Real $)")
    ax2.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax2.legend(loc="upper left")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    s_amts, probs, traj, rec_amt, hor, evts = automated_planner()
    plot_analysis(s_amts, probs, traj, rec_amt, hor, evts)
