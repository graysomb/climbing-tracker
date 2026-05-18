import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Optional model fitting
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import classification_report, roc_auc_score


# ============================================================
# SETTINGS
# ============================================================

csv_path = "climb_data (4).csv"

filter_to_climbing_type = True
climbing_type_value = 0

drop_missing_grades = True

min_days_for_30 = 7
min_days_for_90 = 14

# Week definition:
# "W-SUN" means weeks end on Sunday.
# So each injury marker is placed at the Sunday ending that zero-load week.
week_rule = "W-SUN"


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(csv_path)

df["time"] = pd.to_datetime(df["time"])
df["date"] = df["time"].dt.floor("D")

if filter_to_climbing_type and "type" in df.columns:
    df = df[df["type"] == climbing_type_value].copy()

if drop_missing_grades:
    df = df.dropna(subset=["grade"]).copy()


# ============================================================
# DEFINE LOAD
# ============================================================

# Every logged climb attempt counts as one try, send or fail
df["tries"] = 1

# Load score for each attempt
df["score"] = df["tries"] * df["grade"]

if "send/reps" in df.columns:
    df["is_send"] = (df["send/reps"] > 0).astype(int)
else:
    df["is_send"] = np.nan


# ============================================================
# DAILY SUMMARY
# ============================================================

daily = (
    df.groupby("date", as_index=False)
      .agg(
          daily_score=("score", "sum"),
          attempts=("tries", "sum"),
          sends=("is_send", "sum"),
          mean_grade=("grade", "mean"),
          max_grade=("grade", "max")
      )
)

daily = daily.sort_values("date")

# Fill missing calendar days with zero load
daily = daily.set_index("date").asfreq("D")

for col in ["daily_score", "attempts", "sends"]:
    daily[col] = daily[col].fillna(0)


# ============================================================
# PAST-ONLY MOVING AVERAGES
# ============================================================

past_load = daily["daily_score"].shift(1)

daily["ma_7"] = past_load.rolling(window=7, min_periods=1).mean()
daily["ma_30"] = past_load.rolling(window=30, min_periods=1).mean()
daily["ma_90"] = past_load.rolling(window=90, min_periods=1).mean()


# ============================================================
# ACUTE / CHRONIC WORKLOAD
# ============================================================

# Acute load: total previous 7 days
daily["acute_7"] = past_load.rolling(window=7, min_periods=1).sum()

# Chronic load: mean previous 30/90 days
daily["chronic_30_daily"] = past_load.rolling(
    window=30,
    min_periods=min_days_for_30
).mean()

daily["chronic_90_daily"] = past_load.rolling(
    window=90,
    min_periods=min_days_for_90
).mean()

# Expected 7-day load from chronic baseline
daily["chronic_30_expected_7"] = daily["chronic_30_daily"] * 7
daily["chronic_90_expected_7"] = daily["chronic_90_daily"] * 7

daily["acwr_7_30"] = daily["acute_7"] / daily["chronic_30_expected_7"]
daily["acwr_7_90"] = daily["acute_7"] / daily["chronic_90_expected_7"]

daily[["acwr_7_30", "acwr_7_90"]] = daily[
    ["acwr_7_30", "acwr_7_90"]
].replace([np.inf, -np.inf], np.nan)


# ============================================================
# ABSOLUTE AND STANDARDIZED OVERSHOOT
# ============================================================

daily["ramp_7_30"] = daily["acute_7"] - daily["chronic_30_expected_7"]
daily["ramp_7_90"] = daily["acute_7"] - daily["chronic_90_expected_7"]

daily["chronic_30_sd"] = past_load.rolling(
    window=30,
    min_periods=min_days_for_30
).std()

daily["chronic_90_sd"] = past_load.rolling(
    window=90,
    min_periods=min_days_for_90
).std()

daily["chronic_30_sd_7day"] = daily["chronic_30_sd"] * np.sqrt(7)
daily["chronic_90_sd_7day"] = daily["chronic_90_sd"] * np.sqrt(7)

daily["z_overshoot_7_30"] = (
    daily["acute_7"] - daily["chronic_30_expected_7"]
) / daily["chronic_30_sd_7day"]

daily["z_overshoot_7_90"] = (
    daily["acute_7"] - daily["chronic_90_expected_7"]
) / daily["chronic_90_sd_7day"]

