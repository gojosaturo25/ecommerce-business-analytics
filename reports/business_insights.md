# 📊 Business Insights Report — E-Commerce Analytics

**Date:** October 2018 (analysis period: Sep 2016 – Oct 2018)  
**Analyst:** Vishal Kumar  
**Dataset:** Olist Brazilian E-Commerce — 99,441 orders, 112,650 order-items

---

## Executive Summary

This report presents key findings from a comprehensive analysis of ~100K real e-commerce orders across Brazil. The analysis reveals **strong delivery-experience impact on customer satisfaction**, a **critically low repeat purchase rate (3.0%)**, and identifies **seller performance and geographic distance** as the top predictors of late delivery. A Random Forest classifier achieves **84.5% ROC-AUC** for predicting delivery-delay risk, enabling proactive logistics interventions.

---

## 1. Revenue & Growth Performance

### Key Metrics
| Metric | Value |
|--------|-------|
| Total GMV | R$ 15.4M |
| Total Delivered Orders | 96,478 |
| Average Order Value (AOV) | R$ 159.83 |
| Repeat Purchase Rate | 3.0% |
| Unique Customers | 96,096 |
| Active Sellers | 3,095 |
| Product Categories | 71+ |

### Insights
- **Growth Trajectory:** Monthly GMV grew from R$ 46K (Oct 2016) to R$ 1.1M+ (Mar–May 2018) — a **24x increase** in 18 months, driven by platform expansion.
- **November Spike:** Nov 2017 saw the highest GMV (R$ 1.15M), likely driven by Black Friday — a 53.6% month-over-month jump.
- **Category Concentration:** Top 5 categories (health & beauty, watches & gifts, bed/bath/table, sports/leisure, computers/accessories) account for ~R$ 6.05M — **39% of total GMV**.
- **Geographic Concentration:** São Paulo dominates with ~46,168 delivered items (42% of volume).

### Recommendation
> Focus marketing on the top 5 revenue categories while investing in cross-selling from high-margin adjacent categories (perfumery, cool stuff). São Paulo's dominance means regional expansion offers significant upside — but delivery infrastructure must precede marketing investment in distant states.

---

## 2. Delivery Performance ⚠️ Critical Finding

### Key Metrics
| Metric | Value |
|--------|-------|
| On-Time Delivery Rate | 92.1% |
| Average Delivery Time | 12.5 days |
| Average Delay (late orders only) | 9.4 days |
| Worst-Performing States | BA (19.2d avg), RS (15.2d), ES (15.5d) |
| Best-Performing State | SP (8.7d avg) |

### Root Cause Analysis

**Delivery delays are driven by three primary factors:**

1. **Geographic Distance:** São Paulo averages 8.7 days delivery; Bahia averages 19.2 days (2.2x longer). State explains **12.8% of variance** in delivery time (η² = 0.1278, ANOVA p ≈ 0).
2. **Seller Performance:** The top risk predictor in our ML model is `seller_late_rate` (importance = 0.2077). Poor-performing sellers have systematic fulfillment issues.
3. **Estimated Delivery Days:** The second-strongest ML feature (importance = 0.1224), suggesting that orders with long estimated timelines have structural logistics challenges.

