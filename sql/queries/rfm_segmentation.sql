-- ============================================================
-- RFM Customer Segmentation
-- E-Commerce Data Warehouse
-- ============================================================
-- RFM = Recency, Frequency, Monetary
-- Uses NTILE window functions to score customers 1–5 on each dimension,
-- then classifies into business-meaningful segments.
--
-- Usage: sqlite3 -header -column data/processed/ecommerce.db < sql/queries/rfm_segmentation.sql
-- ============================================================


-- ============================================================
-- 1. RFM Score Computation
-- ============================================================
SELECT '=== 1. RFM SCORES (Top 30 Customers) ===' AS section;

WITH reference_date AS (
    -- Use the latest order date in the dataset as the reference point
    SELECT MAX(order_date_key) AS ref_date FROM fact_orders WHERE is_delivered = 1
),

customer_rfm_raw AS (
    SELECT 
        f.customer_unique_id,
        c.customer_city,
        c.customer_state,
        
        -- Recency: days since last purchase (lower = better)
        CAST(
            JULIANDAY((SELECT ref_date FROM reference_date)) - 
            JULIANDAY(MAX(f.order_date_key)) AS INTEGER
        )                                                 AS recency_days,
        
        -- Frequency: number of distinct orders
        COUNT(DISTINCT f.order_id)                        AS frequency,
        
        -- Monetary: total spend
        ROUND(SUM(f.total_item_value), 2)                 AS monetary
    
    FROM fact_orders f
    JOIN dim_customers c ON f.customer_unique_id = c.customer_unique_id
    WHERE f.is_delivered = 1
    GROUP BY f.customer_unique_id, c.customer_city, c.customer_state
),

rfm_scored AS (
    SELECT 
        customer_unique_id,
        customer_city,
        customer_state,
        recency_days,
        frequency,
        monetary,
        
        -- Score 1–5 using NTILE (5 = best for frequency/monetary, 1 = best for recency)
        -- Recency: lower days = more recent = better → score 5
        NTILE(5) OVER (ORDER BY recency_days DESC)       AS r_score,
        -- Frequency: more orders = better → score 5
        NTILE(5) OVER (ORDER BY frequency ASC)            AS f_score,
        -- Monetary: higher spend = better → score 5
        NTILE(5) OVER (ORDER BY monetary ASC)             AS m_score
    FROM customer_rfm_raw
)

SELECT 
    customer_unique_id,
    customer_state,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    -- Combined RFM score (simple average)
    ROUND((r_score + f_score + m_score) / 3.0, 1)        AS rfm_avg,
    -- Concatenated RFM string (e.g., "5-4-5")
    r_score || '-' || f_score || '-' || m_score           AS rfm_string
FROM rfm_scored
ORDER BY rfm_avg DESC, monetary DESC
LIMIT 30;


-- ============================================================
-- 2. Customer Segment Classification
-- ============================================================
SELECT '=== 2. CUSTOMER SEGMENTS ===' AS section;

WITH reference_date AS (
    SELECT MAX(order_date_key) AS ref_date FROM fact_orders WHERE is_delivered = 1
),

customer_rfm_raw AS (
    SELECT 
        f.customer_unique_id,
        CAST(
            JULIANDAY((SELECT ref_date FROM reference_date)) - 
            JULIANDAY(MAX(f.order_date_key)) AS INTEGER
        ) AS recency_days,
        COUNT(DISTINCT f.order_id)    AS frequency,
        ROUND(SUM(f.total_item_value), 2) AS monetary
    FROM fact_orders f
    WHERE f.is_delivered = 1
    GROUP BY f.customer_unique_id
),

rfm_scored AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC)      AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC)        AS m_score
    FROM customer_rfm_raw
),