daily[["z_overshoot_7_30", "z_overshoot_7_90"]] = daily[
    ["z_overshoot_7_30", "z_overshoot_7_90"]
].replace([np.inf, -np.inf], np.nan)


# ============================================================
# DEFINE INJURY WEEKS
# ============================================================

# Weekly load. A week with total load == 0 is labeled as injury.
weekly = pd.DataFrame()
weekly["week_load"] = daily["daily_score"].resample(week_rule).sum()
weekly["injury_week"] = weekly["week_load"].eq(0).astype(int)

# For plotting, put injury Xs at the end of each zero-load week
injury_dates = weekly.index[weekly["injury_week"] == 1]

# Use y=0 for injury markers on load plots
injury_y_zero = np.zeros(len(injury_dates))


# ============================================================
# BUILD WEEKLY MODELING DATASET
# ============================================================

# We want to predict whether the upcoming week is an injury week
# using workload features known BEFORE that week starts.
#
# For each week ending date, the prediction date is 7 days earlier:
# e.g. for a week ending Sunday, use the previous Sunday as the feature date.

feature_cols = [
    "acute_7",
    "chronic_30_expected_7",
    "chronic_90_expected_7",
    "acwr_7_30",
    "acwr_7_90",
    "ramp_7_30",
    "ramp_7_90",
    "z_overshoot_7_30",
    "z_overshoot_7_90",
    "ma_7",
    "ma_30",
    "ma_90"
]

model_rows = []

for week_end in weekly.index:
    feature_date = week_end - pd.Timedelta(days=7)

    if feature_date in daily.index:
        row = daily.loc[feature_date, feature_cols].copy()
        row["week_end"] = week_end
        row["week_load"] = weekly.loc[week_end, "week_load"]
        row["injury_week"] = weekly.loc[week_end, "injury_week"]
        model_rows.append(row)

model_df = pd.DataFrame(model_rows)

# Clean modeling data
model_df = model_df.replace([np.inf, -np.inf], np.nan)
model_df = model_df.dropna(subset=feature_cols + ["injury_week"]).copy()

print()
print("Weekly injury labels:")
print(weekly.tail(20))

print()
print(f"Number of injury weeks: {weekly['injury_week'].sum()}")
print(f"Number of non-injury weeks: {(weekly['injury_week'] == 0).sum()}")


# ============================================================
# FIT SIMPLE INJURY MODEL
# ============================================================

can_fit_model = (
    len(model_df) >= 10 and
    model_df["injury_week"].nunique() == 2
)

if can_fit_model:
    X = model_df[feature_cols]
    y = model_df["injury_week"]

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=1000
        )
    )

    model.fit(X, y)

    model_df["predicted_injury_probability"] = model.predict_proba(X)[:, 1]

    print()
    print("In-sample model performance:")
    print(classification_report(y, model.predict(X)))

    try:
        auc = roc_auc_score(y, model_df["predicted_injury_probability"])
        print(f"ROC AUC: {auc:.3f}")
    except ValueError:
        print("ROC AUC could not be computed.")

    # Put model predictions back onto weekly df
    weekly["predicted_injury_probability"] = np.nan
    weekly.loc[
        model_df["week_end"],
        "predicted_injury_probability"
    ] = model_df["predicted_injury_probability"].values

else:
    print()
    print("Not enough data/classes to fit injury model.")
    print("You need at least some injury weeks and some non-injury weeks after dropping NaNs.")
    weekly["predicted_injury_probability"] = np.nan


# ============================================================
# SAVE OUTPUT
# ============================================================

daily.to_csv("climbing_daily_load_analysis.csv")
weekly.to_csv("climbing_weekly_injury_analysis.csv")

if len(model_df) > 0:
    model_df.to_csv("climbing_injury_model_data.csv", index=False)

print()
print("Saved:")
print("  climbing_daily_load_analysis.csv")
print("  climbing_weekly_injury_analysis.csv")
print("  climbing_injury_model_data.csv")


# ============================================================
# PLOT 1: DAILY LOAD + MOVING AVERAGES + INJURY Xs
# ============================================================

plt.figure(figsize=(13, 6))

plt.plot(
    daily.index,
    daily["daily_score"],
    marker="o",
    linewidth=1,
    alpha=0.45,
    label="Daily load"
)

plt.plot(
    daily.index,
    daily["ma_7"],
    linewidth=2,
    label="Past-only 7-day average"
)

