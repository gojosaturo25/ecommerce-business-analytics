-- ============================================================
-- Business Metrics Queries
-- E-Commerce Data Warehouse
-- ============================================================
-- Usage: sqlite3 -header -column data/processed/ecommerce.db < sql/queries/metrics.sql
-- ============================================================


-- ============================================================
-- 1. GMV (Gross Merchandise Value) — Overall
-- ============================================================
SELECT '=== 1. OVERALL GMV ===' AS section;

SELECT 
    COUNT(DISTINCT order_id)                         AS total_orders,
    SUM(total_item_value)                            AS total_gmv,
    ROUND(SUM(price), 2)                             AS total_product_revenue,
    ROUND(SUM(freight_value), 2)                     AS total_freight_revenue,
    ROUND(AVG(total_item_value), 2)                  AS avg_order_item_value
FROM fact_orders
WHERE is_delivered = 1;


-- ============================================================
-- 2. Monthly GMV Trend
-- ============================================================
SELECT '=== 2. MONTHLY GMV TREND ===' AS section;

SELECT 
    SUBSTR(order_date_key, 1, 7)                     AS year_month,
    COUNT(DISTINCT order_id)                          AS orders,
    ROUND(SUM(total_item_value), 2)                  AS gmv,
    ROUND(AVG(total_item_value), 2)                  AS avg_item_value,
    -- Month-over-month growth (using LAG)
    ROUND(
        (SUM(total_item_value) - LAG(SUM(total_item_value)) OVER (ORDER BY SUBSTR(order_date_key, 1, 7)))
        / NULLIF(LAG(SUM(total_item_value)) OVER (ORDER BY SUBSTR(order_date_key, 1, 7)), 0) * 100,
        1
    )                                                 AS mom_growth_pct
FROM fact_orders
WHERE is_delivered = 1
GROUP BY SUBSTR(order_date_key, 1, 7)
ORDER BY year_month;


-- ============================================================
-- 3. Average Order Value (AOV)
-- ============================================================
SELECT '=== 3. AVERAGE ORDER VALUE ===' AS section;

WITH order_totals AS (
    SELECT 
        order_id,
        SUM(total_item_value) AS order_total
    FROM fact_orders
    WHERE is_delivered = 1
    GROUP BY order_id
)
SELECT 
    COUNT(*)                                          AS total_orders,
    ROUND(AVG(order_total), 2)                        AS aov,
    ROUND(MIN(order_total), 2)                        AS min_order,
    ROUND(MAX(order_total), 2)                        AS max_order,
    ROUND(AVG(order_total) - 
          (SELECT AVG(order_total) FROM order_totals), 2) AS deviation_from_mean
FROM order_totals;


-- ============================================================
-- 4. Repeat Purchase Rate
-- ============================================================
SELECT '=== 4. REPEAT PURCHASE RATE ===' AS section;

WITH customer_orders AS (
    SELECT 
        customer_unique_id,
        COUNT(DISTINCT order_id) AS order_count
    FROM fact_orders
    WHERE is_delivered = 1
    GROUP BY customer_unique_id
)
SELECT 
    COUNT(*)                                          AS total_customers,
    SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(
        SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 
        2
    )                                                  AS repeat_purchase_rate_pct,
    ROUND(AVG(order_count), 2)                         AS avg_orders_per_customer,
    MAX(order_count)                                   AS max_orders_by_customer
FROM customer_orders;


-- ============================================================
-- 5. Category-wise Revenue Ranking
-- ============================================================
SELECT '=== 5. CATEGORY REVENUE RANKING ===' AS section;

SELECT 
    p.product_category,
    COUNT(DISTINCT f.order_id)                        AS orders,
    ROUND(SUM(f.total_item_value), 2)                 AS revenue,
    ROUND(AVG(f.review_score), 2)                     AS avg_review,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_delivery_pct,
    RANK() OVER (ORDER BY SUM(f.total_item_value) DESC) AS revenue_rank
FROM fact_orders f
JOIN dim_products p ON f.product_id = p.product_id
WHERE f.is_delivered = 1
GROUP BY p.product_category
ORDER BY revenue DESC
LIMIT 20;


-- ============================================================
-- 6. On-Time Delivery Rate
-- ============================================================
SELECT '=== 6. DELIVERY PERFORMANCE ===' AS section;

