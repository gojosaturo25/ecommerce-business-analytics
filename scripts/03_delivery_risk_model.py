"""
03 — Delivery Risk Prediction (ML Model)
==========================================

Predicts whether an order will be delivered late using:
  1. Logistic Regression (baseline)
  2. Random Forest Classifier

Features:
  - Product: weight, volume, category
  - Seller: state, historical performance
  - Customer: state
  - Order: day of week, month, payment type
  - Logistics: estimated delivery days, freight ratio

Outputs:
  - Model evaluation metrics (accuracy, precision, recall, F1, ROC-AUC)
  - Feature importance plot
  - ROC curves
  - Confusion matrices
  - All saved to reports/figures/ and reports/model_results.txt

Usage:
    python scripts/03_delivery_risk_model.py
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
import joblib

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, confusion_matrix, classification_report
)

warnings.filterwarnings('ignore')

# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'ecommerce.db')
FIGURES_DIR = os.path.join(PROJECT_ROOT, 'reports', 'figures')
RESULTS_PATH = os.path.join(PROJECT_ROOT, 'reports', 'model_results.txt')
os.makedirs(FIGURES_DIR, exist_ok=True)

plt.style.use('seaborn-v0_8-whitegrid')

output_buffer = StringIO()

def tee(text):
    print(text)
    output_buffer.write(text + '\n')

def save_fig(fig, name):
    path = os.path.join(FIGURES_DIR, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    tee(f"  ✓ Chart saved: {path}")


# ============================================================
# STEP 1: LOAD & PREPARE DATA
# ============================================================

def load_and_prepare():
    """Load data and engineer features for ML."""
    tee("Loading data and engineering features...")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}. Run etl.py first.")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT 
            f.order_id,
            f.order_item_id,
            f.seller_id,
            f.price,
            f.freight_value,
            f.total_item_value,
            f.estimated_delivery_days,
            f.is_late,
            f.payment_type,
            f.payment_installments,
            p.product_category,
            p.product_weight_g,
            p.product_volume_cm3,
            p.product_photos_qty,
            s.seller_state,
            c.customer_state,
            d.month,
            d.day_of_week,
            d.is_weekend,
            d.quarter
        FROM fact_orders f
        JOIN dim_products p   ON f.product_id = p.product_id
        JOIN dim_sellers s    ON f.seller_id = s.seller_id
        JOIN dim_customers c  ON f.customer_unique_id = c.customer_unique_id
        JOIN dim_date d       ON f.order_date_key = d.date_key
        WHERE f.is_delivered = 1
          AND f.delivery_days IS NOT NULL
          AND f.estimated_delivery_days IS NOT NULL
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    tee(f"  Raw records: {len(df):,}")
    
    # ---- Feature Engineering ----
    
    # 1. Freight ratio (freight as fraction of total)
    df['freight_ratio'] = df['freight_value'] / (df['total_item_value'] + 0.01)
    
    # 2. Same-state delivery flag
    df['same_state'] = (df['seller_state'] == df['customer_state']).astype(int)
    
    # 3. Seller historical performance (average late rate per seller)
    seller_perf = df.groupby('seller_id')['is_late'].mean().reset_index()
    seller_perf.columns = ['seller_id', 'seller_late_rate']
    df = df.merge(seller_perf, on='seller_id', how='left')
    
    # 4. Seller order volume (proxy for experience)
    seller_volume = df.groupby('seller_id')['order_id'].nunique().reset_index()
    seller_volume.columns = ['seller_id', 'seller_order_count']
    df = df.merge(seller_volume, on='seller_id', how='left')
    
    # 5. State-level delivery baseline
    state_avg_delay = df.groupby('customer_state')['is_late'].mean().reset_index()
    state_avg_delay.columns = ['customer_state', 'state_late_rate']
    df = df.merge(state_avg_delay, on='customer_state', how='left')
    
    # 6. Category encoding (top N categories, rest → 'other')
    top_categories = df['product_category'].value_counts().head(20).index
    df['product_category_clean'] = df['product_category'].where(
        df['product_category'].isin(top_categories), 'other'
    )
    
    # 7. Log-transform skewed features
    df['log_weight'] = np.log1p(df['product_weight_g'].fillna(0))
    df['log_volume'] = np.log1p(df['product_volume_cm3'].fillna(0))
    df['log_price'] = np.log1p(df['price'])
    
    # ---- Drop rows with too many nulls ----
    df = df.dropna(subset=['estimated_delivery_days', 'product_weight_g'])
    
    tee(f"  After feature engineering: {len(df):,} records")
    tee(f"  Target distribution: {df['is_late'].value_counts().to_dict()}")
    tee(f"  Late rate: {df['is_late'].mean()*100:.1f}%")
    
    return df


# ============================================================
# STEP 2: FEATURE SELECTION & ENCODING
# ============================================================

def prepare_features(df):
    """Select and encode features for modeling."""
    tee("\nPreparing feature matrix...")
    
    # Numeric features
    numeric_features = [
        'price', 'freight_value', 'estimated_delivery_days',
        'payment_installments', 'product_weight_g', 'product_volume_cm3',
        'product_photos_qty', 'freight_ratio', 'same_state',
        'seller_late_rate', 'seller_order_count', 'state_late_rate',
        'log_weight', 'log_volume', 'log_price',
        'month', 'day_of_week', 'is_weekend', 'quarter'
    ]
    
    # Categorical features to encode
    categorical_features = ['product_category_clean', 'payment_type', 'seller_state', 'customer_state']
    
    # Fill numeric nulls
    for col in numeric_features:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())
    
    # One-hot encode categoricals
    df_encoded = pd.get_dummies(df[numeric_features + categorical_features], 
                                columns=categorical_features, 
                                drop_first=True,
                                dtype=int)
    
    feature_names = df_encoded.columns.tolist()
    X = df_encoded.values
    y = df['is_late'].values
    
    tee(f"  Feature matrix shape: {X.shape}")
    tee(f"  Number of features: {len(feature_names)}")
    
    return X, y, feature_names


# ============================================================
# STEP 3: TRAIN & EVALUATE MODELS
# ============================================================

def train_and_evaluate(X, y, feature_names):
    """Train Logistic Regression and Random Forest, evaluate both."""
    tee("\n" + "=" * 70)
    tee("  MODEL TRAINING & EVALUATION")
    tee("=" * 70)
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    tee(f"\n  Train set: {X_train.shape[0]:,} ({y_train.mean()*100:.1f}% late)")
    tee(f"  Test set:  {X_test.shape[0]:,} ({y_test.mean()*100:.1f}% late)")
    
    # Scale features for Logistic Regression
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    results = {}
    
    # ---- Model 1: Logistic Regression ----
    tee("\n  --- Logistic Regression ---")
    lr = LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced')
    lr.fit(X_train_scaled, y_train)
    
    y_pred_lr = lr.predict(X_test_scaled)
    y_prob_lr = lr.predict_proba(X_test_scaled)[:, 1]
    
    results['Logistic Regression'] = evaluate_model(
        y_test, y_pred_lr, y_prob_lr, 'Logistic Regression'
    )
    
    # Cross-validation
    cv_scores = cross_val_score(lr, X_train_scaled, y_train, cv=5, scoring='roc_auc')
    tee(f"  5-Fold CV ROC-AUC: {cv_scores.mean():.4f} (±{cv_scores.std():.4f})")
    
    # ---- Model 2: Random Forest ----
    tee("\n  --- Random Forest ---")
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    
    y_pred_rf = rf.predict(X_test)
    y_prob_rf = rf.predict_proba(X_test)[:, 1]
    
    results['Random Forest'] = evaluate_model(
        y_test, y_pred_rf, y_prob_rf, 'Random Forest'
    )
    
    # Cross-validation
    cv_scores_rf = cross_val_score(rf, X_train, y_train, cv=5, scoring='roc_auc')
    tee(f"  5-Fold CV ROC-AUC: {cv_scores_rf.mean():.4f} (±{cv_scores_rf.std():.4f})")
    
    # ---- Comparison ----
    plot_comparison(y_test, y_pred_lr, y_prob_lr, y_pred_rf, y_prob_rf, results)
    plot_feature_importance(rf, feature_names)
    plot_logistic_coefficients(lr, feature_names)
    # ---- Save the Model ----
    model_path = os.path.join(PROJECT_ROOT, 'models', 'rf_model.joblib')
    joblib.dump({'model': rf, 'features': feature_names}, model_path)
    tee(f"\n  Random Forest model saved to: {model_path}")
    
    return results


def evaluate_model(y_true, y_pred, y_prob, model_name):
    """Compute and print evaluation metrics."""
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    auc = roc_auc_score(y_true, y_prob)
    
    tee(f"\n  {model_name} Results:")
    tee(f"    Accuracy:  {acc:.4f}")
    tee(f"    Precision: {prec:.4f}")
    tee(f"    Recall:    {rec:.4f}")
    tee(f"    F1 Score:  {f1:.4f}")
    tee(f"    ROC-AUC:   {auc:.4f}")
    
    tee(f"\n  Classification Report:")
    report = classification_report(y_true, y_pred, target_names=['On-Time', 'Late'])
    tee(report)
    
    return {'accuracy': acc, 'precision': prec, 'recall': rec, 'f1': f1, 'roc_auc': auc}


# ============================================================
# STEP 4: VISUALIZATIONS
# ============================================================

def plot_comparison(y_test, y_pred_lr, y_prob_lr, y_pred_rf, y_prob_rf, results):
    """Plot ROC curves and confusion matrices."""
    tee("\n  Plotting model comparison...")
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle('Model Comparison: Logistic Regression vs Random Forest', 
                 fontsize=16, fontweight='bold')
    
    # ROC Curves
    ax = axes[0, 0]
    for name, y_prob, color in [
        ('Logistic Regression', y_prob_lr, '#2196F3'),
        ('Random Forest', y_prob_rf, '#4CAF50')
    ]:
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        auc = results[name]['roc_auc']
        ax.plot(fpr, tpr, color=color, linewidth=2, label=f'{name} (AUC={auc:.3f})')
    
    ax.plot([0, 1], [0, 1], 'k--', alpha=0.5, label='Random (AUC=0.500)')
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.set_title('ROC Curves')
    ax.legend(loc='lower right')
    
    # Confusion Matrix — Logistic Regression
    ax = axes[0, 1]
    cm_lr = confusion_matrix(y_test, y_pred_lr)
    sns.heatmap(cm_lr, annot=True, fmt='d', cmap='Blues', ax=ax,
                xticklabels=['On-Time', 'Late'], yticklabels=['On-Time', 'Late'])
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')
    ax.set_title('Confusion Matrix — Logistic Regression')
    
    # Confusion Matrix — Random Forest
    ax = axes[1, 0]
    cm_rf = confusion_matrix(y_test, y_pred_rf)
    sns.heatmap(cm_rf, annot=True, fmt='d', cmap='Greens', ax=ax,
                xticklabels=['On-Time', 'Late'], yticklabels=['On-Time', 'Late'])
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Actual')
    ax.set_title('Confusion Matrix — Random Forest')
    
    # Metrics comparison bar chart
    ax = axes[1, 1]
    metrics = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']
    lr_vals = [results['Logistic Regression'][m] for m in metrics]
    rf_vals = [results['Random Forest'][m] for m in metrics]
    
    x = np.arange(len(metrics))
    width = 0.35
    ax.bar(x - width/2, lr_vals, width, label='Logistic Regression', color='#2196F3', alpha=0.8)
    ax.bar(x + width/2, rf_vals, width, label='Random Forest', color='#4CAF50', alpha=0.8)
    ax.set_ylabel('Score')
    ax.set_title('Metrics Comparison')
    ax.set_xticks(x)
    ax.set_xticklabels(['Accuracy', 'Precision', 'Recall', 'F1', 'ROC-AUC'])
    ax.legend()
    ax.set_ylim(0, 1.15)
    
    # Add value labels
    for i, (lr_v, rf_v) in enumerate(zip(lr_vals, rf_vals)):
        ax.text(i - width/2, lr_v + 0.02, f'{lr_v:.3f}', ha='center', fontsize=8)
        ax.text(i + width/2, rf_v + 0.02, f'{rf_v:.3f}', ha='center', fontsize=8)
    
    plt.tight_layout()
    save_fig(fig, '13_model_comparison')


def plot_feature_importance(rf, feature_names):
    """Plot Random Forest feature importance."""
    tee("  Plotting feature importance...")
    
    importances = rf.feature_importances_
    indices = np.argsort(importances)[-20:]  # Top 20
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(indices)))
    ax.barh(range(len(indices)), importances[indices], color=colors)
    ax.set_yticks(range(len(indices)))
    ax.set_yticklabels([feature_names[i] for i in indices], fontsize=9)
    ax.set_xlabel('Feature Importance (Gini)')
    ax.set_title('Top 20 Features — Random Forest', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    save_fig(fig, '14_feature_importance_rf')
    
    # Print top features
    tee("\n  Top 10 Most Important Features (Random Forest):")
    for i in reversed(indices[-10:]):
        tee(f"    {feature_names[i]:<35} {importances[i]:.4f}")


def plot_logistic_coefficients(lr, feature_names):
    """Plot Logistic Regression coefficients."""
    tee("  Plotting logistic regression coefficients...")
    
    coefs = lr.coef_[0]
    top_idx = np.argsort(np.abs(coefs))[-20:]
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    colors = ['#F44336' if c > 0 else '#4CAF50' for c in coefs[top_idx]]
    ax.barh(range(len(top_idx)), coefs[top_idx], color=colors, alpha=0.8)
    ax.set_yticks(range(len(top_idx)))
    ax.set_yticklabels([feature_names[i] for i in top_idx], fontsize=9)
    ax.set_xlabel('Coefficient (positive = increases late probability)')
    ax.set_title('Top 20 Features — Logistic Regression Coefficients', fontsize=14, fontweight='bold')
    ax.axvline(0, color='black', linewidth=0.8)
    
    plt.tight_layout()
    save_fig(fig, '15_logistic_coefficients')


# ============================================================
# MAIN
# ============================================================

def main():
    tee("=" * 70)
    tee("  Delivery Risk Prediction — ML Model")
    tee("=" * 70)
    
    df = load_and_prepare()
    X, y, feature_names = prepare_features(df)
    results = train_and_evaluate(X, y, feature_names)
    
    # Final summary
    tee("\n" + "=" * 70)
    tee("  FINAL MODEL SUMMARY")
    tee("=" * 70)
    
    best_model = max(results.items(), key=lambda x: x[1]['roc_auc'])
    tee(f"\n  Best Model: {best_model[0]}")
    tee(f"  ROC-AUC:    {best_model[1]['roc_auc']:.4f}")
    tee(f"  F1 Score:   {best_model[1]['f1']:.4f}")
    tee(f"  Precision:  {best_model[1]['precision']:.4f}")
    tee(f"  Recall:     {best_model[1]['recall']:.4f}")
    
    tee(f"\n  Business Recommendation:")
    tee(f"  The {best_model[0]} model can identify orders at risk of late")
    tee(f"  delivery with {best_model[1]['roc_auc']*100:.1f}% discriminative ability (ROC-AUC).")
    tee(f"  This enables proactive logistics interventions for high-risk orders.")
    
    # Save results
    with open(RESULTS_PATH, 'w') as f:
        f.write(output_buffer.getvalue())
    
    tee(f"\n  ✅ ML MODEL COMPLETE")
    tee(f"  Results saved to: {RESULTS_PATH}")
    tee(f"  Charts saved to: {FIGURES_DIR}")


if __name__ == '__main__':
    main()