plt.plot(
    daily.index,
    daily["ma_30"],
    linewidth=3,
    label="Past-only 30-day average"
)

plt.plot(
    daily.index,
    daily["ma_90"],
    linewidth=3,
    label="Past-only 90-day average"
)

plt.scatter(
    injury_dates,
    injury_y_zero,
    marker="x",
    s=100,
    linewidths=3,
    label="Injury week: zero weekly load"
)

plt.xlabel("Date")
plt.ylabel("Load = attempts × grade")
plt.title("Climbing load with past-only moving averages and injury weeks")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# ============================================================
# PLOT 2: ACUTE/CHRONIC RATIO + INJURY Xs
# ============================================================

plt.figure(figsize=(13, 6))

plt.plot(
    daily.index,
    daily["acwr_7_30"],
    linewidth=2,
    label="7-day load / 30-day expected 7-day load"
)

plt.plot(
    daily.index,
    daily["acwr_7_90"],
    linewidth=2,
    label="7-day load / 90-day expected 7-day load"
)

plt.axhline(1.0, linestyle="--", linewidth=1, label="Baseline")
plt.axhline(1.3, linestyle="--", linewidth=1, label="Moderate overshoot")
plt.axhline(1.5, linestyle="--", linewidth=1, label="Large overshoot")
plt.axhline(0.8, linestyle="--", linewidth=1, label="Under baseline")

# Put injury Xs near bottom of ratio plot
ratio_marker_y = np.full(len(injury_dates), 0.05)

plt.scatter(
    injury_dates,
    ratio_marker_y,
    marker="x",
    s=100,
    linewidths=3,
    label="Injury week: zero weekly load"
)

plt.xlabel("Date")
plt.ylabel("Acute:chronic workload ratio")
plt.title("Workload overshoot with injury-week markers")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# ============================================================
# PLOT 3: ABSOLUTE OVERSHOOT + INJURY Xs
# ============================================================

plt.figure(figsize=(13, 6))

plt.plot(
    daily.index,
    daily["ramp_7_30"],
    linewidth=2,
    label="7-day load minus 30-day expected load"
)

plt.plot(
    daily.index,
    daily["ramp_7_90"],
    linewidth=2,
    label="7-day load minus 90-day expected load"
)

plt.axhline(0, linestyle="--", linewidth=1)

plt.scatter(
    injury_dates,
    np.zeros(len(injury_dates)),
    marker="x",
    s=100,
    linewidths=3,
    label="Injury week: zero weekly load"
)

plt.xlabel("Date")
plt.ylabel("Load above/below baseline")
plt.title("Absolute climbing load overshoot with injury-week markers")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# ============================================================
# PLOT 4: Z-SCORE OVERSHOOT + INJURY Xs
# ============================================================

plt.figure(figsize=(13, 6))

plt.plot(
    daily.index,
    daily["z_overshoot_7_30"],
    linewidth=2,
    label="Z overshoot vs 30-day baseline"
)

plt.plot(
    daily.index,
    daily["z_overshoot_7_90"],
    linewidth=2,
    label="Z overshoot vs 90-day baseline"
)

plt.axhline(0, linestyle="--", linewidth=1, label="Baseline")
plt.axhline(1, linestyle="--", linewidth=1, label="+1 SD")
plt.axhline(2, linestyle="--", linewidth=1, label="+2 SD")

plt.scatter(
    injury_dates,
    np.zeros(len(injury_dates)),
    marker="x",
    s=100,
    linewidths=3,
    label="Injury week: zero weekly load"
)

plt.xlabel("Date")
plt.ylabel("Standardized overshoot")
plt.title("Standardized climbing load overshoot with injury-week markers")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# ============================================================
# PLOT 5: PREDICTED INJURY PROBABILITY
# ============================================================

if can_fit_model:
    plt.figure(figsize=(13, 6))

    plt.plot(
        weekly.index,
        weekly["predicted_injury_probability"],
        marker="o",
        linewidth=2,
        label="Predicted injury probability"
    )

    plt.scatter(
        injury_dates,
        np.ones(len(injury_dates)),
        marker="x",
        s=100,
        linewidths=3,
        label="Observed injury week"
    )

    plt.ylim(-0.05, 1.05)
    plt.xlabel("Week ending")
    plt.ylabel("Predicted injury probability")
    plt.title("Simple fitted injury-week probability model")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()