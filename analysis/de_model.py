import pandas as pd
import numpy as np
import matplotlib
from pathlib import Path

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from plot_export import save_all_figures

from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit


# ============================================================
# SETTINGS
# ============================================================

analysis_dir = Path(__file__).resolve().parent
csv_path = analysis_dir / "data" / "climb_data.csv"
derived_data_dir = analysis_dir / "data" / "derived"
plot_output_dir = analysis_dir / "outputs" / "plots" / "de_model"

plt.rcParams["figure.max_open_warning"] = 0

# Try different time constants for the one-state readiness model
tau_grid = [1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90, 120]

# Load definition
# 1 = grade
# 2 = grade^2, harder climbs count superlinearly
load_exponent = 2

# Optional: keep only climbing rows if type == 0 means climbing
filter_to_climbing_type = True
climbing_type_value = 0

# Number of splits for time-series cross-validation
n_splits = 5


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(csv_path)

df["time"] = pd.to_datetime(df["time"], errors="coerce")
df["grade"] = pd.to_numeric(df["grade"], errors="coerce")
df["send/reps"] = pd.to_numeric(df["send/reps"], errors="coerce")
if "type" in df.columns:
    df["type"] = pd.to_numeric(df["type"], errors="coerce")
df = df.dropna(subset=["time"]).copy()
df["date"] = df["time"].dt.floor("D")

if filter_to_climbing_type and "type" in df.columns:
    df = df[df["type"] == climbing_type_value].copy()

df = df.dropna(subset=["grade", "send/reps"]).copy()

# Define send/fail outcome
df["send"] = (df["send/reps"] > 0).astype(int)

# Every row is one attempt
df["attempts"] = 1

# Define attempt load
df["attempt_load"] = df["grade"] ** load_exponent

# Sort by time
df = df.sort_values("time").reset_index(drop=True)


# ============================================================
# DAILY LOAD
# ============================================================

daily_load = (
    df.groupby("date", as_index=True)
      .agg(
          daily_load=("attempt_load", "sum"),
          attempts=("attempts", "sum"),
          sends=("send", "sum"),
          mean_grade=("grade", "mean"),
          max_grade=("grade", "max")
      )
      .sort_index()
)

# Fill missing calendar days with zero load
daily_load = daily_load.asfreq("D")

for col in ["daily_load", "attempts", "sends"]:
    daily_load[col] = daily_load[col].fillna(0)


# ============================================================
# BUILD ONE-STATE READINESS MODEL
# ============================================================

def make_readiness_state(daily_load, tau):
    """
    One-state past-only readiness/load-history model.

    Positive values here are not automatically "good" or "bad".
    The logistic regression will learn whether this recent-load state
    predicts better or worse sending after controlling for grade.

    Today's state uses only previous days' load.
    """

    decay = np.exp(-1 / tau)

    load = daily_load["daily_load"].values
    readiness = np.zeros(len(daily_load))

    for t in range(1, len(daily_load)):
        readiness[t] = decay * readiness[t - 1] + load[t - 1]

    states = daily_load.copy()
    states["readiness"] = readiness

    return states


# ============================================================
# TIME-SERIES CROSS-VALIDATION HELPER
# ============================================================

def time_series_score(model_df, feature_cols):
    """
    Returns held-out log loss and AUC using time-series CV.
    """

    model_df = model_df.sort_values("time").copy()

    X = model_df[feature_cols].values
    y = model_df["send"].values

    if len(np.unique(y)) < 2:
        return None

    tscv = TimeSeriesSplit(n_splits=n_splits)

    fold_log_losses = []
    fold_aucs = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # Skip unusable folds
        if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
            continue

        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000)
        )

        model.fit(X_train, y_train)

        p_test = model.predict_proba(X_test)[:, 1]

        fold_log_losses.append(log_loss(y_test, p_test))
        fold_aucs.append(roc_auc_score(y_test, p_test))

    if len(fold_log_losses) == 0:
        return None

    return {
        "mean_log_loss": np.mean(fold_log_losses),
        "mean_auc": np.mean(fold_aucs),
        "n_folds": len(fold_log_losses)
    }


