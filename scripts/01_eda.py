"""
01 — Exploratory Data Analysis (EDA)
=====================================

Loads the SQLite star schema database and produces comprehensive
exploratory visualizations. All charts saved to reports/figures/.

Usage:
    python scripts/01_eda.py
"""

import os
import sys
import sqlite3
import warnings

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'ecommerce.db')
FIGURES_DIR = os.path.join(PROJECT_ROOT, 'reports', 'figures')
os.makedirs(FIGURES_DIR, exist_ok=True)

# Style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette('husl')
COLORS = {
    'primary': '#2196F3',
    'secondary': '#FF9800',
    'accent': '#4CAF50',
    'danger': '#F44336',
    'dark': '#37474F',
    'gradient': ['#1a237e', '#283593', '#3949ab', '#5c6bc0', '#7986cb'],
}


def load_data():
    """Load tables from SQLite."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("   Run 'python scripts/etl.py' first.")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    fact = pd.read_sql("SELECT * FROM fact_orders", conn)
    dim_customers = pd.read_sql("SELECT * FROM dim_customers", conn)
    dim_products = pd.read_sql("SELECT * FROM dim_products", conn)
    dim_sellers = pd.read_sql("SELECT * FROM dim_sellers", conn)
    dim_date = pd.read_sql("SELECT * FROM dim_date", conn)
    conn.close()
    
    # Parse dates
    fact['order_purchase_timestamp'] = pd.to_datetime(fact['order_purchase_timestamp'])
    fact['year_month'] = fact['order_purchase_timestamp'].dt.to_period('M').astype(str)
    
    return fact, dim_customers, dim_products, dim_sellers, dim_date


def save_fig(fig, name):
    """Save figure and close."""
    path = os.path.join(FIGURES_DIR, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  ✓ Saved: {path}")


# ============================================================
# 1. DATASET OVERVIEW
# ============================================================

def dataset_overview(fact, dim_customers, dim_products, dim_sellers):
    """Print dataset summary statistics."""
    print("\n" + "=" * 60)
    print("  1. DATASET OVERVIEW")
    print("=" * 60)
    
    delivered = fact[fact['is_delivered'] == 1]
    
    print(f"\n  Total order items:     {len(fact):,}")
    print(f"  Delivered items:       {len(delivered):,}")
    print(f"  Unique orders:         {fact['order_id'].nunique():,}")
    print(f"  Unique customers:      {len(dim_customers):,}")
    print(f"  Unique products:       {len(dim_products):,}")
    print(f"  Unique sellers:        {len(dim_sellers):,}")
    print(f"  Date range:            {fact['order_purchase_timestamp'].min().date()} to {fact['order_purchase_timestamp'].max().date()}")
    print(f"  Total GMV:             R$ {delivered['total_item_value'].sum():,.2f}")
    print(f"  Avg order item value:  R$ {delivered['total_item_value'].mean():.2f}")
    
    # Missing values
    print(f"\n  Missing values in fact_orders:")
    nulls = fact.isnull().sum()
    for col in nulls[nulls > 0].index:
        print(f"    {col}: {nulls[col]:,} ({nulls[col]*100/len(fact):.1f}%)")


# ============================================================
# 2. ORDER VOLUME TREND
# ============================================================

def plot_order_volume(fact):
    """Monthly order volume and GMV trend."""
    print("\n  Plotting order volume trend...")
    
    delivered = fact[fact['is_delivered'] == 1]
    monthly = (
        delivered.groupby('year_month')
        .agg(orders=('order_id', 'nunique'), gmv=('total_item_value', 'sum'))
        .reset_index()
    )
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle('Monthly Order Volume & GMV Trend', fontsize=16, fontweight='bold')
    
    # Order count
    ax1.bar(range(len(monthly)), monthly['orders'], color=COLORS['primary'], alpha=0.8)
    ax1.set_ylabel('Number of Orders', fontsize=12)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1000:.1f}K'))
    ax1.set_title('Order Volume', fontsize=13)
    
    # GMV
    ax2.fill_between(range(len(monthly)), monthly['gmv'], alpha=0.3, color=COLORS['accent'])
    ax2.plot(range(len(monthly)), monthly['gmv'], color=COLORS['accent'], linewidth=2, marker='o', markersize=4)
    ax2.set_ylabel('GMV (R$)', fontsize=12)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'R${x/1e6:.1f}M'))
    ax2.set_title('Gross Merchandise Value', fontsize=13)
    
    # X-axis labels
    tick_positions = range(0, len(monthly), max(1, len(monthly) // 12))
    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels([monthly['year_month'].iloc[i] for i in tick_positions], rotation=45, ha='right')
    
    plt.tight_layout()
    save_fig(fig, '01_order_volume_trend')


# ============================================================
# 3. REVENUE BY CATEGORY
# ============================================================

def plot_category_revenue(fact, dim_products):
    """Top 15 product categories by revenue."""
    print("  Plotting category revenue...")
    
    delivered = fact[fact['is_delivered'] == 1]
    merged = delivered.merge(dim_products[['product_id', 'product_category']], on='product_id')
    
    cat_rev = (
        merged.groupby('product_category')['total_item_value']
        .sum()
        .sort_values(ascending=True)
        .tail(15)
    )
    
    fig, ax = plt.subplots(figsize=(12, 8))
    bars = ax.barh(cat_rev.index, cat_rev.values, color=plt.cm.viridis(np.linspace(0.3, 0.9, len(cat_rev))))
    ax.set_xlabel('Revenue (R$)', fontsize=12)
    ax.set_title('Top 15 Product Categories by Revenue', fontsize=16, fontweight='bold')
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'R${x/1e6:.1f}M'))
    
    # Add value labels
    for bar, val in zip(bars, cat_rev.values):
        ax.text(val + cat_rev.max() * 0.01, bar.get_y() + bar.get_height() / 2,
                f'R${val/1e6:.2f}M', va='center', fontsize=9)
    
    plt.tight_layout()
    save_fig(fig, '02_category_revenue')


# ============================================================
# 4. REVENUE BY STATE
# ============================================================

def plot_state_revenue(fact, dim_customers):
    """Revenue by customer state."""
    print("  Plotting state revenue...")
    
    delivered = fact[fact['is_delivered'] == 1]
    merged = delivered.merge(dim_customers[['customer_unique_id', 'customer_state']], on='customer_unique_id')
    
    state_rev = (
        merged.groupby('customer_state')['total_item_value']
        .sum()
        .sort_values(ascending=True)
        .tail(15)
    )
    
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = plt.cm.YlOrRd(np.linspace(0.3, 0.9, len(state_rev)))
    ax.barh(state_rev.index, state_rev.values, color=colors)
    ax.set_xlabel('Revenue (R$)', fontsize=12)
    ax.set_title('Revenue by Customer State (Top 15)', fontsize=16, fontweight='bold')
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'R${x/1e6:.1f}M'))
    
    plt.tight_layout()
    save_fig(fig, '03_state_revenue')


# ============================================================
# 5. DELIVERY TIME DISTRIBUTION
# ============================================================

def plot_delivery_distribution(fact):
    """Distribution of delivery times and delays."""
    print("  Plotting delivery distribution...")
    
    delivered = fact[(fact['is_delivered'] == 1) & (fact['delivery_days'].notna())]
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('Delivery Time Analysis', fontsize=16, fontweight='bold')
    
    # Delivery days distribution
    ax = axes[0]
    ax.hist(delivered['delivery_days'].clip(0, 60), bins=40, color=COLORS['primary'], alpha=0.7, edgecolor='white')
    ax.axvline(delivered['delivery_days'].median(), color=COLORS['danger'], linestyle='--', linewidth=2,
               label=f'Median: {delivered["delivery_days"].median():.1f} days')
    ax.set_xlabel('Delivery Days')
    ax.set_ylabel('Count')
    ax.set_title('Actual Delivery Time')
    ax.legend()
    
    # Delay distribution
    ax = axes[1]
    delay = delivered['delivery_delay_days'].dropna()
    ax.hist(delay.clip(-30, 30), bins=50, color=COLORS['secondary'], alpha=0.7, edgecolor='white')
    ax.axvline(0, color=COLORS['danger'], linestyle='-', linewidth=2, label='On-time threshold')
    ax.set_xlabel('Delay Days (positive = late)')
    ax.set_ylabel('Count')
    ax.set_title('Delivery Delay Distribution')
    ax.legend()
    
    # On-time vs Late pie
    ax = axes[2]
    on_time = (delivered['is_late'] == 0).sum()
    late = (delivered['is_late'] == 1).sum()
    ax.pie([on_time, late], labels=['On-Time', 'Late'],
           colors=[COLORS['accent'], COLORS['danger']],
           autopct='%1.1f%%', startangle=90, textprops={'fontsize': 12})
    ax.set_title('On-Time vs Late Delivery')
    
    plt.tight_layout()
    save_fig(fig, '04_delivery_distribution')


# ============================================================
# 6. REVIEW SCORE DISTRIBUTION
# ============================================================

def plot_review_scores(fact):
    """Review score distribution and relationship with delivery."""
    print("  Plotting review scores...")
    
    delivered = fact[(fact['is_delivered'] == 1) & (fact['review_score'].notna())]
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('Customer Review Analysis', fontsize=16, fontweight='bold')
    
    # Score distribution
    ax = axes[0]
    score_counts = delivered['review_score'].value_counts().sort_index()
    colors = ['#F44336', '#FF9800', '#FFC107', '#8BC34A', '#4CAF50']
    ax.bar(score_counts.index, score_counts.values, color=colors, edgecolor='white', linewidth=1.5)
    ax.set_xlabel('Review Score')
    ax.set_ylabel('Count')
    ax.set_title('Review Score Distribution')
    ax.set_xticks([1, 2, 3, 4, 5])
    
    # Review by on-time vs late
    ax = axes[1]
    on_time_reviews = delivered[delivered['is_late'] == 0]['review_score']
    late_reviews = delivered[delivered['is_late'] == 1]['review_score']
    ax.hist(on_time_reviews, bins=5, alpha=0.6, label=f'On-Time (mean: {on_time_reviews.mean():.2f})',
            color=COLORS['accent'], edgecolor='white')
    ax.hist(late_reviews, bins=5, alpha=0.6, label=f'Late (mean: {late_reviews.mean():.2f})',
            color=COLORS['danger'], edgecolor='white')
    ax.set_xlabel('Review Score')
    ax.set_ylabel('Count')
    ax.set_title('Reviews: On-Time vs Late')
    ax.legend()
    
    # Average review by delay bucket
    ax = axes[2]
    delivered_copy = delivered.copy()
    delivered_copy['delay_bucket'] = pd.cut(
        delivered_copy['delivery_delay_days'],
        bins=[-np.inf, -7, -3, 0, 3, 7, 14, np.inf],
        labels=['<-7d', '-7 to -3d', '-3 to 0d', '0-3d late', '3-7d late', '7-14d late', '>14d late']
    )
    bucket_avg = delivered_copy.groupby('delay_bucket', observed=True)['review_score'].mean()
    bar_colors = ['#4CAF50', '#66BB6A', '#8BC34A', '#FFC107', '#FF9800', '#FF5722', '#F44336']
    ax.bar(range(len(bucket_avg)), bucket_avg.values, color=bar_colors[:len(bucket_avg)], edgecolor='white')
    ax.set_xticks(range(len(bucket_avg)))
    ax.set_xticklabels(bucket_avg.index, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Average Review Score')
    ax.set_title('Avg Review by Delay Bucket')
    ax.set_ylim(1, 5.5)
    
    plt.tight_layout()
    save_fig(fig, '05_review_analysis')


# ============================================================
# 7. PAYMENT METHOD BREAKDOWN
# ============================================================

def plot_payment_methods(fact):
    """Payment method distribution."""
    print("  Plotting payment methods...")
    
    delivered = fact[fact['is_delivered'] == 1]
    payment_counts = delivered.groupby('payment_type')['order_id'].nunique().sort_values(ascending=False)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Payment Method Analysis', fontsize=16, fontweight='bold')
    
    # Pie chart
    top_payments = payment_counts.head(5)
    colors = plt.cm.Set3(np.linspace(0, 1, len(top_payments)))
    ax1.pie(top_payments.values, labels=top_payments.index,
            colors=colors, autopct='%1.1f%%', startangle=90,
            textprops={'fontsize': 11})
    ax1.set_title('Order Distribution by Payment Type')
    
    # Revenue by payment type
    payment_rev = delivered.groupby('payment_type')['total_item_value'].sum().sort_values(ascending=True)
    ax2.barh(payment_rev.index, payment_rev.values, color=plt.cm.Set2(np.linspace(0, 1, len(payment_rev))))
    ax2.set_xlabel('Revenue (R$)')
    ax2.set_title('Revenue by Payment Type')
    ax2.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'R${x/1e6:.1f}M'))
    
    plt.tight_layout()
    save_fig(fig, '06_payment_methods')


# ============================================================
# 8. SELLER DISTRIBUTION
# ============================================================

def plot_seller_analysis(fact, dim_sellers):
    """Seller performance distribution."""
    print("  Plotting seller analysis...")
    
    delivered = fact[fact['is_delivered'] == 1]
    
    seller_metrics = (
        delivered.groupby('seller_id')
        .agg(
            revenue=('total_item_value', 'sum'),
            orders=('order_id', 'nunique'),
            avg_review=('review_score', 'mean'),
            late_rate=('is_late', 'mean'),
        )
        .reset_index()
    )
    seller_metrics = seller_metrics.merge(
        dim_sellers[['seller_id', 'seller_state']], on='seller_id', how='left'
    )
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Seller Performance Analysis', fontsize=16, fontweight='bold')
    
    # Revenue distribution (log scale)
    ax = axes[0, 0]
    ax.hist(seller_metrics['revenue'], bins=50, color=COLORS['primary'], alpha=0.7, edgecolor='white')
    ax.set_xlabel('Revenue (R$)')
    ax.set_ylabel('Number of Sellers')
    ax.set_title('Seller Revenue Distribution')
    ax.set_xscale('log')
    
    # Orders per seller
    ax = axes[0, 1]
    ax.hist(seller_metrics['orders'].clip(0, 100), bins=40, color=COLORS['secondary'], alpha=0.7, edgecolor='white')
    ax.set_xlabel('Number of Orders')
    ax.set_ylabel('Number of Sellers')
    ax.set_title('Orders per Seller Distribution')
    
    # Top 10 seller states
    ax = axes[1, 0]
    state_sellers = seller_metrics.groupby('seller_state').size().sort_values(ascending=True).tail(10)
    ax.barh(state_sellers.index, state_sellers.values, color=plt.cm.cool(np.linspace(0.3, 0.9, len(state_sellers))))
    ax.set_xlabel('Number of Sellers')
    ax.set_title('Top 10 States by Seller Count')
    
    # Review vs Late Rate scatter
    ax = axes[1, 1]
    sellers_gt5 = seller_metrics[seller_metrics['orders'] >= 5]
    scatter = ax.scatter(sellers_gt5['late_rate'] * 100, sellers_gt5['avg_review'],
                         c=np.log10(sellers_gt5['revenue'] + 1), cmap='YlOrRd',
                         alpha=0.5, s=20)
    ax.set_xlabel('Late Delivery Rate (%)')
    ax.set_ylabel('Average Review Score')
    ax.set_title('Seller Review vs Late Rate (≥5 orders)')
    plt.colorbar(scatter, ax=ax, label='log₁₀(Revenue)')
    
    plt.tight_layout()
    save_fig(fig, '07_seller_analysis')


# ============================================================
# 9. CUSTOMER GEOGRAPHY
# ============================================================

def plot_customer_geography(dim_customers):
    """Customer distribution by state."""
    print("  Plotting customer geography...")
    
    state_counts = dim_customers['customer_state'].value_counts().sort_values(ascending=True).tail(15)
    
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = plt.cm.Blues(np.linspace(0.3, 0.9, len(state_counts)))
    ax.barh(state_counts.index, state_counts.values, color=colors)
    ax.set_xlabel('Number of Customers', fontsize=12)
    ax.set_title('Customer Distribution by State (Top 15)', fontsize=16, fontweight='bold')
    
    # Add percentage labels
    total = dim_customers['customer_state'].notna().sum()
    for i, (state, count) in enumerate(state_counts.items()):
        ax.text(count + total * 0.005, i, f'{count:,} ({count*100/total:.1f}%)',
                va='center', fontsize=9)
    
    plt.tight_layout()
    save_fig(fig, '08_customer_geography')


# ============================================================
# 10. CORRELATION HEATMAP
# ============================================================

def plot_correlation_heatmap(fact):
    """Correlation heatmap of key numeric features."""
    print("  Plotting correlation heatmap...")
    
    delivered = fact[fact['is_delivered'] == 1]
    
    numeric_cols = [
        'price', 'freight_value', 'total_item_value',
        'delivery_days', 'estimated_delivery_days', 'delivery_delay_days',
        'review_score', 'payment_installments', 'review_comment_length'
    ]
    
    corr = delivered[numeric_cols].corr()
    
    fig, ax = plt.subplots(figsize=(10, 8))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r',
                center=0, square=True, linewidths=1, ax=ax,
                vmin=-1, vmax=1)
    ax.set_title('Feature Correlation Heatmap', fontsize=16, fontweight='bold')
    
    plt.tight_layout()
    save_fig(fig, '09_correlation_heatmap')


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  Exploratory Data Analysis (EDA)")
    print("=" * 60)
    
    fact, dim_customers, dim_products, dim_sellers, dim_date = load_data()
    
    dataset_overview(fact, dim_customers, dim_products, dim_sellers)
    plot_order_volume(fact)
    plot_category_revenue(fact, dim_products)
    plot_state_revenue(fact, dim_customers)
    plot_delivery_distribution(fact)
    plot_review_scores(fact)
    plot_payment_methods(fact)
    plot_seller_analysis(fact, dim_sellers)
    plot_customer_geography(dim_customers)
    plot_correlation_heatmap(fact)
    
    print("\n" + "=" * 60)
    print(f"  ✅ EDA COMPLETE — All charts saved to: {FIGURES_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()