rfm_segmented AS (
    SELECT *,
        CASE 
            -- Champions: recent, frequent, high spenders
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 
                THEN 'Champions'
            
            -- Loyal Customers: frequent buyers (may not be most recent)
            WHEN f_score >= 4 AND m_score >= 3 
                THEN 'Loyal Customers'
            
            -- Potential Loyalists: recent with moderate frequency
            WHEN r_score >= 4 AND f_score >= 2 AND f_score <= 4 
                THEN 'Potential Loyalists'
            
            -- New Customers: very recent, low frequency
            WHEN r_score >= 4 AND f_score <= 2 
                THEN 'New Customers'
            
            -- At Risk: used to buy frequently but haven't recently
            WHEN r_score <= 2 AND f_score >= 3 
                THEN 'At Risk'
            
            -- Can't Lose Them: were big spenders but slipping away
            WHEN r_score <= 2 AND m_score >= 4 
                THEN 'Cant Lose Them'
            
            -- Hibernating: low on all dimensions
            WHEN r_score <= 2 AND f_score <= 2 
                THEN 'Hibernating'
            
            -- Need Attention: middle of the road
            WHEN r_score = 3 AND f_score = 3 
                THEN 'Need Attention'
            
            -- About to Sleep: below average recency and frequency
            WHEN r_score <= 3 AND f_score <= 3 
                THEN 'About to Sleep'
            
            ELSE 'Others'
        END AS segment
    FROM rfm_scored
)

SELECT 
    segment,
    COUNT(*)                                          AS customer_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM rfm_segmented), 1) AS pct_of_total,
    ROUND(AVG(recency_days), 0)                       AS avg_recency_days,
    ROUND(AVG(frequency), 2)                          AS avg_frequency,
    ROUND(AVG(monetary), 2)                           AS avg_monetary,
    ROUND(SUM(monetary), 2)                           AS total_revenue,
    ROUND(
        SUM(monetary) * 100.0 / (SELECT SUM(monetary) FROM rfm_segmented), 1
    )                                                  AS pct_of_revenue
FROM rfm_segmented
GROUP BY segment
ORDER BY total_revenue DESC;


-- ============================================================
-- 3. Segment Distribution by State (Top 5 States)
-- ============================================================
SELECT '=== 3. SEGMENT × STATE (Top 5 States) ===' AS section;

WITH reference_date AS (
    SELECT MAX(order_date_key) AS ref_date FROM fact_orders WHERE is_delivered = 1
),

top_states AS (
    SELECT customer_state
    FROM dim_customers
    GROUP BY customer_state
    ORDER BY COUNT(*) DESC
    LIMIT 5
),

customer_rfm_raw AS (
    SELECT 
        f.customer_unique_id,
        c.customer_state,
        CAST(
            JULIANDAY((SELECT ref_date FROM reference_date)) - 
            JULIANDAY(MAX(f.order_date_key)) AS INTEGER
        ) AS recency_days,
        COUNT(DISTINCT f.order_id)    AS frequency,
        ROUND(SUM(f.total_item_value), 2) AS monetary
    FROM fact_orders f
    JOIN dim_customers c ON f.customer_unique_id = c.customer_unique_id
    WHERE f.is_delivered = 1
      AND c.customer_state IN (SELECT customer_state FROM top_states)
    GROUP BY f.customer_unique_id, c.customer_state
),

rfm_scored AS (
    SELECT *,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC)      AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC)        AS m_score
    FROM customer_rfm_raw
),

rfm_segmented AS (
    SELECT *,
        CASE 
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN f_score >= 4 AND m_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score >= 2 AND f_score <= 4 THEN 'Potential Loyalists'
            WHEN r_score >= 4 AND f_score <= 2 THEN 'New Customers'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
            WHEN r_score <= 2 AND m_score >= 4 THEN 'Cant Lose Them'
            WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating'
            WHEN r_score = 3 AND f_score = 3 THEN 'Need Attention'
            WHEN r_score <= 3 AND f_score <= 3 THEN 'About to Sleep'
            ELSE 'Others'
        END AS segment
    FROM rfm_scored
)

SELECT 
    customer_state,
    segment,
    COUNT(*) AS customers,
    ROUND(AVG(monetary), 2) AS avg_monetary
FROM rfm_segmented
GROUP BY customer_state, segment
ORDER BY customer_state, customers DESC;
