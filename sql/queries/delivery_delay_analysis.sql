-- ============================================================
-- Delivery Delay Root-Cause Analysis
-- E-Commerce Data Warehouse
-- ============================================================
-- Deep-dive into delivery delays: by state, category, seller,
-- seasonal patterns, and worst-performing corridors.
--
-- Usage: sqlite3 -header -column data/processed/ecommerce.db < sql/queries/delivery_delay_analysis.sql
-- ============================================================


-- ============================================================
-- 1. Overall Delay Distribution
-- ============================================================
SELECT '=== 1. DELAY DISTRIBUTION ===' AS section;

SELECT 
    CASE 
        WHEN delivery_delay_days <= -7 THEN '7+ days early'
        WHEN delivery_delay_days <= -3 THEN '3-7 days early'
        WHEN delivery_delay_days <= 0  THEN '0-3 days early'
        WHEN delivery_delay_days <= 3  THEN '1-3 days late'
        WHEN delivery_delay_days <= 7  THEN '3-7 days late'
        WHEN delivery_delay_days <= 14 THEN '7-14 days late'
        ELSE '14+ days late'
    END                                               AS delay_bucket,
    COUNT(*)                                          AS item_count,
    ROUND(COUNT(*) * 100.0 / (
        SELECT COUNT(*) FROM fact_orders 
        WHERE is_delivered = 1 AND delivery_delay_days IS NOT NULL
    ), 1)                                              AS pct_of_total,
    ROUND(AVG(review_score), 2)                        AS avg_review_in_bucket
FROM fact_orders
WHERE is_delivered = 1
  AND delivery_delay_days IS NOT NULL
GROUP BY delay_bucket
ORDER BY 
    CASE delay_bucket
        WHEN '7+ days early' THEN 1
        WHEN '3-7 days early' THEN 2
        WHEN '0-3 days early' THEN 3
        WHEN '1-3 days late' THEN 4
        WHEN '3-7 days late' THEN 5
        WHEN '7-14 days late' THEN 6
        WHEN '14+ days late' THEN 7
    END;


-- ============================================================
-- 2. Delay by Customer State (Top 15)
-- ============================================================
SELECT '=== 2. DELAY BY CUSTOMER STATE ===' AS section;

SELECT 
    c.customer_state,
    COUNT(DISTINCT f.order_id)                        AS orders,
    ROUND(AVG(f.delivery_days), 1)                    AS avg_delivery_days,
    ROUND(AVG(f.estimated_delivery_days), 1)          AS avg_estimated_days,
    ROUND(AVG(f.delivery_delay_days), 1)              AS avg_delay_days,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_pct,
    ROUND(AVG(f.review_score), 2)                     AS avg_review,
    ROUND(AVG(CASE WHEN f.is_late = 1 THEN f.delivery_delay_days END), 1) AS avg_late_delay
FROM fact_orders f
JOIN dim_customers c ON f.customer_unique_id = c.customer_unique_id
WHERE f.is_delivered = 1
  AND f.delivery_days IS NOT NULL
GROUP BY c.customer_state
HAVING COUNT(DISTINCT f.order_id) >= 100
ORDER BY late_pct DESC
LIMIT 15;


-- ============================================================
-- 3. Delay by Product Category (Top 15)
-- ============================================================
SELECT '=== 3. DELAY BY CATEGORY ===' AS section;

SELECT 
    p.product_category,
    COUNT(DISTINCT f.order_id)                        AS orders,
    ROUND(AVG(f.delivery_days), 1)                    AS avg_delivery_days,
    ROUND(AVG(f.delivery_delay_days), 1)              AS avg_delay_days,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_pct,
    ROUND(AVG(f.review_score), 2)                     AS avg_review,
    ROUND(AVG(p.product_weight_g), 0)                 AS avg_weight_g,
    ROUND(AVG(p.product_volume_cm3), 0)               AS avg_volume_cm3
FROM fact_orders f
JOIN dim_products p ON f.product_id = p.product_id
WHERE f.is_delivered = 1
  AND f.delivery_days IS NOT NULL
GROUP BY p.product_category
HAVING COUNT(DISTINCT f.order_id) >= 50
ORDER BY late_pct DESC
LIMIT 15;


-- ============================================================
-- 4. Delay by Seller Performance Tier
-- ============================================================
SELECT '=== 4. DELAY BY SELLER TIER ===' AS section;

WITH seller_metrics AS (
    SELECT 
        seller_id,
        COUNT(DISTINCT order_id)     AS orders,
        AVG(is_late)                 AS late_rate,
        AVG(delivery_days)           AS avg_delivery,
        AVG(review_score)            AS avg_review,
        SUM(total_item_value)        AS revenue
    FROM fact_orders
    WHERE is_delivered = 1
      AND delivery_days IS NOT NULL
    GROUP BY seller_id
    HAVING COUNT(DISTINCT order_id) >= 5
),
seller_tiered AS (
    SELECT *,
        NTILE(4) OVER (ORDER BY late_rate ASC) AS performance_quartile
    FROM seller_metrics
)