# ============================================================
# BASELINE MODEL: GRADE ONLY
# ============================================================

baseline_df = df.dropna(subset=["grade", "send"]).copy()

baseline_score = time_series_score(
    model_df=baseline_df,
    feature_cols=["grade"]
)

print()
print("Grade-only baseline model:")
print(baseline_score)


# ============================================================
# GRID SEARCH: GRADE + READINESS
# ============================================================

results = []

for tau in tau_grid:
    states = make_readiness_state(daily_load, tau)

    model_df = df.merge(
        states[["readiness"]],
        left_on="date",
        right_index=True,
        how="left"
    )

    model_df = model_df.dropna(subset=["grade", "readiness", "send"]).copy()

    score = time_series_score(
        model_df=model_df,
        feature_cols=["grade", "readiness"]
    )

    if score is not None:
        results.append({
            "tau": tau,
            "mean_log_loss": score["mean_log_loss"],
            "mean_auc": score["mean_auc"],
            "n_folds": score["n_folds"]
        })

results_df = pd.DataFrame(results).sort_values("mean_log_loss")

print()
print("Readiness model grid search:")
print(results_df)

best_tau = results_df.iloc[0]["tau"]

print()
print(f"Best tau: {best_tau} days")


# ============================================================
# COMPARE BASELINE VS BEST READINESS MODEL
# ============================================================

best_log_loss = results_df.iloc[0]["mean_log_loss"]
baseline_log_loss = baseline_score["mean_log_loss"]

improvement = baseline_log_loss - best_log_loss

print()
print("Model comparison:")
print(f"Grade-only log loss:          {baseline_log_loss:.6f}")
print(f"Grade + readiness log loss:   {best_log_loss:.6f}")
print(f"Improvement:                  {improvement:.6f}")

if improvement > 0:
    print("Readiness improved held-out prediction.")
else:
    print("Readiness did NOT improve held-out prediction. Rude, but informative.")


# ============================================================
# FIT FINAL MODEL USING BEST TAU
# ============================================================

best_states = make_readiness_state(daily_load, best_tau)

model_df = df.merge(
    best_states[["readiness"]],
    left_on="date",
    right_index=True,
    how="left"
)

model_df = model_df.dropna(subset=["grade", "readiness", "send"]).copy()
model_df = model_df.sort_values("time")

feature_cols = ["grade", "readiness"]

final_model = make_pipeline(
    StandardScaler(),
    LogisticRegression(max_iter=1000)
)

final_model.fit(model_df[feature_cols], model_df["send"])

model_df["predicted_send_probability"] = final_model.predict_proba(
    model_df[feature_cols]
)[:, 1]

coefs = final_model.named_steps["logisticregression"].coef_[0]

coef_df = pd.DataFrame({
    "feature": feature_cols,
    "coefficient": coefs
})

print()
print("Final model coefficients:")
print(coef_df)

print()
print("Interpretation:")
if coef_df.loc[coef_df["feature"] == "readiness", "coefficient"].iloc[0] > 0:
    print("Higher recent-load/readiness state predicts higher send probability.")
else:
    print("Higher recent-load/readiness state predicts lower send probability.")


# ============================================================
# GRADE-ONLY EXPECTED SEND PROBABILITY
# ============================================================

grade_only_model = make_pipeline(
    StandardScaler(),
    LogisticRegression(max_iter=1000)
)

grade_only_model.fit(model_df[["grade"]], model_df["send"])

model_df["grade_only_expected_send_probability"] = grade_only_model.predict_proba(
    model_df[["grade"]]
)[:, 1]

model_df["performance_residual"] = (
    model_df["send"] - model_df["grade_only_expected_send_probability"]
)


# ============================================================
# DAILY PERFORMANCE SUMMARY
# ============================================================

daily_perf = (
    model_df.groupby("date", as_index=False)
            .agg(
                actual_send_rate=("send", "mean"),
                predicted_send_probability=("predicted_send_probability", "mean"),
                grade_only_expected_send_probability=("grade_only_expected_send_probability", "mean"),
                performance_residual=("performance_residual", "mean"),
                attempts=("send", "size"),
                mean_grade=("grade", "mean"),
                readiness=("readiness", "mean")
            )
)

