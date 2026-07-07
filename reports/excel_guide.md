# Excel Workbook — Build Guide

This guide walks you through creating a professional Excel summary workbook with pivot tables, demonstrating Excel skills for the JD.

---

## Prerequisites

- **Microsoft Excel** or Google Sheets
- **Data files** in `data/processed/`:
  - `fact_orders.csv`
  - `dim_customers.csv`
  - `dim_products.csv`
  - `dim_sellers.csv`

---

## Step 1: Import Data

1. Open Excel → **Data → From Text/CSV**
2. Import `fact_orders.csv` into a sheet named "FactOrders"
3. Import `dim_customers.csv` → "DimCustomers"
4. Import `dim_products.csv` → "DimProducts"
5. Format each as a **Table** (Ctrl+T) for easy pivot table creation

---

## Step 2: Create Pivot Tables

### Pivot 1: Monthly Revenue Summary (Sheet: "Monthly KPIs")

1. Select the FactOrders table
2. **Insert → PivotTable → New Worksheet**
3. Configure:
   - **Rows:** `order_date_key` (group by Year-Month)
   - **Values:**
     - Sum of `total_item_value` → rename "Total GMV"
     - Count of `order_id` → rename "Order Count"
     - Average of `total_item_value` → rename "AOV"
4. **Filter:** `is_delivered = 1`
5. Add a **PivotChart** (Line chart) showing GMV trend

### Pivot 2: Category Performance (Sheet: "Category Revenue")

1. First, VLOOKUP category from DimProducts:
   ```
   =VLOOKUP([@product_id], DimProducts[#All], MATCH("product_category", DimProducts[#Headers], 0), FALSE)
   ```
2. Create PivotTable:
   - **Rows:** Product Category
   - **Values:** Sum of Revenue, Average of Review Score, Average of is_late
3. **Sort** by Revenue descending
4. Add **conditional formatting** to the Late Rate column (red = high)

### Pivot 3: State Performance (Sheet: "Regional Analysis")

1. VLOOKUP customer state from DimCustomers
2. Create PivotTable:
   - **Rows:** Customer State
   - **Values:** Order Count, Avg Delivery Days, Late Rate, Avg Review
3. Add a **PivotChart** (Map chart if available, or bar chart)

### Pivot 4: Seller Ranking (Sheet: "Seller Board")

1. Create PivotTable:
   - **Rows:** seller_id
   - **Values:** Sum of Revenue, Count of Orders, Avg Review Score
2. Sort by Revenue descending
3. Highlight **Top 10** using conditional formatting

---

## Step 3: Summary Dashboard Sheet

Create a "Dashboard" sheet with:

1. **KPI Cards** (formatted cells with large fonts):
   - Total GMV: `=SUM(FactOrders[total_item_value])`
   - Total Orders: `=COUNTA(UNIQUE(FactOrders[order_id]))`
   - AOV: `=GMV / Orders`
   - On-Time Rate: `=1 - AVERAGE(FactOrders[is_late])`

2. **Charts** copied from pivot sheets

3. **Formatting:**
   - Use company-style colors
   - Add borders and headers
   - Number formatting: R$ for currency, % for rates

---

## Step 4: Key Formulas to Demonstrate

| Formula | Purpose | Example |
|---------|---------|---------|
| `VLOOKUP` | Cross-table joins | Category lookup |
| `SUMIFS` | Conditional aggregation | Revenue by state |
| `AVERAGEIFS` | Conditional averages | Avg delivery time for late orders |
| `COUNTIFS` | Conditional counts | Orders per month |
| `IF(AND(...))` | Conditional logic | Flag high-risk orders |
| `TEXT()` | Date formatting | `=TEXT(A2,"YYYY-MM")` |
| `PERCENTILE` | Statistical analysis | Delivery time percentiles |

---

## Step 5: Save

Save as: `reports/ecommerce_summary.xlsx`

---

## Tips for Portfolio

- Use **consistent formatting** throughout
- Add a **cover sheet** with project title and date
- Include a **data dictionary** sheet explaining each column
- Use **named ranges** for cleaner formulas
- Add **data validation** dropdowns for interactive filtering
