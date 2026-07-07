"""
02 — Statistical Hypothesis Testing
======================================

Tests:
  1. Pearson & Spearman correlation: delivery delay vs review score
  2. Independent t-test: review scores for on-time vs late deliveries
  3. One-way ANOVA: delivery times across top 10 customer states
  4. Effect sizes (Cohen's d) and confidence intervals

All results printed to console and saved to reports/statistical_results.txt.

Usage:
    python scripts/02_statistical_tests.py
"""

import os
import sys
import sqlite3
import warnings
from io import StringIO

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import pearsonr, spearmanr, ttest_ind, f_oneway, mannwhitneyu

warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'ecommerce.db')
FIGURES_DIR = os.path.join(PROJECT_ROOT, 'reports', 'figures')
RESULTS_PATH = os.path.join(PROJECT_ROOT, 'reports', 'statistical_results.txt')
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

plt.style.use('seaborn-v0_8-whitegrid')

# Dual output: console + file
output_buffer = StringIO()

def tee(text):
    """Print to both console and buffer."""
    print(text)
    output_buffer.write(text + '\n')


def save_fig(fig, name):
    path = os.path.join(FIGURES_DIR, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    tee(f"  ✓ Chart saved: {path}")


def load_data():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}. Run etl.py first.")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Load fact_orders with customer state
    query = """
        SELECT f.*, c.customer_state
        FROM fact_orders f
        JOIN dim_customers c ON f.customer_unique_id = c.customer_unique_id
        WHERE f.is_delivered = 1
          AND f.delivery_days IS NOT NULL
          AND f.review_score IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    tee(f"  Loaded {len(df):,} delivered order-items with reviews and delivery data")
    return df


def cohens_d(group1, group2):
    """Compute Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = group1.var(), group2.var()
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    return (group1.mean() - group2.mean()) / pooled_std


def interpret_effect_size(d):
    """Interpret Cohen's d magnitude."""
    d = abs(d)
    if d < 0.2:
        return "negligible"
    elif d < 0.5:
        return "small"
    elif d < 0.8:
        return "medium"
    else:
        return "large"


def interpret_correlation(r):
    """Interpret correlation coefficient magnitude."""
    r = abs(r)
    if r < 0.1:
        return "negligible"
    elif r < 0.3:
        return "weak"
    elif r < 0.5:
        return "moderate"
    elif r < 0.7:
        return "strong"
    else:
        return "very strong"


# ============================================================
# TEST 1: CORRELATION — Delivery Delay vs Review Score
# ============================================================

