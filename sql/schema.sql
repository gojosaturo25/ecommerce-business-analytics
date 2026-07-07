-- ============================================================
-- E-Commerce Data Warehouse — Star Schema
-- Database: SQLite (compatible with PostgreSQL/MySQL with minor type changes)
-- Grain: fact_orders is at the ORDER-ITEM level
-- ============================================================

-- ============================================================
-- DIMENSION TABLES
-- ============================================================

-- dim_customers: One row per unique customer
CREATE TABLE IF NOT EXISTS dim_customers (
    customer_unique_id    TEXT PRIMARY KEY,
    customer_city         TEXT,
    customer_state        TEXT,
    first_order_date      TEXT,      -- ISO date string
    total_orders          INTEGER,
    total_spent           REAL
);

-- dim_products: One row per product
CREATE TABLE IF NOT EXISTS dim_products (
    product_id                TEXT PRIMARY KEY,
    product_category          TEXT,       -- English category name
    product_category_original TEXT,       -- Original Portuguese name
    product_weight_g          REAL,
    product_length_cm         REAL,
    product_height_cm         REAL,
    product_width_cm          REAL,
    product_volume_cm3        REAL,       -- Derived: L × W × H
    product_photos_qty        INTEGER,
    product_name_length       INTEGER,
    product_description_length INTEGER
);

-- dim_sellers: One row per seller
CREATE TABLE IF NOT EXISTS dim_sellers (
    seller_id       TEXT PRIMARY KEY,
    seller_city     TEXT,
    seller_state    TEXT,
    total_items_sold INTEGER,
    total_revenue    REAL,
    avg_review_score REAL
);

-- dim_date: Calendar dimension covering the order date range
CREATE TABLE IF NOT EXISTS dim_date (
    date_key        TEXT PRIMARY KEY,   -- 'YYYY-MM-DD'
    year            INTEGER,
    month           INTEGER,
    day             INTEGER,
    day_of_week     INTEGER,            -- 0=Monday ... 6=Sunday
    day_name        TEXT,               -- 'Monday', 'Tuesday', etc.
    month_name      TEXT,               -- 'January', 'February', etc.
    quarter         INTEGER,            -- 1, 2, 3, 4
    is_weekend      INTEGER             -- 0 or 1
);


-- ============================================================
-- FACT TABLE
-- ============================================================

-- fact_orders: One row per order-item (an order can have multiple items)
CREATE TABLE IF NOT EXISTS fact_orders (
    order_id                    TEXT,
    order_item_id               INTEGER,
    customer_unique_id          TEXT,
    product_id                  TEXT,
    seller_id                   TEXT,
    order_date_key              TEXT,       -- FK to dim_date
    
    -- Order status & timestamps
    order_status                TEXT,
    order_purchase_timestamp    TEXT,
    order_approved_at           TEXT,
    order_delivered_carrier_date TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT,
    
    -- Financials
    price                       REAL,
    freight_value               REAL,
    total_item_value            REAL,       -- price + freight_value
    payment_type                TEXT,       -- Most common payment type for the order
    payment_installments        INTEGER,
    payment_value               REAL,       -- Total payment for the order
    
    -- Delivery metrics (derived)
    delivery_days               REAL,       -- Actual: delivered - purchased (days)
    estimated_delivery_days     REAL,       -- Estimated: estimated - purchased (days)
    delivery_delay_days         REAL,       -- delivered - estimated (positive = late)
    is_late                     INTEGER,    -- 1 if delivered after estimate, else 0
    is_delivered                INTEGER,    -- 1 if order_status = 'delivered'
    
    -- Review
    review_score                INTEGER,    -- 1 to 5
    review_comment_length       INTEGER,    -- Length of review comment (0 if none)
    
    -- Composite primary key
    PRIMARY KEY (order_id, order_item_id),
    
    -- Foreign keys (enforced in SQLite with PRAGMA foreign_keys = ON)
    FOREIGN KEY (customer_unique_id) REFERENCES dim_customers(customer_unique_id),
    FOREIGN KEY (product_id)         REFERENCES dim_products(product_id),
    FOREIGN KEY (seller_id)          REFERENCES dim_sellers(seller_id),
    FOREIGN KEY (order_date_key)     REFERENCES dim_date(date_key)
);


-- ============================================================
-- INDEXES for query performance
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_fact_orders_customer  ON fact_orders(customer_unique_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_product   ON fact_orders(product_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_seller    ON fact_orders(seller_id);
CREATE INDEX IF NOT EXISTS idx_fact_orders_date      ON fact_orders(order_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_orders_status    ON fact_orders(order_status);
CREATE INDEX IF NOT EXISTS idx_fact_orders_late      ON fact_orders(is_late);
CREATE INDEX IF NOT EXISTS idx_fact_orders_category  ON fact_orders(product_id, price);
CREATE INDEX IF NOT EXISTS idx_dim_date_yearmonth    ON dim_date(year, month);