SELECT 
    CASE performance_quartile
        WHEN 1 THEN 'Q1 - Best (lowest delay rate)'
        WHEN 2 THEN 'Q2 - Good'
        WHEN 3 THEN 'Q3 - Below Average'
        WHEN 4 THEN 'Q4 - Worst (highest delay rate)'
    END                                               AS seller_tier,
    COUNT(*)                                          AS seller_count,
    ROUND(AVG(late_rate) * 100, 1)                    AS avg_late_pct,
    ROUND(AVG(avg_delivery), 1)                       AS avg_delivery_days,
    ROUND(AVG(avg_review), 2)                         AS avg_review,
    ROUND(SUM(revenue), 2)                            AS total_revenue,
    ROUND(AVG(orders), 0)                             AS avg_orders_per_seller
FROM seller_tiered
GROUP BY performance_quartile
ORDER BY performance_quartile;


-- ============================================================
-- 5. Seasonal Delay Patterns (by Month)
-- ============================================================
SELECT '=== 5. SEASONAL DELAY PATTERN ===' AS section;

SELECT 
    d.month,
    d.month_name,
    COUNT(DISTINCT f.order_id)                        AS orders,
    ROUND(AVG(f.delivery_days), 1)                    AS avg_delivery_days,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_pct,
    ROUND(AVG(f.review_score), 2)                     AS avg_review
FROM fact_orders f
JOIN dim_date d ON f.order_date_key = d.date_key
WHERE f.is_delivered = 1
  AND f.delivery_days IS NOT NULL
GROUP BY d.month, d.month_name
ORDER BY d.month;


-- ============================================================
-- 6. Day of Week Effect
-- ============================================================
SELECT '=== 6. DAY OF WEEK EFFECT ===' AS section;

SELECT 
    d.day_name,
    d.day_of_week,
    COUNT(DISTINCT f.order_id)                        AS orders,
    ROUND(AVG(f.delivery_days), 1)                    AS avg_delivery_days,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_pct,
    ROUND(AVG(f.review_score), 2)                     AS avg_review
FROM fact_orders f
JOIN dim_date d ON f.order_date_key = d.date_key
WHERE f.is_delivered = 1
  AND f.delivery_days IS NOT NULL
GROUP BY d.day_name, d.day_of_week
ORDER BY d.day_of_week;


-- ============================================================
-- 7. Worst-Performing Corridors (Seller State → Customer State)
-- ============================================================
SELECT '=== 7. WORST DELIVERY CORRIDORS ===' AS section;

SELECT 
    s.seller_state                                    AS from_state,
    c.customer_state                                  AS to_state,
    COUNT(DISTINCT f.order_id)                        AS orders,
    ROUND(AVG(f.delivery_days), 1)                    AS avg_delivery_days,
    ROUND(AVG(f.delivery_delay_days), 1)              AS avg_delay_days,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_pct,
    ROUND(AVG(f.review_score), 2)                     AS avg_review,
    -- Compare to overall average
    ROUND(
        AVG(f.delivery_days) - (
            SELECT AVG(delivery_days) FROM fact_orders 
            WHERE is_delivered = 1 AND delivery_days IS NOT NULL
        ), 1
    )                                                  AS days_above_avg
FROM fact_orders f
JOIN dim_sellers s   ON f.seller_id = s.seller_id
JOIN dim_customers c ON f.customer_unique_id = c.customer_unique_id
WHERE f.is_delivered = 1
  AND f.delivery_days IS NOT NULL
GROUP BY s.seller_state, c.customer_state
HAVING COUNT(DISTINCT f.order_id) >= 50
ORDER BY late_pct DESC
LIMIT 20;


-- ============================================================
-- 8. Heavy Product Impact on Delivery
-- ============================================================
SELECT '=== 8. PRODUCT WEIGHT vs DELAY ===' AS section;

SELECT 
    CASE 
        WHEN p.product_weight_g <= 500   THEN '1: ≤500g (Light)'
        WHEN p.product_weight_g <= 2000  THEN '2: 500g–2kg'
        WHEN p.product_weight_g <= 5000  THEN '3: 2kg–5kg'
        WHEN p.product_weight_g <= 10000 THEN '4: 5kg–10kg'
        ELSE '5: >10kg (Heavy)'
    END                                               AS weight_bucket,
    COUNT(DISTINCT f.order_id)                        AS orders,
    ROUND(AVG(f.delivery_days), 1)                    AS avg_delivery_days,
    ROUND(AVG(f.delivery_delay_days), 1)              AS avg_delay_days,
    ROUND(AVG(f.is_late) * 100, 1)                    AS late_pct,
    ROUND(AVG(f.review_score), 2)                     AS avg_review
FROM fact_orders f
JOIN dim_products p ON f.product_id = p.product_id
WHERE f.is_delivered = 1
  AND f.delivery_days IS NOT NULL
  AND p.product_weight_g IS NOT NULL
GROUP BY weight_bucket
ORDER BY weight_bucket;