def test_correlation(df):
    tee("\n" + "=" * 70)
    tee("  TEST 1: CORRELATION — Delivery Delay vs Review Score")
    tee("=" * 70)
    
    delay = df['delivery_delay_days'].values
    review = df['review_score'].values
    
    # Pearson correlation
    r_pearson, p_pearson = pearsonr(delay, review)
    tee(f"\n  Pearson Correlation:")
    tee(f"    r = {r_pearson:.4f}  (p = {p_pearson:.2e})")
    tee(f"    Interpretation: {interpret_correlation(r_pearson)} {'negative' if r_pearson < 0 else 'positive'} correlation")
    tee(f"    Significant at α=0.05? {'YES ✓' if p_pearson < 0.05 else 'NO ✗'}")
    
    # Spearman correlation (rank-based, more robust)
    r_spearman, p_spearman = spearmanr(delay, review)
    tee(f"\n  Spearman Rank Correlation:")
    tee(f"    ρ = {r_spearman:.4f}  (p = {p_spearman:.2e})")
    tee(f"    Interpretation: {interpret_correlation(r_spearman)} {'negative' if r_spearman < 0 else 'positive'} correlation")
    tee(f"    Significant at α=0.05? {'YES ✓' if p_spearman < 0.05 else 'NO ✗'}")
    
    tee(f"\n  Business Insight: {'Delivery delays are significantly associated with lower review scores.' if p_pearson < 0.05 and r_pearson < 0 else 'No significant association found.'}")
    
    # Visualization
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Delivery Delay vs Review Score — Correlation Analysis', fontsize=14, fontweight='bold')
    
    # Scatter with regression line
    ax = axes[0]
    # Sample for visualization (too many points)
    sample = df.sample(min(5000, len(df)), random_state=42)
    ax.scatter(sample['delivery_delay_days'], sample['review_score'],
               alpha=0.1, s=10, color='#2196F3')
    
    # Add regression line
    z = np.polyfit(delay, review, 1)
    p = np.poly1d(z)
    x_line = np.linspace(delay.min(), min(delay.max(), 40), 100)
    ax.plot(x_line, p(x_line), color='#F44336', linewidth=2,
            label=f'Pearson r = {r_pearson:.3f}')
    ax.set_xlabel('Delivery Delay (days)')
    ax.set_ylabel('Review Score')
    ax.set_title('Scatter Plot with Regression Line')
    ax.set_xlim(-30, 40)
    ax.legend()
    
    # Box plot: review score by delay bucket
    ax = axes[1]
    df_copy = df.copy()
    df_copy['delay_cat'] = pd.cut(
        df_copy['delivery_delay_days'],
        bins=[-np.inf, -7, 0, 7, 14, np.inf],
        labels=['7+ early', 'On-time', '1-7d late', '7-14d late', '14+ late']
    )
    sns.boxplot(data=df_copy, x='delay_cat', y='review_score', ax=ax,
                palette='RdYlGn_r', order=['7+ early', 'On-time', '1-7d late', '7-14d late', '14+ late'])
    ax.set_xlabel('Delivery Status')
    ax.set_ylabel('Review Score')
    ax.set_title('Review Score Distribution by Delay Category')
    
    plt.tight_layout()
    save_fig(fig, '10_correlation_delay_review')


# ============================================================
# TEST 2: T-TEST — Review Scores for On-Time vs Late
# ============================================================

