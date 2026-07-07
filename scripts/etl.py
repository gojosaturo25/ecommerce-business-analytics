"""
ETL Pipeline: Olist Raw CSVs → SQLite Star Schema
===================================================

Reads 9 Olist CSV files from data/raw/, cleans and transforms data,
builds a star schema (fact_orders + 4 dimension tables), and loads
everything into a SQLite database at data/processed/ecommerce.db.

Also exports cleaned/aggregated CSVs for Power BI and Excel use.

Usage:
    python scripts/etl.py
"""

import os
import sys
import sqlite3
import warnings
from datetime import datetime

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')
PROCESSED_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
DASHBOARD_DIR = os.path.join(PROJECT_ROOT, 'dashboard', 'data')
DB_PATH = os.path.join(PROCESSED_DIR, 'ecommerce.db')
SCHEMA_PATH = os.path.join(PROJECT_ROOT, 'sql', 'schema.sql')

# Expected raw CSV files
EXPECTED_FILES = [
    'olist_customers_dataset.csv',
    'olist_orders_dataset.csv',
    'olist_order_items_dataset.csv',
    'olist_order_payments_dataset.csv',
    'olist_order_reviews_dataset.csv',
    'olist_products_dataset.csv',
    'olist_sellers_dataset.csv',
    'olist_geolocation_dataset.csv',
    'product_category_name_translation.csv',
]


