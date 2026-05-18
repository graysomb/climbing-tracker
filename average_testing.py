import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# SETTINGS
# ============================================================

csv_path = "climb_data (4).csv"

# Set this to True if type == 0 means climbing and you want only those rows
filter_to_climbing_type = True
climbing_type_value = 0

# Optional: only include rows with real grades
drop_missing_grades = True

# Minimum number of past days required before calculating chronic averages
min_days_for_30 = 7
min_days_for_90 = 14


# ============================================================
# LOAD DATA
# ============================================================

df = pd.read_csv(csv_path)

# Convert time to datetime
df["time"] = pd.to_datetime(df["time"])

# Make calendar-date column
df["date"] = df["time"].dt.floor("D")

# Optional filter to climbing rows
if filter_to_climbing_type and "type" in df.columns:
    df = df[df["type"] == climbing_type_value].copy()

# Optional remove rows without grades
if drop_missing_grades:
    df = df.dropna(subset=["grade"]).copy()


# ============================================================
# DEFINE LOAD
# ============================================================

# Every row is one attempt, whether send or fail
df["tries"] = 1

# Load score for each attempt
df["score"] = df["tries"] * df["grade"]

# Optional useful columns
# If send/reps > 0 means send, this counts sends
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

# Fill load/count columns with zero on rest days
for col in ["daily_score", "attempts", "sends"]:
    daily[col] = daily[col].fillna(0)

# Leave grade columns as NaN on rest days
# because there was no mean/max grade that day


# ============================================================
# PAST-ONLY MOVING AVERAGES
# ============================================================

# Shift first so today's predictors only use previous days
past_load = daily["daily_score"].shift(1)

daily["ma_7"] = past_load.rolling(window=7, min_periods=1).mean()
daily["ma_30"] = past_load.rolling(window=30, min_periods=1).mean()
daily["ma_90"] = past_load.rolling(window=90, min_periods=1).mean()


# ============================================================
# ACUTE / CHRONIC WORKLOAD
# ============================================================

# Acute load: total load over previous 7 days
daily["acute_7"] = past_load.rolling(window=7, min_periods=1).sum()

# Chronic load: average daily load over previous 30 and 90 days
daily["chronic_30_daily"] = past_load.rolling(
    window=30,
    min_periods=min_days_for_30
).mean()

daily["chronic_90_daily"] = past_load.rolling(
    window=90,
    min_periods=min_days_for_90
).mean()

# Convert chronic daily load to expected 7-day load
# This puts acute and chronic on the same scale
daily["chronic_30_expected_7"] = daily["chronic_30_daily"] * 7
daily["chronic_90_expected_7"] = daily["chronic_90_daily"] * 7

# Acute:chronic workload ratios
daily["acwr_7_30"] = daily["acute_7"] / daily["chronic_30_expected_7"]
daily["acwr_7_90"] = daily["acute_7"] / daily["chronic_90_expected_7"]

# Replace infinities caused by division by zero
daily[["acwr_7_30", "acwr_7_90"]] = daily[["acwr_7_30", "acwr_7_90"]].replace(
    [np.inf, -np.inf],
    np.nan
)


# ============================================================
# ABSOLUTE LOAD OVERSHOOT
# ============================================================

daily["ramp_7_30"] = daily["acute_7"] - daily["chronic_30_expected_7"]
daily["ramp_7_90"] = daily["acute_7"] - daily["chronic_90_expected_7"]


# ============================================================
# Z-SCORE STYLE OVERSHOOT
# ============================================================

# Standard deviation of daily load over the past 30/90 days
daily["chronic_30_sd"] = past_load.rolling(
    window=30,
    min_periods=min_days_for_30
).std()

daily["chronic_90_sd"] = past_load.rolling(
    window=90,
    min_periods=min_days_for_90
).std()

# Convert daily-load SD to approximate 7-day-load SD
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
# SIMPLE RISK FLAGS
# ============================================================

# These are not true injury probabilities.
# They are rough workload warning flags.

daily["risk_flag_7_30"] = "normal"

daily.loc[daily["acwr_7_30"] > 1.3, "risk_flag_7_30"] = "moderate overshoot"
daily.loc[daily["acwr_7_30"] > 1.5, "risk_flag_7_30"] = "large overshoot"
daily.loc[daily["acwr_7_30"] < 0.8, "risk_flag_7_30"] = "under baseline"

daily["risk_flag_7_90"] = "normal"

daily.loc[daily["acwr_7_90"] > 1.3, "risk_flag_7_90"] = "moderate overshoot"
daily.loc[daily["acwr_7_90"] > 1.5, "risk_flag_7_90"] = "large overshoot"
daily.loc[daily["acwr_7_90"] < 0.8, "risk_flag_7_90"] = "under baseline"


# ============================================================
# SAVE OUTPUT
# ============================================================

daily.to_csv("climbing_load_analysis.csv")

print("Saved output to climbing_load_analysis.csv")
print()
print(daily.tail(10)[[
    "daily_score",
    "acute_7",
    "chronic_30_expected_7",
    "chronic_90_expected_7",
    "acwr_7_30",
    "acwr_7_90",
    "z_overshoot_7_30",
    "z_overshoot_7_90",
    "risk_flag_7_30",
    "risk_flag_7_90"
]])


# ============================================================
# PLOT 1: DAILY LOAD AND MOVING AVERAGES
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

plt.xlabel("Date")
plt.ylabel("Load = attempts × grade")
plt.title("Climbing load with past-only moving averages")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# ============================================================
# PLOT 2: ACUTE/CHRONIC WORKLOAD RATIO
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

plt.xlabel("Date")
plt.ylabel("Acute:chronic workload ratio")
plt.title("Past-only climbing workload overshoot")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# ============================================================
# PLOT 3: ABSOLUTE OVERSHOOT
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

plt.xlabel("Date")
plt.ylabel("Load above/below baseline")
plt.title("Absolute climbing load overshoot")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# ============================================================
# PLOT 4: Z-SCORE OVERSHOOT
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

plt.xlabel("Date")
plt.ylabel("Standardized overshoot")
plt.title("Standardized climbing load overshoot")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()