def test_ttest(df):
    tee("\n" + "=" * 70)
    tee("  TEST 2: INDEPENDENT T-TEST — On-Time vs Late Reviews")
    tee("=" * 70)
    
    on_time = df[df['is_late'] == 0]['review_score']
    late = df[df['is_late'] == 1]['review_score']
    
    tee(f"\n  Group Sizes:")
    tee(f"    On-Time: n = {len(on_time):,}")
    tee(f"    Late:    n = {len(late):,}")
    
    tee(f"\n  Descriptive Statistics:")
    tee(f"    On-Time: mean = {on_time.mean():.3f}, std = {on_time.std():.3f}, median = {on_time.median():.1f}")
    tee(f"    Late:    mean = {late.mean():.3f}, std = {late.std():.3f}, median = {late.median():.1f}")
    
    # Welch's t-test (does not assume equal variances)
    t_stat, p_value = ttest_ind(on_time, late, equal_var=False)
    
    tee(f"\n  Welch's t-test:")
    tee(f"    t-statistic = {t_stat:.4f}")
    tee(f"    p-value     = {p_value:.2e}")
    tee(f"    Significant at α=0.05? {'YES ✓' if p_value < 0.05 else 'NO ✗'}")
    tee(f"    Significant at α=0.01? {'YES ✓' if p_value < 0.01 else 'NO ✗'}")
    
    # Effect size
    d = cohens_d(on_time, late)
    tee(f"\n  Effect Size:")
    tee(f"    Cohen's d = {d:.4f} ({interpret_effect_size(d)})")
    
    # 95% CI for difference in means
    diff = on_time.mean() - late.mean()
    se = np.sqrt(on_time.var() / len(on_time) + late.var() / len(late))
    ci_lower = diff - 1.96 * se
    ci_upper = diff + 1.96 * se
    tee(f"\n  95% Confidence Interval for Mean Difference:")
    tee(f"    Difference = {diff:.4f}")
    tee(f"    CI = [{ci_lower:.4f}, {ci_upper:.4f}]")
    
    # Mann-Whitney U test (non-parametric alternative)
    u_stat, u_pvalue = mannwhitneyu(on_time, late, alternative='two-sided')
    tee(f"\n  Mann-Whitney U Test (non-parametric confirmation):")
    tee(f"    U-statistic = {u_stat:,.0f}")
    tee(f"    p-value     = {u_pvalue:.2e}")
    tee(f"    Significant at α=0.05? {'YES ✓' if u_pvalue < 0.05 else 'NO ✗'}")
    
    tee(f"\n  Business Insight: {'On-time deliveries receive significantly higher review scores than late deliveries.' if p_value < 0.05 else 'No significant difference in review scores between on-time and late deliveries.'}")
    
    # Visualization
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('T-Test: On-Time vs Late Delivery Review Scores', fontsize=14, fontweight='bold')
    
    # Distribution comparison
    ax = axes[0]
    bins = np.arange(0.5, 6.5, 1)
    ax.hist(on_time, bins=bins, alpha=0.6, color='#4CAF50', label=f'On-Time (μ={on_time.mean():.2f})', density=True)
    ax.hist(late, bins=bins, alpha=0.6, color='#F44336', label=f'Late (μ={late.mean():.2f})', density=True)
    ax.set_xlabel('Review Score')
    ax.set_ylabel('Density')
    ax.set_title('Review Score Distribution')
    ax.legend()
    ax.set_xticks([1, 2, 3, 4, 5])
    
    # Mean comparison with CI
    ax = axes[1]
    means = [on_time.mean(), late.mean()]
    errors = [1.96 * on_time.std() / np.sqrt(len(on_time)),
              1.96 * late.std() / np.sqrt(len(late))]
    bars = ax.bar(['On-Time', 'Late'], means, yerr=errors, capsize=8,
                  color=['#4CAF50', '#F44336'], alpha=0.8, edgecolor='white', linewidth=2)
    ax.set_ylabel('Mean Review Score')
    ax.set_title(f'Mean Comparison (Cohen\'s d = {d:.3f})')
    ax.set_ylim(1, 5.5)
    
    # Add value labels
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f'{mean:.3f}', ha='center', fontweight='bold', fontsize=12)
    
    plt.tight_layout()
    save_fig(fig, '11_ttest_ontime_vs_late')


# ============================================================
# TEST 3: ANOVA — Delivery Times Across States
# ============================================================

