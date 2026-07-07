import os
import streamlit as st
import pandas as pd
import numpy as np
import joblib
import plotly.express as px

# ==========================================
# CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="E-Commerce Analytics & ML Predictor",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide Streamlit footer
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)


# ==========================================
# LOAD DATA
# ==========================================
@st.cache_data
def load_dashboard_data():
    base_dir = os.path.join(os.path.dirname(__file__), 'dashboard', 'data')
    try:
        kpi_df = pd.read_csv(os.path.join(base_dir, 'monthly_kpis.csv'))
        cat_df = pd.read_csv(os.path.join(base_dir, 'category_breakdown.csv'))
        reg_df = pd.read_csv(os.path.join(base_dir, 'regional_delivery.csv'))
        seller_df = pd.read_csv(os.path.join(base_dir, 'seller_leaderboard.csv'))
        return kpi_df, cat_df, reg_df, seller_df
    except FileNotFoundError:
        return None, None, None, None

@st.cache_resource
def load_ml_model():
    model_path = os.path.join(os.path.dirname(__file__), 'models', 'rf_model.joblib')
    try:
        data = joblib.load(model_path)
        return data['model'], data['features']
    except FileNotFoundError:
        return None, None


# ==========================================
# SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title("📦 Olist E-Commerce")
st.sidebar.markdown("Portfolio Project by Vishal Kumar")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate", ["📊 Executive Dashboard", "🤖 ML Delivery Predictor"])


# ==========================================
# PAGE 1: DASHBOARD
# ==========================================
if page == "📊 Executive Dashboard":
    st.title("📊 E-Commerce Executive Dashboard")
    st.markdown("Analyze 100K+ real orders to understand GMV, delivery performance, and categories.")
    
    kpi_df, cat_df, reg_df, seller_df = load_dashboard_data()
    
    if kpi_df is None:
        st.warning("Dashboard data not found. Please run the ETL pipeline first (`python scripts/etl.py`).")
    else:
        # Top-level KPIs
        st.subheader("Key Performance Indicators (Overall)")
        total_gmv = kpi_df['total_gmv'].sum()
        total_orders = kpi_df['total_orders'].sum()
        avg_on_time = kpi_df['on_time_rate'].mean() * 100
        avg_score = kpi_df['avg_review_score'].mean()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total GMV", f"R$ {total_gmv:,.0f}")
        col2.metric("Total Orders", f"{total_orders:,}")
        col3.metric("On-Time Delivery", f"{avg_on_time:.1f}%")
        col4.metric("Avg Review Score", f"{avg_score:.2f} ⭐")
        
        st.markdown("---")
        
        # Monthly Trends
        st.subheader("📈 Monthly GMV & Volume Trend")
        # Ensure year_month is string for proper plotting
        kpi_df['year_month'] = kpi_df['year_month'].astype(str)
        fig_trend = px.bar(kpi_df, x='year_month', y='total_gmv', 
                           title='Total GMV by Month',
                           labels={'year_month': 'Month', 'total_gmv': 'GMV (R$)'},
                           color_discrete_sequence=['#2196F3'])
        st.plotly_chart(fig_trend, use_container_width=True)
        
        col_charts1, col_charts2 = st.columns(2)
        
        with col_charts1:
            st.subheader("🏆 Top Categories by Revenue")
            top_cats = cat_df.head(10)
            fig_cats = px.bar(top_cats, x='revenue', y='product_category', orientation='h',
                              title='Top 10 Categories',
                              labels={'revenue': 'Revenue (R$)', 'product_category': 'Category'},
                              color_discrete_sequence=['#4CAF50']).update_yaxes(categoryorder='total ascending')
            st.plotly_chart(fig_cats, use_container_width=True)
            
        with col_charts2:
            st.subheader("📍 Deliveries by State")
            top_states = reg_df.head(10)
            fig_states = px.bar(top_states, x='customer_state', y='total_orders',
                                title='Top 10 States by Orders',
                                labels={'total_orders': 'Orders', 'customer_state': 'State'},
                                color_discrete_sequence=['#FF9800'])
            st.plotly_chart(fig_states, use_container_width=True)
            
        st.markdown("---")
        st.subheader("Top Performing Sellers")
        st.dataframe(seller_df.head(10)[['seller_id', 'seller_city', 'seller_state', 'total_revenue', 'avg_review_score']], use_container_width=True)