### Impact on Customer Satisfaction
- **Statistically significant:** Pearson r = −0.2288 (p ≈ 0) between delivery delay and review score.
- **On-time deliveries average 4.21 review score vs 2.55 for late** — a gap of **1.66 points** (Cohen's d = 1.31, **large effect**).
- **This is the single most impactful finding:** improving delivery directly and measurably improves customer satisfaction.

### Recommendation
> 1. **Regional fulfillment hubs** in BA, RS, and northern states — delivery times 2x the SP baseline indicate logistics infrastructure gaps.
> 2. **Seller accountability:** Top predictor of delays is seller history. Implement seller scorecards and quality gates.
> 3. **Realistic delivery estimates:** Overpromising creates dissatisfaction even when absolute delivery time is reasonable.

---

## 3. Customer Segmentation (RFM Analysis)

### Segment Distribution
| Segment | % of Customers | % of Revenue | Avg Spend (R$) |
|---------|---------------|-------------|----------------|
| Champions | 16.2% | 30.4% | 310.17 |
| Loyal Customers | 23.6% | 42.9% | 300.12 |
| Potential Loyalists | 15.7% | 8.6% | 90.63 |
| New Customers | 7.8% | 1.9% | 39.59 |
| At Risk | 8.0% | 5.3% | 109.17 |
| Hibernating | 16.5% | 5.6% | 55.81 |
| About to Sleep | 8.1% | 2.7% | 54.55 |
| Need Attention | 3.9% | 2.6% | 108.97 |

### Key Insight
- **Repeat purchase rate is only 3.0%** — critically low for e-commerce. 93,358 unique customers made just 1.03 orders on average.
- **"Champions" + "Loyal Customers" = 39.8% of customers but 73.3% of revenue.** These are the lifeblood of the business.
- **"At Risk" + "Can't Lose Them" segments** represent 8.0% of customers but 5.3% of revenue — losing them means losing R$ 816K.

### Recommendation
> 1. **Retention is the #1 priority.** A 3% repeat rate means 97% of customers never return. Post-purchase engagement (tracking updates, loyalty programs, personalized follow-ups) is essential.
> 2. **"At Risk" rescue campaigns:** These 7,477 customers (avg spend R$ 109) haven't purchased recently despite prior engagement. Targeted win-back emails with discount incentives could recover significant revenue.
> 3. **"Champions" loyalty rewards:** The 15,130 Champions (avg R$ 310 spend) should receive exclusive early access, loyalty discounts, and premium support.

---

## 4. Delivery Risk Prediction (ML Model)

### Model Performance
| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|-------|----------|-----------|--------|-----|---------|
| Logistic Regression | 72.1% | 0.180 | 0.709 | 0.287 | 0.793 |
| **Random Forest** | **86.4%** | **0.313** | **0.603** | **0.412** | **0.845** |

### Top Risk Factors (by feature importance)
1. **Seller late rate** (0.208) — seller's historical on-time performance
2. **Estimated delivery days** (0.122) — longer estimates = higher risk
3. **Month** (0.088) — seasonal demand patterns
4. **State late rate** (0.063) — regional logistics baseline
5. **Quarter** (0.054) — quarterly demand cycles
6. **Freight value** (0.047) — shipping cost correlates with distance/complexity
7. **Seller order count** (0.039) — seller experience level
8. **Freight ratio** (0.033) — freight as % of total value
9. **Price** (0.031) — order value effects

### Business Application
> The Random Forest model achieves **84.5% ROC-AUC**, meaning it can distinguish at-risk orders from on-time orders with strong discriminative power. Deployment strategy:
>
> 1. **Flag high-risk orders at checkout** — automatically add 2–3 days buffer to estimated delivery dates for orders scoring above the risk threshold.
> 2. **Route flagged orders to priority fulfillment** — proactive warehouse prioritization for delay-prone orders.
> 3. **Proactive customer communication** — notify customers of potential delays before they occur, converting frustration into trust.
>
> **Expected impact:** With 60% recall, the model catches ~60% of orders that would be late, enabling intervention before customer dissatisfaction occurs.

---

## 5. Seller Performance

### Key Findings
- **Seller concentration:** Top sellers by revenue dominate, while many sellers have minimal volume.
- **Performance variance:** Seller late rate is the #1 predictor of delivery delay (ML importance = 0.208).
- **Review correlation:** Seller on-time performance directly impacts review scores — sellers in the worst performance quartile receive significantly lower ratings.

### Recommendation
> 1. **Seller scorecards:** Monthly performance reports benchmarked against peer sellers in the same state.
> 2. **Quality gates:** Sellers with persistent high late rates (>15%) should face reduced listing visibility until improvement.
> 3. **Incentive program:** Top-performing sellers get priority listing placement and "Trusted Seller" badges.

---

## 6. Payment Insights

- **Credit card** is the dominant payment method, followed by boleto (bank slip).
- Average payment installments reflect Brazilian consumer financing patterns.
- Payment method is not a significant predictor of delivery delay.

---

## Summary of Recommendations (Priority-Ranked)

| # | Recommendation | Expected Impact | Effort |
|---|---------------|----------------|--------|
| 1 | Post-purchase retention programs (3% repeat rate is critical) | High — even 1% improvement = ~960 additional returning customers | Medium |
| 2 | Seller performance scorecards & accountability | High — addresses #1 delay predictor | Low |
| 3 | Regional fulfillment for BA, RS, northern states | High — reduces 19+ day delivery to SP-like 9 days | High |
| 4 | ML-based proactive delay notifications | Medium — catches 60% of late orders before customer frustration | Medium |
| 5 | Realistic delivery date estimation | Medium — reduces perception of delay | Low |
| 6 | "At Risk" customer win-back campaigns | Medium — potential R$ 816K revenue recovery | Low |
| 7 | Champions loyalty program | Medium — protects 30.4% of revenue | Low |

---

## Methodology

- **Data Period:** September 2016 to October 2018
- **Analysis limited to delivered orders** (excludes cancelled, processing, etc.)
- **Statistical tests:** Two-tailed, α = 0.05 significance level, with non-parametric confirmations
- **ML models:** 80/20 stratified split, 5-fold cross-validation, class-balanced weighting
- **Currency:** Brazilian Real (R$)
- **Tools:** SQLite, Python (Pandas, scikit-learn, SciPy), Power BI

---

*This report was generated as part of a portfolio analytics project demonstrating SQL, Python, statistics, and ML capabilities applied to real e-commerce data.*