def log(msg):
    """Simple timestamped logging."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ============================================================
# STEP 1: LOAD RAW DATA
# ============================================================

def load_raw_data():
    """Load all Olist CSVs into a dictionary of DataFrames."""
    log("Loading raw CSV files...")
    
    # Check all files exist
    missing = [f for f in EXPECTED_FILES if not os.path.exists(os.path.join(RAW_DIR, f))]
    if missing:
        print(f"\n❌ ERROR: Missing files in {RAW_DIR}:")
        for f in missing:
            print(f"   - {f}")
        print(f"\nPlease download the Olist dataset from Kaggle and place CSVs in: {RAW_DIR}")
        sys.exit(1)
    
    data = {}
    data['customers']    = pd.read_csv(os.path.join(RAW_DIR, 'olist_customers_dataset.csv'))
    data['orders']       = pd.read_csv(os.path.join(RAW_DIR, 'olist_orders_dataset.csv'))
    data['order_items']  = pd.read_csv(os.path.join(RAW_DIR, 'olist_order_items_dataset.csv'))
    data['payments']     = pd.read_csv(os.path.join(RAW_DIR, 'olist_order_payments_dataset.csv'))
    data['reviews']      = pd.read_csv(os.path.join(RAW_DIR, 'olist_order_reviews_dataset.csv'))
    data['products']     = pd.read_csv(os.path.join(RAW_DIR, 'olist_products_dataset.csv'))
    data['sellers']      = pd.read_csv(os.path.join(RAW_DIR, 'olist_sellers_dataset.csv'))
    data['geolocation']  = pd.read_csv(os.path.join(RAW_DIR, 'olist_geolocation_dataset.csv'))
    data['category_translation'] = pd.read_csv(os.path.join(RAW_DIR, 'product_category_name_translation.csv'))
    
    for name, df in data.items():
        log(f"  {name}: {df.shape[0]:,} rows × {df.shape[1]} cols")
    
    return data


# ============================================================
# STEP 2: CLEAN & TRANSFORM
# ============================================================

def clean_orders(orders_df):
    """Parse timestamps and filter to delivered orders for analysis."""
    log("Cleaning orders...")
    
    date_cols = [
        'order_purchase_timestamp', 'order_approved_at',
        'order_delivered_carrier_date', 'order_delivered_customer_date',
        'order_estimated_delivery_date'
    ]
    for col in date_cols:
        orders_df[col] = pd.to_datetime(orders_df[col], errors='coerce')
    
    # Add date key (YYYY-MM-DD) for the purchase date
    orders_df['order_date_key'] = orders_df['order_purchase_timestamp'].dt.strftime('%Y-%m-%d')
    
    return orders_df


def clean_products(products_df, translation_df):
    """Add English category names and compute volume."""
    log("Cleaning products...")
    
    # Merge with translation
    products_df = products_df.merge(
        translation_df,
        on='product_category_name',
        how='left'
    )
    
    # Rename columns
    products_df = products_df.rename(columns={
        'product_category_name': 'product_category_original',
        'product_category_name_english': 'product_category'
    })
    
    # Fill missing category names
    products_df['product_category'] = products_df['product_category'].fillna('unknown')
    products_df['product_category_original'] = products_df['product_category_original'].fillna('unknown')
    
    # Fix Olist typos in column names ('lenght' → 'length')
    products_df = products_df.rename(columns={
        'product_name_lenght': 'product_name_length',
        'product_description_lenght': 'product_description_length',
    })
    
    # Compute volume
    products_df['product_volume_cm3'] = (
        products_df['product_length_cm'].fillna(0) *
        products_df['product_height_cm'].fillna(0) *
        products_df['product_width_cm'].fillna(0)
    )
    
    return products_df


def clean_reviews(reviews_df):
    """Clean reviews: deduplicate per order (take first review)."""
    log("Cleaning reviews...")
    
    # Some orders have multiple reviews — keep the first one
    reviews_df = reviews_df.sort_values('review_creation_date').drop_duplicates(
        subset='order_id', keep='first'
    )
    
    # Compute review comment length
    reviews_df['review_comment_length'] = (
        reviews_df['review_comment_message']
        .fillna('')
        .str.len()
        .astype(int)
    )
    
    return reviews_df[['order_id', 'review_score', 'review_comment_length']]


def aggregate_payments(payments_df):
    """Aggregate payments per order (total value, most common type, max installments)."""
    log("Aggregating payments...")
    
    # Most common payment type per order
    payment_type = (
        payments_df.groupby('order_id')['payment_type']
        .agg(lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'unknown')
        .reset_index()
    )
    
    payment_agg = (
        payments_df.groupby('order_id')
        .agg(
            payment_value=('payment_value', 'sum'),
            payment_installments=('payment_installments', 'max')
        )
        .reset_index()
    )
    
    return payment_agg.merge(payment_type, on='order_id', how='left')


# ============================================================
# STEP 3: BUILD FACT & DIMENSION TABLES
# ============================================================

def build_fact_orders(data):
    """Build the fact_orders table by joining all sources."""
    log("Building fact_orders...")
    
    orders = data['orders']
    items = data['order_items']
    customers = data['customers']
    reviews = data['reviews']
    payments = data['payments']
    products = data['products']
    
    # Start with order_items as the grain
    fact = items.merge(orders, on='order_id', how='inner')
    
    # Join customer_unique_id via customer_id
    customer_map = customers[['customer_id', 'customer_unique_id']].drop_duplicates()
    fact = fact.merge(customer_map, on='customer_id', how='left')
    
    # Join reviews
    fact = fact.merge(reviews, on='order_id', how='left')
    
    # Join payments
    fact = fact.merge(payments, on='order_id', how='left')
    
    # Compute derived delivery metrics
    fact['total_item_value'] = fact['price'] + fact['freight_value']
    
    fact['delivery_days'] = (
        (fact['order_delivered_customer_date'] - fact['order_purchase_timestamp'])
        .dt.total_seconds() / 86400
    ).round(2)
    
    fact['estimated_delivery_days'] = (
        (fact['order_estimated_delivery_date'] - fact['order_purchase_timestamp'])
        .dt.total_seconds() / 86400
    ).round(2)
    
    fact['delivery_delay_days'] = (
        (fact['order_delivered_customer_date'] - fact['order_estimated_delivery_date'])
        .dt.total_seconds() / 86400
    ).round(2)
    
    fact['is_late'] = (fact['delivery_delay_days'] > 0).astype(int)
    fact['is_delivered'] = (fact['order_status'] == 'delivered').astype(int)
    
    # Convert timestamps to ISO strings for SQLite storage
    timestamp_cols = [
        'order_purchase_timestamp', 'order_approved_at',
        'order_delivered_carrier_date', 'order_delivered_customer_date',
        'order_estimated_delivery_date'
    ]
    for col in timestamp_cols:
        fact[col] = fact[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Select final columns
    fact_columns = [
        'order_id', 'order_item_id', 'customer_unique_id', 'product_id',
        'seller_id', 'order_date_key', 'order_status',
        'order_purchase_timestamp', 'order_approved_at',
        'order_delivered_carrier_date', 'order_delivered_customer_date',
        'order_estimated_delivery_date',
        'price', 'freight_value', 'total_item_value',
        'payment_type', 'payment_installments', 'payment_value',
        'delivery_days', 'estimated_delivery_days', 'delivery_delay_days',
        'is_late', 'is_delivered',
        'review_score', 'review_comment_length'
    ]
    
    fact = fact[fact_columns]
    
    log(f"  fact_orders: {fact.shape[0]:,} rows")
    return fact


def build_dim_customers(data):
    """Build dim_customers from customers + computed aggregates."""
    log("Building dim_customers...")
    
    customers = data['customers']
    orders = data['orders']
    items = data['order_items']
    
    # Get unique customer info
    dim = (
        customers[['customer_unique_id', 'customer_city', 'customer_state']]
        .drop_duplicates(subset='customer_unique_id', keep='first')
    )
    
    # Compute aggregates per unique customer
    order_customer = orders.merge(
        customers[['customer_id', 'customer_unique_id']], on='customer_id'
    )
    order_items = order_customer.merge(items[['order_id', 'price', 'freight_value']], on='order_id')
    
    agg = (
        order_items.groupby('customer_unique_id')
        .agg(
            first_order_date=('order_purchase_timestamp', 'min'),
            total_orders=('order_id', 'nunique'),
            total_spent=('price', 'sum')
        )
        .reset_index()
    )
    agg['first_order_date'] = pd.to_datetime(agg['first_order_date']).dt.strftime('%Y-%m-%d')
    agg['total_spent'] = agg['total_spent'].round(2)
    
    dim = dim.merge(agg, on='customer_unique_id', how='left')
    
    log(f"  dim_customers: {dim.shape[0]:,} rows")
    return dim


def build_dim_products(data):
    """Build dim_products."""
    log("Building dim_products...")
    
    products = data['products']
    
    dim = products[[
        'product_id', 'product_category', 'product_category_original',
        'product_weight_g', 'product_length_cm', 'product_height_cm',
        'product_width_cm', 'product_volume_cm3', 'product_photos_qty',
        'product_name_length', 'product_description_length'
    ]].drop_duplicates(subset='product_id', keep='first')
    
    log(f"  dim_products: {dim.shape[0]:,} rows")
    return dim


def build_dim_sellers(data):
    """Build dim_sellers with performance aggregates."""
    log("Building dim_sellers...")
    
    sellers = data['sellers']
    items = data['order_items']
    orders = data['orders']
    reviews = data['reviews']
    
    dim = sellers[['seller_id', 'seller_city', 'seller_state']].drop_duplicates(
        subset='seller_id', keep='first'
    )
    
    # Compute seller metrics
    seller_items = items.merge(orders[['order_id', 'order_status']], on='order_id')
    
    item_agg = (
        seller_items.groupby('seller_id')
        .agg(
            total_items_sold=('order_item_id', 'count'),
            total_revenue=('price', 'sum')
        )
        .reset_index()
    )
    item_agg['total_revenue'] = item_agg['total_revenue'].round(2)
    
    # Average review score per seller
    seller_reviews = items[['order_id', 'seller_id']].merge(reviews, on='order_id')
    review_agg = (
        seller_reviews.groupby('seller_id')['review_score']
        .mean()
        .round(2)
        .reset_index()
        .rename(columns={'review_score': 'avg_review_score'})
    )
    
    dim = dim.merge(item_agg, on='seller_id', how='left')
    dim = dim.merge(review_agg, on='seller_id', how='left')
    
    log(f"  dim_sellers: {dim.shape[0]:,} rows")
    return dim


def build_dim_date(data):
    """Build dim_date calendar dimension covering the order date range."""
    log("Building dim_date...")
    
    orders = data['orders']
    min_date = orders['order_purchase_timestamp'].min()
    max_date = orders['order_purchase_timestamp'].max()
    
    if pd.isna(min_date) or pd.isna(max_date):
        # Fallback
        min_date = pd.Timestamp('2016-01-01')
        max_date = pd.Timestamp('2018-12-31')
    
    dates = pd.date_range(start=min_date.normalize(), end=max_date.normalize(), freq='D')
    
    dim = pd.DataFrame({
        'date_key': dates.strftime('%Y-%m-%d'),
        'year': dates.year,
        'month': dates.month,
        'day': dates.day,
        'day_of_week': dates.dayofweek,
        'day_name': dates.day_name(),
        'month_name': dates.month_name(),
        'quarter': dates.quarter,
        'is_weekend': (dates.dayofweek >= 5).astype(int),
    })
    
    log(f"  dim_date: {dim.shape[0]:,} rows ({dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')})")
    return dim


# ============================================================
# STEP 4: LOAD TO SQLITE
# ============================================================

def load_to_sqlite(tables):
    """Load all tables into the SQLite database."""
    log(f"Loading to SQLite: {DB_PATH}")
    
    # Remove existing DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Create schema
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Load each table
    for table_name, df in tables.items():
        log(f"  Loading {table_name}: {df.shape[0]:,} rows...")
        df.to_sql(table_name, conn, if_exists='replace', index=False)
    
    # Verify row counts
    log("\nVerification — row counts:")
    for table_name in tables.keys():
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        log(f"  {table_name}: {count:,}")
    
    conn.close()
    log("SQLite load complete ✓")


# ============================================================
# STEP 5: EXPORT CSVS FOR DASHBOARD & EXCEL
# ============================================================

def export_csvs(tables):
    """Export processed tables as CSVs for Power BI and Excel."""
    log("Exporting processed CSVs...")
    
    # Export main tables
    for table_name, df in tables.items():
        path = os.path.join(PROCESSED_DIR, f"{table_name}.csv")
        df.to_csv(path, index=False)
        log(f"  Exported: {path}")
    
    # Create dashboard-specific aggregations
    fact = tables['fact_orders']
    fact_dt = fact.copy()
    fact_dt['order_purchase_timestamp'] = pd.to_datetime(fact_dt['order_purchase_timestamp'])
    fact_dt['year_month'] = fact_dt['order_purchase_timestamp'].dt.to_period('M').astype(str)
    
    # Monthly KPIs
    monthly = (
        fact_dt[fact_dt['is_delivered'] == 1]
        .groupby('year_month')
        .agg(
            total_gmv=('total_item_value', 'sum'),
            total_orders=('order_id', 'nunique'),
            avg_order_value=('total_item_value', 'mean'),
            on_time_rate=('is_late', lambda x: 1 - x.mean()),
            avg_delivery_days=('delivery_days', 'mean'),
            avg_review_score=('review_score', 'mean'),
        )
        .round(2)
        .reset_index()
    )
    monthly.to_csv(os.path.join(DASHBOARD_DIR, 'monthly_kpis.csv'), index=False)
    log(f"  Exported: dashboard/data/monthly_kpis.csv")
    
    # Category breakdown
    dim_products = tables['dim_products']
    fact_with_cat = fact_dt.merge(dim_products[['product_id', 'product_category']], on='product_id', how='left')
    
    category = (
        fact_with_cat[fact_with_cat['is_delivered'] == 1]
        .groupby('product_category')
        .agg(
            revenue=('total_item_value', 'sum'),
            order_count=('order_id', 'nunique'),
            avg_review=('review_score', 'mean'),
            late_rate=('is_late', 'mean'),
        )
        .round(2)
        .reset_index()
        .sort_values('revenue', ascending=False)
    )
    category.to_csv(os.path.join(DASHBOARD_DIR, 'category_breakdown.csv'), index=False)
    log(f"  Exported: dashboard/data/category_breakdown.csv")
    
    # Regional delivery stats
    dim_customers = tables['dim_customers']
    fact_with_state = fact_dt.merge(
        dim_customers[['customer_unique_id', 'customer_state']], 
        on='customer_unique_id', how='left'
    )
    
    regional = (
        fact_with_state[fact_with_state['is_delivered'] == 1]
        .groupby('customer_state')
        .agg(
            total_orders=('order_id', 'nunique'),
            avg_delivery_days=('delivery_days', 'mean'),
            late_rate=('is_late', 'mean'),
            avg_review=('review_score', 'mean'),
            total_revenue=('total_item_value', 'sum'),
        )
        .round(2)
        .reset_index()
        .sort_values('total_orders', ascending=False)
    )
    regional.to_csv(os.path.join(DASHBOARD_DIR, 'regional_delivery.csv'), index=False)
    log(f"  Exported: dashboard/data/regional_delivery.csv")
    
    # Seller leaderboard
    seller_board = (
        tables['dim_sellers']
        .sort_values('total_revenue', ascending=False)
        .head(50)
    )
    seller_board.to_csv(os.path.join(DASHBOARD_DIR, 'seller_leaderboard.csv'), index=False)
    log(f"  Exported: dashboard/data/seller_leaderboard.csv")
    
    log("CSV export complete ✓")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  E-Commerce ETL Pipeline")
    print("  Olist Raw CSVs → SQLite Star Schema")
    print("=" * 60)
    print()
    
    # Ensure output directories exist
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    
    # Step 1: Load raw data
    data = load_raw_data()
    
    # Step 2: Clean & transform
    data['orders'] = clean_orders(data['orders'])
    data['products'] = clean_products(data['products'], data['category_translation'])
    data['reviews'] = clean_reviews(data['reviews'])
    data['payments'] = aggregate_payments(data['payments'])
    
    # Step 3: Build star schema tables
    fact_orders = build_fact_orders(data)
    dim_customers = build_dim_customers(data)
    dim_products = build_dim_products(data)
    dim_sellers = build_dim_sellers(data)
    dim_date = build_dim_date(data)
    
    tables = {
        'fact_orders': fact_orders,
        'dim_customers': dim_customers,
        'dim_products': dim_products,
        'dim_sellers': dim_sellers,
        'dim_date': dim_date,
    }
    
    # Step 4: Load to SQLite
    load_to_sqlite(tables)
    
    # Step 5: Export CSVs
    export_csvs(tables)
    
    print()
    print("=" * 60)
    print("  ✅ ETL COMPLETE")
    print(f"  Database: {DB_PATH}")
    print(f"  Processed CSVs: {PROCESSED_DIR}")
    print(f"  Dashboard CSVs: {DASHBOARD_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()