daily_perf = daily_perf.sort_values("date")


# ============================================================
# SAVE OUTPUTS
# ============================================================

derived_data_dir.mkdir(parents=True, exist_ok=True)
results_df.to_csv(derived_data_dir / "tau_grid_search_results.csv", index=False)
model_df.to_csv(derived_data_dir / "attempt_level_send_model.csv", index=False)
daily_perf.to_csv(derived_data_dir / "daily_performance_readiness.csv", index=False)
best_states.to_csv(derived_data_dir / "daily_readiness_state.csv")

print()
print("Saved:")
print(f"  {derived_data_dir / 'tau_grid_search_results.csv'}")
print(f"  {derived_data_dir / 'attempt_level_send_model.csv'}")
print(f"  {derived_data_dir / 'daily_performance_readiness.csv'}")
print(f"  {derived_data_dir / 'daily_readiness_state.csv'}")


# ============================================================
# PLOT 1: TAU GRID SEARCH
# ============================================================

plt.figure(figsize=(10, 5))

plt.plot(
    results_df["tau"],
    results_df["mean_log_loss"],
    marker="o"
)

plt.axhline(
    baseline_log_loss,
    linestyle="--",
    label="Grade-only baseline"
)

plt.xlabel("Tau, days")
plt.ylabel("Held-out log loss")
plt.title("Readiness timescale search")
plt.legend()
plt.tight_layout()


# ============================================================
# PLOT 2: DAILY LOAD AND READINESS
# ============================================================

plt.figure(figsize=(12, 6))

plt.plot(
    best_states.index,
    best_states["daily_load"],
    marker="o",
    alpha=0.4,
    label="Daily load"
)

plt.plot(
    best_states.index,
    best_states["readiness"],
    linewidth=3,
    label=f"Readiness/load-history state, tau={best_tau:.0f} days"
)

plt.xlabel("Date")
plt.ylabel("Load / state value")
plt.title("Daily load and fitted readiness state")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()


# ============================================================
# PLOT 3: ACTUAL VS PREDICTED DAILY SEND RATE
# ============================================================

plt.figure(figsize=(12, 6))

plt.plot(
    daily_perf["date"],
    daily_perf["actual_send_rate"],
    marker="o",
    alpha=0.6,
    label="Actual daily send rate"
)

plt.plot(
    daily_perf["date"],
    daily_perf["predicted_send_probability"],
    marker="o",
    label="Grade + readiness prediction"
)

plt.plot(
    daily_perf["date"],
    daily_perf["grade_only_expected_send_probability"],
    marker="o",
    linestyle="--",
    label="Grade-only prediction"
)

plt.xlabel("Date")
plt.ylabel("Send probability")
plt.title("Actual vs predicted send probability")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()


# ============================================================
# PLOT 4: READINESS VS PERFORMANCE RESIDUAL
# ============================================================

plt.figure(figsize=(8, 6))

plt.scatter(
    daily_perf["readiness"],
    daily_perf["performance_residual"],
    s=20 + 8 * daily_perf["attempts"],
    alpha=0.6
)

plt.axhline(0, linestyle="--", linewidth=1)

plt.xlabel("Readiness/load-history state")
plt.ylabel("Performance residual: send - grade-only expected send probability")
plt.title("Does readiness explain above/below-grade performance?")
plt.tight_layout()


# ============================================================
# PLOT 5: PERFORMANCE RESIDUAL OVER TIME
# ============================================================

plt.figure(figsize=(12, 6))

plt.plot(
    daily_perf["date"],
    daily_perf["performance_residual"],
    marker="o",
    label="Daily performance residual"
)

plt.axhline(0, linestyle="--", linewidth=1)

plt.xlabel("Date")
plt.ylabel("Performance residual")
plt.title("Daily performance relative to grade-only expectation")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
save_all_figures(plot_output_dir)