def test_anova(df):
    tee("\n" + "=" * 70)
    tee("  TEST 3: ONE-WAY ANOVA — Delivery Times Across States")
    tee("=" * 70)
    
    # Top 10 states by order count
    top_states = df['customer_state'].value_counts().head(10).index.tolist()
    df_states = df[df['customer_state'].isin(top_states)]
    
    tee(f"\n  Analyzing top 10 states: {', '.join(top_states)}")
    tee(f"  Total observations: {len(df_states):,}")
    
    # Descriptive stats per state
    tee(f"\n  {'State':<8} {'N':>8} {'Mean':>8} {'Std':>8} {'Median':>8}")
    tee("  " + "-" * 44)
    
    groups = []
    for state in top_states:
        group = df_states[df_states['customer_state'] == state]['delivery_days']
        groups.append(group)
        tee(f"  {state:<8} {len(group):>8,} {group.mean():>8.1f} {group.std():>8.1f} {group.median():>8.1f}")
    
    # One-way ANOVA
    f_stat, p_value = f_oneway(*groups)
    
    tee(f"\n  One-Way ANOVA:")
    tee(f"    F-statistic = {f_stat:.4f}")
    tee(f"    p-value     = {p_value:.2e}")
    tee(f"    Significant at α=0.05? {'YES ✓' if p_value < 0.05 else 'NO ✗'}")
    
    # Effect size: eta-squared
    ss_between = sum(len(g) * (g.mean() - df_states['delivery_days'].mean()) ** 2 for g in groups)
    ss_total = sum((df_states['delivery_days'] - df_states['delivery_days'].mean()) ** 2)
    eta_squared = ss_between / ss_total
    
    tee(f"\n  Effect Size:")
    tee(f"    η² (eta-squared) = {eta_squared:.4f}")
    tee(f"    Interpretation: {'small' if eta_squared < 0.06 else 'medium' if eta_squared < 0.14 else 'large'} effect")
    tee(f"    {eta_squared * 100:.1f}% of variance in delivery time is explained by state")
    
    # Kruskal-Wallis test (non-parametric alternative)
    h_stat, h_pvalue = stats.kruskal(*groups)
    tee(f"\n  Kruskal-Wallis Test (non-parametric confirmation):")
    tee(f"    H-statistic = {h_stat:.4f}")
    tee(f"    p-value     = {h_pvalue:.2e}")
    tee(f"    Significant at α=0.05? {'YES ✓' if h_pvalue < 0.05 else 'NO ✗'}")
    
    tee(f"\n  Business Insight: {'Delivery times differ significantly across states — logistics optimization should be region-specific.' if p_value < 0.05 else 'No significant regional differences in delivery times.'}")
    
    # Visualization
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle('ANOVA: Delivery Times Across Top 10 States', fontsize=14, fontweight='bold')
    
    # Box plot
    ax = axes[0]
    state_order = (
        df_states.groupby('customer_state')['delivery_days']
        .mean()
        .sort_values(ascending=False)
        .index.tolist()
    )
    sns.boxplot(data=df_states, x='customer_state', y='delivery_days',
                order=state_order, palette='RdYlGn_r', ax=ax,
                showfliers=False)
    ax.set_xlabel('Customer State')
    ax.set_ylabel('Delivery Days')
    ax.set_title(f'Delivery Time by State (F={f_stat:.1f}, p={p_value:.2e})')
    ax.tick_params(axis='x', rotation=45)
    
    # Mean comparison with CI
    ax = axes[1]
    state_means = df_states.groupby('customer_state')['delivery_days'].agg(['mean', 'std', 'count']).loc[state_order]
    state_means['se'] = state_means['std'] / np.sqrt(state_means['count'])
    state_means['ci'] = 1.96 * state_means['se']
    
    colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(state_means)))
    ax.barh(range(len(state_means)), state_means['mean'], xerr=state_means['ci'],
            capsize=4, color=colors, edgecolor='white', linewidth=1.5)
    ax.set_yticks(range(len(state_means)))
    ax.set_yticklabels(state_means.index)
    ax.set_xlabel('Mean Delivery Days (± 95% CI)')
    ax.set_title('Mean Delivery Time with Confidence Intervals')
    ax.invert_yaxis()
    
    plt.tight_layout()
    save_fig(fig, '12_anova_delivery_by_state')


# ============================================================
# MAIN
# ============================================================

def main():
    tee("=" * 70)
    tee("  Statistical Hypothesis Testing")
    tee("=" * 70)
    
    df = load_data()
    
    test_correlation(df)
    test_ttest(df)
    test_anova(df)
    
    # Summary
    tee("\n" + "=" * 70)
    tee("  SUMMARY OF ALL TESTS")
    tee("=" * 70)
    tee("""
  ┌─────────────────────────────────────────────────────────────────┐
  │  Test                          │  Significant? │ Effect Size   │
  ├─────────────────────────────────────────────────────────────────┤
  │  1. Correlation (delay→review) │  See above    │ See above     │
  │  2. T-test (on-time vs late)   │  See above    │ See above     │
  │  3. ANOVA (delivery by state)  │  See above    │ See above     │
  └─────────────────────────────────────────────────────────────────┘
  
  Note: Actual values are printed above for each test.
  All results saved to: reports/statistical_results.txt
""")
    
    # Save results to file
    with open(RESULTS_PATH, 'w') as f:
        f.write(output_buffer.getvalue())
    
    tee(f"\n  ✅ STATISTICAL TESTS COMPLETE")
    tee(f"  Results saved to: {RESULTS_PATH}")
    tee(f"  Charts saved to: {FIGURES_DIR}")


if __name__ == '__main__':
    main()
