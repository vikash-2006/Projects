# ============================================================
#  MITTI Cafe — Churn Prediction Model
#  File: train_model.py
#  Run this file ONCE to train and save the model.
#  Command: python3 train_model.py
# ============================================================

# ── STEP 1: Import required libraries ──────────────────────
import pandas as pd                          # for reading CSV data
import numpy as np                           # for numbers
from sklearn.model_selection import train_test_split   # split data into train/test
from sklearn.linear_model import LogisticRegression    # our ML model
from sklearn.preprocessing import StandardScaler       # normalize features
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)
import joblib                                # for saving/loading model

import json

print("=" * 55)
print("  MITTI Cafe — Churn Prediction Model Training")
print("=" * 55)

# ── STEP 2: Load the CSV data ────────────────────────────
print("\n[1/6] Loading subscriber data...")

df = pd.read_csv("data/mitti_subscribers.csv")

print(f"      Total rows loaded   : {len(df)}")
print(f"      Columns             : {list(df.columns)}")
print(f"      Churned customers   : {df['churned'].sum()}")
print(f"      Active customers    : {(df['churned'] == 0).sum()}")

# ── STEP 3: Prepare features (X) and label (y) ──────────
print("\n[2/6] Preparing features and labels...")

# X = input columns the model learns FROM
# These are the signals that predict whether someone churns
FEATURES = [
    "cafe_visits_last_month",   # more visits = less likely to churn
    "whatsapp_opened",          # engaged = less likely to churn
    "box_accepted",             # receiving box = happy customer
    "months_subscribed",        # longer = more loyal
    "plan_type"                 # 0=Seedling, 1=Grower, 2=Farmer
]

X = df[FEATURES]               # input features
y = df["churned"]              # output label: 0 = stayed, 1 = churned

print(f"      Feature columns     : {FEATURES}")
print(f"      Target column       : churned (0=stayed, 1=churned)")

# ── STEP 4: Split data into Train and Test sets ──────────
# We use 80% data to TRAIN the model
# We use 20% data to TEST how well it learned
print("\n[3/6] Splitting data (80% train / 20% test)...")

X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,        # 20% goes to test
    random_state=42,      # so results are same every run
    stratify=y            # keep same churn ratio in both splits
)

print(f"      Training rows       : {len(X_train)}")
print(f"      Testing rows        : {len(X_test)}")

# ── STEP 5: Scale the features ────────────────────────────
# StandardScaler converts all values to same range
# This helps Logistic Regression perform better
print("\n[4/6] Scaling features with StandardScaler...")

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)   # fit + transform on train
X_test_scaled  = scaler.transform(X_test)        # only transform on test (not fit)

print("      Scaling complete.")

# ── STEP 6: Train the Logistic Regression model ──────────
print("\n[5/6] Training Logistic Regression model...")

model = LogisticRegression(
    random_state=42,
    max_iter=1000,         # max iterations for convergence
    C=1.0                  # regularization (higher = less regularized)
)

model.fit(X_train_scaled, y_train)   # THE TRAINING HAPPENS HERE

print("      Model trained successfully!")

# ── STEP 7: Evaluate the model ───────────────────────────
print("\n[6/6] Evaluating model performance...")

y_pred       = model.predict(X_test_scaled)
y_pred_proba = model.predict_proba(X_test_scaled)

accuracy = accuracy_score(y_test, y_pred)
print(f"\n      ✅ Accuracy          : {accuracy * 100:.1f}%")

print("\n      Classification Report:")
print(classification_report(y_test, y_pred,
      target_names=["Stayed (0)", "Churned (1)"]))

print("      Confusion Matrix (Actual vs Predicted):")
cm = confusion_matrix(y_test, y_pred)
print(f"      True Negative  (Correct: Stayed)  : {cm[0][0]}")
print(f"      False Positive (Wrong: Said Churn) : {cm[0][1]}")
print(f"      False Negative (Missed Churn)      : {cm[1][0]}")
print(f"      True Positive  (Correct: Churn)    : {cm[1][1]}")

# ── Feature Importance (Coefficients) ────────────────────
print("\n      Feature Importance (higher = stronger signal):")
coefficients = dict(zip(FEATURES, model.coef_[0]))
for feat, coef in sorted(coefficients.items(), key=lambda x: abs(x[1]), reverse=True):
    direction = "⬆ less churn" if coef < 0 else "⬇ more churn"
    print(f"        {feat:<30} {coef:+.3f}  {direction}")

# ── STEP 8: Save the model and scaler ────────────────────
print("\n  Saving model and scaler to /model/ folder...")

os.makedirs("model", exist_ok=True)

joblib.dump(model,  "model/churn_model.pkl")
joblib.dump(scaler, "model/churn_scaler.pkl")

# Save metadata (feature names + accuracy) for reference
metadata = {
    "features"    : FEATURES,
    "accuracy"    : round(accuracy * 100, 2),
    "model_type"  : "LogisticRegression",
    "trained_on"  : len(X_train),
    "version"     : "1.0"
}
with open("model/model_info.json", "w") as f:
    json.dump(metadata, f, indent=2)

print("      model/churn_model.pkl    ✅ saved")
print("      model/churn_scaler.pkl   ✅ saved")
print("      model/model_info.json    ✅ saved")

# ── STEP 9: Test a quick prediction ──────────────────────
print("\n" + "=" * 55)
print("  QUICK TEST — Sample Predictions")
print("=" * 55)

test_cases = [
    {
        "name"                   : "Sunita (Loyal Farmer)",
        "cafe_visits_last_month" : 5,
        "whatsapp_opened"        : 1,
        "box_accepted"           : 1,
        "months_subscribed"      : 8,
        "plan_type"              : 2     # Farmer plan
    },
    {
        "name"                   : "Rahul (At-Risk)",
        "cafe_visits_last_month" : 0,
        "whatsapp_opened"        : 0,
        "box_accepted"           : 0,
        "months_subscribed"      : 1,
        "plan_type"              : 0     # Seedling plan
    },
    {
        "name"                   : "Priya (Medium Risk)",
        "cafe_visits_last_month" : 2,
        "whatsapp_opened"        : 1,
        "box_accepted"           : 0,
        "months_subscribed"      : 3,
        "plan_type"              : 1     # Grower plan
    },
]

for case in test_cases:
    name = case.pop("name")
    values = [[case[f] for f in FEATURES]]
    scaled = scaler.transform(values)
    prob   = model.predict_proba(scaled)[0][1]   # probability of churn
    risk   = "🔴 HIGH RISK"  if prob > 0.7 else \
             "🟡 MEDIUM"     if prob > 0.4 else \
             "🟢 LOW RISK"

    print(f"\n  Customer: {name}")
    print(f"  Churn probability : {prob * 100:.1f}%")
    print(f"  Risk level        : {risk}")
    if prob > 0.5:
        print(f"  Action            : Send WhatsApp retention offer now!")
    else:
        print(f"  Action            : Keep nurturing. No action needed.")

print("\n" + "=" * 55)
print("  Training complete! Now update your app.py")
print("  Run: python3 train_model.py")
print("=" * 55 + "\n")