# ==========================================
# PAGE 2: ML PREDICTOR
# ==========================================
elif page == "🤖 ML Delivery Predictor":
    st.title("🤖 Delivery Risk Predictor")
    st.markdown("""
    This Random Forest model predicts the probability of an order being delivered **late**. 
    It was trained on 88,000+ historical orders and achieved an **84.5% ROC-AUC score**.
    """)
    
    model, features = load_ml_model()
    
    if model is None:
        st.warning("ML Model not found. Please run `python scripts/03_delivery_risk_model.py` first.")
    else:
        st.markdown("### 📝 Enter Order Details")
        
        with st.form("prediction_form"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Order & Product Info**")
                price = st.number_input("Item Price (R$)", min_value=1.0, max_value=10000.0, value=150.0)
                freight = st.number_input("Freight Value (R$)", min_value=0.0, max_value=1000.0, value=20.0)
                weight = st.number_input("Product Weight (grams)", min_value=100, max_value=30000, value=1500)
                month = st.slider("Purchase Month", 1, 12, 11)
                
            with col2:
                st.markdown("**Logistics & Seller**")
                est_days = st.number_input("Estimated Delivery (Days)", min_value=1.0, max_value=90.0, value=25.0)
                seller_late_rate = st.slider("Seller Historical Late Rate (%)", 0.0, 100.0, 5.0) / 100.0
                seller_orders = st.number_input("Seller Historical Order Count", min_value=1, max_value=5000, value=100)
                same_state = st.checkbox("Seller & Customer in Same State?", value=False)
                
            with col3:
                st.markdown("**Categorical Info**")
                state_late_rate = st.slider("State Historical Late Rate (%)", 0.0, 100.0, 10.0) / 100.0
                
                # We need standard categories and states to populate
                category = st.selectbox("Product Category", ["health_beauty", "watches_gifts", "bed_bath_table", "sports_leisure", "computers_accessories", "furniture_decor", "housewares", "cool_stuff", "auto", "toys", "other"])
                customer_state = st.selectbox("Customer State", ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "ES", "other"])
                
            submit_button = st.form_submit_button("Predict Delivery Risk 🚀")
            
        if submit_button:
            # 1. Feature Engineering
            total_value = price + freight
            freight_ratio = freight / (total_value + 0.01)
            log_weight = np.log1p(weight)
            log_price = np.log1p(price)
            log_volume = np.log1p(5000) # placeholder avg volume
            quarter = (month - 1) // 3 + 1
            
            # 2. Build the input array matching exact feature names
            input_df = pd.DataFrame(columns=features)
            input_df.loc[0] = 0 # Initialize with zeros
            
            # Set numeric features
            num_map = {
                'price': price,
                'freight_value': freight,
                'estimated_delivery_days': est_days,
                'payment_installments': 1.0,
                'product_weight_g': weight,
                'product_volume_cm3': 5000,
                'product_photos_qty': 1,
                'freight_ratio': freight_ratio,
                'same_state': int(same_state),
                'seller_late_rate': seller_late_rate,
                'seller_order_count': seller_orders,
                'state_late_rate': state_late_rate,
                'log_weight': log_weight,
                'log_volume': log_volume,
                'log_price': log_price,
                'month': month,
                'day_of_week': 2, # Assume Wednesday
                'is_weekend': 0,
                'quarter': quarter
            }
            
            for col, val in num_map.items():
                if col in input_df.columns:
                    input_df.at[0, col] = val
                    
            # Set dummy features if they exist in the trained model
            cat_col = f'product_category_clean_{category}'
            if cat_col in input_df.columns:
                input_df.at[0, cat_col] = 1
                
            state_col = f'customer_state_{customer_state}'
            if state_col in input_df.columns:
                input_df.at[0, state_col] = 1
                
            # 3. Predict
            prob_late = model.predict_proba(input_df)[0][1] * 100
            
            st.markdown("---")
            st.subheader("Prediction Result")
            
            if prob_late > 50:
                st.error(f"⚠️ **HIGH RISK:** This order has a {prob_late:.1f}% chance of being delivered LATE.")
                st.markdown("""
                **Recommended Action:**
                - Add 3-day buffer to estimated delivery time.
                - Upgrade shipping class automatically.
                - Send proactive communication to the customer.
                """)
            elif prob_late > 20:
                st.warning(f"🟡 **MODERATE RISK:** This order has a {prob_late:.1f}% chance of being delivered late.")
            else:
                st.success(f"✅ **LOW RISK:** This order has only a {prob_late:.1f}% chance of being late. It will likely arrive on time.")
            
            # Display feature contributions (simplified logic)
            st.markdown("### Why? (Key Risk Drivers)")
            drivers = []
            if seller_late_rate > 0.15: drivers.append("• **Seller History:** This seller has a high historical late rate.")
            if est_days > 30: drivers.append("• **Long Estimate:** The estimated delivery timeline is very long, indicating structural logistics issues.")
            if state_late_rate > 0.15: drivers.append("• **Geography:** Deliveries to this state historically face delays.")
            if month in [11, 12]: drivers.append("• **Seasonality:** High holiday volume increases logistics strain.")
            
            if drivers:
                for d in drivers: st.markdown(d)
            else:
                st.markdown("• The combination of factors looks standard.")