SELECT 
    COUNT(DISTINCT order_id)                          AS delivered_orders,
    SUM(CASE WHEN is_late = 0 THEN 1 ELSE 0 END)     AS on_time_items,
    SUM(CASE WHEN is_late = 1 THEN 1 ELSE 0 END)     AS late_items,
    ROUND(
        SUM(CASE WHEN is_late = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    )                                                  AS on_time_rate_pct,
    ROUND(AVG(delivery_days), 1)                       AS avg_delivery_days,
    ROUND(AVG(delivery_delay_days), 1)                 AS avg_delay_days,
    ROUND(AVG(CASE WHEN is_late = 1 THEN delivery_delay_days END), 1) AS avg_late_delay_days
FROM fact_orders
WHERE is_delivered = 1
  AND delivery_days IS NOT NULL;


-- ============================================================
-- 7. Delivery Delay by Customer State
-- ============================================================
SELECT '=== 7. DELIVERY BY STATE ===' AS section;

SELECT 
    c.customer_state,
    COUNT(DISTINCT f.order_id)                        AS orders,
    ROUND(AVG(f.delivery_days), 1)                    AS avg_delivery_days,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_pct,
    ROUND(AVG(CASE WHEN f.is_late = 1 THEN f.delivery_delay_days END), 1) AS avg_late_delay,
    ROUND(AVG(f.review_score), 2)                     AS avg_review
FROM fact_orders f
JOIN dim_customers c ON f.customer_unique_id = c.customer_unique_id
WHERE f.is_delivered = 1
  AND f.delivery_days IS NOT NULL
GROUP BY c.customer_state
ORDER BY late_pct DESC;


-- ============================================================
-- 8. Seller Performance Ranking
-- ============================================================
SELECT '=== 8. TOP 20 SELLERS ===' AS section;

SELECT 
    f.seller_id,
    s.seller_city,
    s.seller_state,
    COUNT(DISTINCT f.order_id)                        AS orders,
    COUNT(f.order_item_id)                            AS items_sold,
    ROUND(SUM(f.total_item_value), 2)                 AS revenue,
    ROUND(AVG(f.review_score), 2)                     AS avg_review,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_pct,
    ROUND(AVG(f.delivery_days), 1)                    AS avg_delivery_days,
    RANK() OVER (ORDER BY SUM(f.total_item_value) DESC) AS revenue_rank
FROM fact_orders f
JOIN dim_sellers s ON f.seller_id = s.seller_id
WHERE f.is_delivered = 1
GROUP BY f.seller_id, s.seller_city, s.seller_state
ORDER BY revenue DESC
LIMIT 20;


-- ============================================================
-- 9. Payment Method Breakdown
-- ============================================================
SELECT '=== 9. PAYMENT METHODS ===' AS section;

SELECT 
    payment_type,
    COUNT(DISTINCT order_id)                          AS orders,
    ROUND(SUM(total_item_value), 2)                   AS revenue,
    ROUND(AVG(payment_installments), 1)               AS avg_installments,
    ROUND(
        COUNT(DISTINCT order_id) * 100.0 / 
        (SELECT COUNT(DISTINCT order_id) FROM fact_orders WHERE is_delivered = 1),
        1
    )                                                  AS pct_of_orders
FROM fact_orders
WHERE is_delivered = 1
GROUP BY payment_type
ORDER BY orders DESC;


-- ============================================================
-- 10. Monthly New vs Returning Customers
-- ============================================================
SELECT '=== 10. NEW vs RETURNING CUSTOMERS ===' AS section;

WITH customer_first_month AS (
    SELECT 
        customer_unique_id,
        MIN(SUBSTR(order_date_key, 1, 7)) AS first_month
    FROM fact_orders
    WHERE is_delivered = 1
    GROUP BY customer_unique_id
),
monthly_customers AS (
    SELECT 
        SUBSTR(f.order_date_key, 1, 7) AS year_month,
        f.customer_unique_id,
        cfm.first_month
    FROM fact_orders f
    JOIN customer_first_month cfm ON f.customer_unique_id = cfm.customer_unique_id
    WHERE f.is_delivered = 1
    GROUP BY SUBSTR(f.order_date_key, 1, 7), f.customer_unique_id, cfm.first_month
)
SELECT 
    year_month,
    COUNT(DISTINCT customer_unique_id)                AS total_customers,
    SUM(CASE WHEN year_month = first_month THEN 1 ELSE 0 END) AS new_customers,
    SUM(CASE WHEN year_month != first_month THEN 1 ELSE 0 END) AS returning_customers,
    ROUND(
        SUM(CASE WHEN year_month != first_month THEN 1 ELSE 0 END) * 100.0 / 
        COUNT(DISTINCT customer_unique_id), 1
    )                                                  AS returning_pct
FROM monthly_customers
GROUP BY year_month
ORDER BY year_month;
