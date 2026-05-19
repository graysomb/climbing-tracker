import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# ---- settings ----
csv_path = "climb_data (4).csv"
group_by_outside = True   # set False to fit all climbs together

# ---- load / clean ----
df = pd.read_csv(csv_path)

# Only keep actual climb attempts: send/reps should be 0 = fail, 1 = send
df = df[df["send/reps"].isin([0, 1])].copy()

df["grade"] = pd.to_numeric(df["grade"], errors="coerce")
df["send"] = df["send/reps"].astype(float)
df = df.dropna(subset=["grade", "send"])

# ---- logistic model ----
# x50 = grade where send probability is 50%
# scale = how quickly probability drops with grade
def logistic(grade, x50, scale):
    return 1 / (1 + np.exp((grade - x50) / scale))

def fit_one(data, label):
    summary = (
        data.groupby("grade")
        .agg(
            n=("send", "size"),
            sends=("send", "sum"),
            p_send=("send", "mean")
        )
        .reset_index()
        .sort_values("grade")
    )

    # Binomial standard error for plotting/fitting weights
    summary["se"] = np.sqrt(summary["p_send"] * (1 - summary["p_send"]) / summary["n"])

    # Avoid zero uncertainty when p is exactly 0 or 1
    summary["se_fit"] = summary["se"].replace(0, np.nan)
    fallback_se = 1 / np.sqrt(4 * summary["n"])
    summary["se_fit"] = summary["se_fit"].fillna(fallback_se)

    x = summary["grade"].to_numpy()
    y = summary["p_send"].to_numpy()
    sigma = summary["se_fit"].to_numpy()

    # Initial guesses
    x50_guess = np.median(x)
    scale_guess = 1.0

    popt, pcov = curve_fit(
        logistic,
        x,
        y,
        p0=[x50_guess, scale_guess],
        sigma=sigma,
        absolute_sigma=True,
        bounds=([-np.inf, 1e-6], [np.inf, np.inf]),
        maxfev=10000
    )

    perr = np.sqrt(np.diag(pcov))

    x50, scale = popt
    x50_err, scale_err = perr

    print(f"\nFit for {label}")
    print(f"  x50   = {x50:.3f} ± {x50_err:.3f}")
    print(f"  scale = {scale:.3f} ± {scale_err:.3f}")
    print(f"  model: p(send) = 1 / (1 + exp((grade - x50) / scale))")

    return summary, popt, perr, label

# ---- fit ----
fits = []

if group_by_outside:
    for outside_value, sub in df.groupby("outside"):
        label = "outside" if outside_value == 1 else "inside"
        fits.append(fit_one(sub, label))
else:
    fits.append(fit_one(df, "all climbs"))

# ---- plot ----
plt.figure(figsize=(8, 5))

grade_grid = np.linspace(df["grade"].min(), df["grade"].max(), 400)

for summary, popt, perr, label in fits:
    plt.errorbar(
        summary["grade"],
        summary["p_send"],
        yerr=summary["se"],
        fmt="o",
        capsize=3,
        label=f"{label} data"
    )

    plt.plot(
        grade_grid,
        logistic(grade_grid, *popt),
        label=f"{label} fit"
    )

plt.xlabel("Grade")
plt.ylabel("Probability of send per try")
plt.ylim(-0.05, 1.05)
plt.title("Send probability by grade")
plt.legend()
plt.tight_layout()
plt.show()


# ============================================================
# Total V-points per week
# Uses all data
# ============================================================

date_col = "time"

df_week = df.copy()
df_week["datetime"] = pd.to_datetime(df_week[date_col])
df_week["grade"] = pd.to_numeric(df_week["grade"], errors="coerce")

df_week = df_week.dropna(subset=["datetime", "grade"]).copy()

# Week starts on Monday
df_week["week"] = df_week["datetime"].dt.to_period("W-MON").dt.start_time

weekly_vpoints = (
    df_week
    .groupby("week")
    .agg(
        total_vpoints=("grade", "sum"),
        n_attempts=("grade", "size")
    )
    .reset_index()
)

print(weekly_vpoints.head())

plt.figure(figsize=(11, 5))

plt.bar(
    weekly_vpoints["week"],
    weekly_vpoints["total_vpoints"],
    width=5
)

plt.xlabel("Week")
plt.ylabel("Total V-points")
plt.title("Total V-points per week")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

# ============================================================
# Weekly V-points transformed by inverse logistic send probability
# transformed_vpoints = grade / p_send_expected
# ============================================================

date_col = "time"

# Build lookup of fit parameters
fit_params = {}

for summary, popt, perr, label in fits:
    fit_params[label] = {
        "x50": popt[0],
        "scale": popt[1]
    }

df_week = df.copy()
df_week["datetime"] = pd.to_datetime(df_week[date_col])
df_week["grade"] = pd.to_numeric(df_week["grade"], errors="coerce")

df_week = df_week.dropna(subset=["datetime", "grade"]).copy()

# Label inside/outside
if group_by_outside:
    df_week["label"] = df_week["outside"].apply(
        lambda x: "outside" if x == 1 else "inside"
    )
else:
    df_week["label"] = "all climbs"

# Expected send probability from the relevant logistic fit
def expected_send_probability(row):
    pars = fit_params[row["label"]]
    return logistic(row["grade"], pars["x50"], pars["scale"])

df_week["p_expected_send"] = df_week.apply(expected_send_probability, axis=1)

# Avoid exploding if p is extremely tiny
min_probability = 0.001
df_week["p_expected_send_clipped"] = df_week["p_expected_send"].clip(lower=min_probability)

# Inverse-logistic transformed V-points
df_week["transformed_vpoints"] = (
    df_week["grade"] / df_week["p_expected_send_clipped"]
)

# Week starts on Monday
df_week["week"] = df_week["datetime"].dt.to_period("W-MON").dt.start_time

weekly_transformed_vpoints = (
    df_week
    .groupby("week")
    .agg(
        total_transformed_vpoints=("transformed_vpoints", "sum"),
        total_raw_vpoints=("grade", "sum"),
        n_attempts=("grade", "size"),
        mean_expected_send_prob=("p_expected_send", "mean")
    )
    .reset_index()
)

print("\nWeekly inverse-logistic transformed V-points:")
print(weekly_transformed_vpoints.head())

plt.figure(figsize=(11, 5))

plt.bar(
    weekly_transformed_vpoints["week"],
    weekly_transformed_vpoints["total_transformed_vpoints"],
    width=5
)

plt.xlabel("Week")
plt.ylabel("Total inverse-logistic transformed V-points")
plt.title("Weekly climbing load weighted by inverse expected send probability")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

fig, ax1 = plt.subplots(figsize=(11, 5))

ax1.bar(
    weekly_transformed_vpoints["week"],
    weekly_transformed_vpoints["total_transformed_vpoints"],
    width=5,
    alpha=0.65,
    label="transformed V-points"
)

ax1.set_xlabel("Week")
ax1.set_ylabel("Inverse-logistic transformed V-points")
ax1.tick_params(axis="x", rotation=45)

ax2 = ax1.twinx()

ax2.plot(
    weekly_transformed_vpoints["week"],
    weekly_transformed_vpoints["total_raw_vpoints"],
    marker="o",
    linewidth=2,
    label="raw V-points"
)

ax2.set_ylabel("Raw V-points")

plt.title("Raw vs inverse-logistic transformed weekly V-points")

fig.tight_layout()
plt.show()

# ============================================================
# Weekly inverse-logistic transformed V-points
# with tunable failure weight
#
# sends:   weight = 1
# failures weight = failure_weight
# ============================================================

date_col = "time"

failure_weight = 0.5      # tunable: 0 = ignore fails, 0.5 = half credit, 1 = same as sends
min_probability = 0.01    # prevents inverse-probability explosion

# Build lookup of fit parameters
fit_params = {}

for summary, popt, perr, label in fits:
    fit_params[label] = {
        "x50": popt[0],
        "scale": popt[1]
    }

df_week = df.copy()
df_week["datetime"] = pd.to_datetime(df_week[date_col])
df_week["grade"] = pd.to_numeric(df_week["grade"], errors="coerce")
df_week["send"] = pd.to_numeric(df_week["send"], errors="coerce")

df_week = df_week.dropna(subset=["datetime", "grade", "send"]).copy()

# Label inside/outside
if group_by_outside:
    df_week["label"] = df_week["outside"].apply(
        lambda x: "outside" if x == 1 else "inside"
    )
else:
    df_week["label"] = "all climbs"

# Expected send probability from the relevant logistic fit
def expected_send_probability(row):
    pars = fit_params[row["label"]]
    return logistic(row["grade"], pars["x50"], pars["scale"])

df_week["p_expected_send"] = df_week.apply(expected_send_probability, axis=1)

# Avoid exploding if p is extremely tiny
df_week["p_expected_send_clipped"] = df_week["p_expected_send"].clip(
    lower=min_probability
)

# Sends count as 1, failures get tunable fractional weight
df_week["attempt_weight"] = np.where(
    df_week["send"] == 1,
    1.0,
    failure_weight
)

# Inverse-logistic transformed weighted V-points
df_week["weighted_transformed_vpoints"] = (
    df_week["grade"] *
    df_week["attempt_weight"] /
    df_week["p_expected_send_clipped"]
)

# Optional raw weighted V-points, without inverse-logistic transform
df_week["weighted_raw_vpoints"] = (
    df_week["grade"] *
    df_week["attempt_weight"]
)

# Week starts on Monday
df_week["week"] = df_week["datetime"].dt.to_period("W-MON").dt.start_time

weekly_weighted_transformed_vpoints = (
    df_week
    .groupby("week")
    .agg(
        total_weighted_transformed_vpoints=("weighted_transformed_vpoints", "sum"),
        total_weighted_raw_vpoints=("weighted_raw_vpoints", "sum"),
        total_raw_vpoints=("grade", "sum"),
        n_attempts=("grade", "size"),
        n_sends=("send", "sum"),
        mean_expected_send_prob=("p_expected_send", "mean")
    )
    .reset_index()
)

print("\nWeekly weighted inverse-logistic transformed V-points:")
print(weekly_weighted_transformed_vpoints.head())

plt.figure(figsize=(11, 5))

plt.bar(
    weekly_weighted_transformed_vpoints["week"],
    weekly_weighted_transformed_vpoints["total_weighted_transformed_vpoints"],
    width=5
)

plt.xlabel("Week")
plt.ylabel("Weighted inverse-logistic transformed V-points")
plt.title(
    f"Weekly transformed climbing load\n"
    f"sends = 1, failures = {failure_weight}"
)
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

# ============================================================
# Weekly untransformed load across a range of failure weights
#
# sends:   weight = 1
# failures weight = 0.1, 0.2, ..., 0.9
# ============================================================

date_col = "time"

df_load = df.copy()
df_load["datetime"] = pd.to_datetime(df_load[date_col])
df_load["grade"] = pd.to_numeric(df_load["grade"], errors="coerce")
df_load["send"] = pd.to_numeric(df_load["send"], errors="coerce")

df_load = df_load.dropna(subset=["datetime", "grade", "send"]).copy()

# Week starts on Monday
df_load["week"] = df_load["datetime"].dt.to_period("W-MON").dt.start_time

failure_weights = np.arange(0.1, 1.0, 0.1)

weekly_loads = []

for failure_weight in failure_weights:
    temp = df_load.copy()

    temp["attempt_weight"] = np.where(
        temp["send"] == 1,
        1.0,
        failure_weight
    )

    temp["weighted_vpoints"] = temp["grade"] * temp["attempt_weight"]

    weekly = (
        temp
        .groupby("week")
        .agg(
            weekly_load=("weighted_vpoints", "sum"),
            n_attempts=("grade", "size"),
            n_sends=("send", "sum")
        )
        .reset_index()
    )

    weekly["failure_weight"] = failure_weight
    weekly_loads.append(weekly)

weekly_loads = pd.concat(weekly_loads, ignore_index=True)

print(weekly_loads.head())

# ============================================================
# Plot weekly loads for failure weights 0.1 to 0.9
# ============================================================

plt.figure(figsize=(12, 6))

for failure_weight, sub in weekly_loads.groupby("failure_weight"):
    plt.plot(
        sub["week"],
        sub["weekly_load"],
        marker="o",
        linewidth=1.5,
        label=f"fail = {failure_weight:.1f}"
    )

plt.xlabel("Week")
plt.ylabel("Weekly untransformed load")
plt.title("Weekly climbing load across failure weights")
plt.xticks(rotation=45, ha="right")
plt.legend(title="Failure weight", bbox_to_anchor=(1.05, 1), loc="upper left")

plt.tight_layout()
plt.show()

# ============================================================
# Weekly negative-log probability load
#
# Sends:   -log(p_send | grade)
# Failures: -log(p_fail | grade) = -log(1 - p_send | grade)
#
# First plot sends and failures separately
# ============================================================

date_col = "time"
log_base = "e"        # use "e" for nats, "2" for bits
min_probability = 1e-6

# Build lookup of fit parameters from existing fits
fit_params = {}

for summary, popt, perr, label in fits:
    fit_params[label] = {
        "x50": popt[0],
        "scale": popt[1]
    }

df_nll = df.copy()
df_nll["datetime"] = pd.to_datetime(df_nll[date_col])
df_nll["grade"] = pd.to_numeric(df_nll["grade"], errors="coerce")
df_nll["send"] = pd.to_numeric(df_nll["send"], errors="coerce")

df_nll = df_nll.dropna(subset=["datetime", "grade", "send"]).copy()

# Label inside/outside
if group_by_outside:
    df_nll["label"] = df_nll["outside"].apply(
        lambda x: "outside" if x == 1 else "inside"
    )
else:
    df_nll["label"] = "all climbs"

# Expected send probability from relevant logistic fit
def expected_send_probability(row):
    pars = fit_params[row["label"]]
    return logistic(row["grade"], pars["x50"], pars["scale"])

df_nll["p_send_expected"] = df_nll.apply(expected_send_probability, axis=1)

# Prevent log(0), because infinity goblins are annoying
df_nll["p_send_expected"] = df_nll["p_send_expected"].clip(
    lower=min_probability,
    upper=1 - min_probability
)

df_nll["p_fail_expected"] = 1 - df_nll["p_send_expected"]

# Choose log base
if log_base == "2":
    log_fun = np.log2
    unit_label = "bits"
else:
    log_fun = np.log
    unit_label = "nats"

# Attempt-level negative log probability
df_nll["nll_send"] = np.where(
    df_nll["send"] == 1,
    -log_fun(df_nll["p_send_expected"]),
    0.0
)

df_nll["nll_fail"] = np.where(
    df_nll["send"] == 0,
    -log_fun(df_nll["p_fail_expected"]),
    0.0
)

df_nll["nll_total"] = df_nll["nll_send"] + df_nll["nll_fail"]

# Week starts on Monday
df_nll["week"] = df_nll["datetime"].dt.to_period("W-MON").dt.start_time

weekly_nll = (
    df_nll
    .groupby("week")
    .agg(
        weekly_send_nll=("nll_send", "sum"),
        weekly_fail_nll=("nll_fail", "sum"),
        weekly_total_nll=("nll_total", "sum"),
        n_attempts=("send", "size"),
        n_sends=("send", "sum"),
        mean_p_send_expected=("p_send_expected", "mean")
    )
    .reset_index()
)

weekly_nll["n_fails"] = weekly_nll["n_attempts"] - weekly_nll["n_sends"]

print("\nWeekly negative-log probability load:")
print(weekly_nll.head())

# ============================================================
# Weekly send NLL
# ============================================================

plt.figure(figsize=(11, 5))

plt.bar(
    weekly_nll["week"],
    weekly_nll["weekly_send_nll"],
    width=5
)

plt.xlabel("Week")
plt.ylabel(f"Weekly send negative log probability [{unit_label}]")
plt.title(r"Weekly total $-\log(p_i(\mathrm{send}\mid g))$ for sends")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

# ============================================================
# Weekly fail NLL
# ============================================================

plt.figure(figsize=(11, 5))

plt.bar(
    weekly_nll["week"],
    weekly_nll["weekly_fail_nll"],
    width=5
)

plt.xlabel("Week")
plt.ylabel(f"Weekly fail negative log probability [{unit_label}]")
plt.title(r"Weekly total $-\log(p_i(\mathrm{fail}\mid g))$ for failures")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

# ============================================================
# Weekly total NL 
# ============================================================
plt.figure(figsize=(11, 5))

plt.bar(
    weekly_nll["week"],
    weekly_nll["weekly_fail_nll"]+weekly_nll["weekly_send_nll"],
    width=5
)

plt.xlabel("Week")
plt.ylabel(f"Weekly total negative log probability [{unit_label}]")
plt.title(r"Weekly total $-\log(p_i(\mathrm{fail}\mid g))$")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

# ============================================================
# Histograms of daily and weekly summed total NLL
# total NLL = send NLL + fail NLL
# ============================================================

# Daily total NLL
df_nll["day"] = df_nll["datetime"].dt.date

daily_nll = (
    df_nll
    .groupby("day")
    .agg(
        daily_total_nll=("nll_total", "sum"),
        daily_send_nll=("nll_send", "sum"),
        daily_fail_nll=("nll_fail", "sum"),
        n_attempts=("send", "size"),
        n_sends=("send", "sum")
    )
    .reset_index()
)

daily_nll["n_fails"] = daily_nll["n_attempts"] - daily_nll["n_sends"]

# Weekly total NLL
weekly_total_nll = (
    df_nll
    .groupby("week")
    .agg(
        weekly_total_nll=("nll_total", "sum"),
        weekly_send_nll=("nll_send", "sum"),
        weekly_fail_nll=("nll_fail", "sum"),
        n_attempts=("send", "size"),
        n_sends=("send", "sum")
    )
    .reset_index()
)

weekly_total_nll["n_fails"] = weekly_total_nll["n_attempts"] - weekly_total_nll["n_sends"]

print("\nDaily NLL summary:")
print(daily_nll.head())

print("\nWeekly NLL summary:")
print(weekly_total_nll.head())

# ============================================================
# Histogram of daily summed total NLL
# ============================================================

plt.figure(figsize=(10, 5))

plt.hist(
    daily_nll["daily_total_nll"],
    bins=30,
    edgecolor="black"
)

plt.xlabel(f"Daily summed total NLL [{unit_label}]")
plt.ylabel("Number of days")
plt.title("Histogram of daily summed send+fail NLL")

plt.tight_layout()
plt.show()

# ============================================================
# Daily and weekly performance
#
# performance = send surprisal - failure surprisal
#
# sends:   +[-log(p_send)]
# failures: -[-log(p_fail)]
# ============================================================

df_perf = df_nll.copy()

df_perf["performance"] = np.where(
    df_perf["send"] == 1,
    df_perf["nll_send"],
    -df_perf["nll_fail"]
)

df_perf["day"] = df_perf["datetime"].dt.date
df_perf["week"] = df_perf["datetime"].dt.to_period("W-MON").dt.start_time

daily_perf = (
    df_perf
    .groupby("day")
    .agg(
        mean_performance=("performance", "mean"),
        total_performance=("performance", "sum"),
        n_attempts=("performance", "size"),
        n_sends=("send", "sum"),
        send_nll=("nll_send", "sum"),
        fail_nll=("nll_fail", "sum")
    )
    .reset_index()
)

daily_perf["n_fails"] = daily_perf["n_attempts"] - daily_perf["n_sends"]
daily_perf["day"] = pd.to_datetime(daily_perf["day"])

weekly_perf = (
    df_perf
    .groupby("week")
    .agg(
        mean_performance=("performance", "mean"),
        total_performance=("performance", "sum"),
        n_attempts=("performance", "size"),
        n_sends=("send", "sum"),
        send_nll=("nll_send", "sum"),
        fail_nll=("nll_fail", "sum")
    )
    .reset_index()
)

weekly_perf["n_fails"] = weekly_perf["n_attempts"] - weekly_perf["n_sends"]

print("\nDaily performance:")
print(daily_perf.head())

print("\nWeekly performance:")
print(weekly_perf.head())

# ============================================================
# Daily mean performance vs time
# ============================================================

plt.figure(figsize=(11, 5))

plt.plot(
    daily_perf["day"],
    daily_perf["mean_performance"],
    marker="o",
    linewidth=1.5
)

plt.axhline(0, linestyle="--", linewidth=1)

plt.xlabel("Day")
plt.ylabel(f"Mean performance per attempt [{unit_label}]")
plt.title("Daily mean performance: send surprisal minus failure surprisal")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

# ============================================================
# Weekly mean performance vs time
# ============================================================

plt.figure(figsize=(11, 5))

plt.plot(
    weekly_perf["week"],
    weekly_perf["mean_performance"],
    marker="o",
    linewidth=1.5
)

plt.axhline(0, linestyle="--", linewidth=1)

plt.xlabel("Week")
plt.ylabel(f"Mean performance per attempt [{unit_label}]")
plt.title("Weekly mean performance: send surprisal minus failure surprisal")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

# ============================================================
# Histograms of mean performance
# ============================================================

plt.figure(figsize=(10, 5))

plt.hist(
    daily_perf["mean_performance"],
    bins=30,
    alpha=0.7,
    edgecolor="black",
    label="daily"
)

plt.axvline(0, linestyle="--", linewidth=1)

plt.xlabel(f"Mean performance per attempt [{unit_label}]")
plt.ylabel("Count")
plt.title("Histogram of daily mean performance")

plt.tight_layout()
plt.show()


plt.figure(figsize=(10, 5))

plt.hist(
    weekly_perf["mean_performance"],
    bins=20,
    alpha=0.7,
    edgecolor="black",
    label="weekly"
)

plt.axvline(0, linestyle="--", linewidth=1)

plt.xlabel(f"Mean performance per attempt [{unit_label}]")
plt.ylabel("Count")
plt.title("Histogram of weekly mean performance")

plt.tight_layout()
plt.show()

# ============================================================
# Daily and weekly load
#
# mean performance = send surprisal - failure surprisal
# mean load        = send surprisal + failure surprisal
#
# sends:   +[-log(p_send)]
# failures: +[-log(p_fail)]
# ============================================================

df_load_info = df_nll.copy()

df_load_info["info_load"] = df_load_info["nll_send"] + df_load_info["nll_fail"]

df_load_info["day"] = df_load_info["datetime"].dt.date
df_load_info["week"] = df_load_info["datetime"].dt.to_period("W-MON").dt.start_time

daily_load_info = (
    df_load_info
    .groupby("day")
    .agg(
        mean_load=("info_load", "mean"),
        total_load=("info_load", "sum"),
        n_attempts=("info_load", "size"),
        n_sends=("send", "sum"),
        send_nll=("nll_send", "sum"),
        fail_nll=("nll_fail", "sum")
    )
    .reset_index()
)

daily_load_info["n_fails"] = daily_load_info["n_attempts"] - daily_load_info["n_sends"]
daily_load_info["day"] = pd.to_datetime(daily_load_info["day"])

weekly_load_info = (
    df_load_info
    .groupby("week")
    .agg(
        mean_load=("info_load", "mean"),
        total_load=("info_load", "sum"),
        n_attempts=("info_load", "size"),
        n_sends=("send", "sum"),
        send_nll=("nll_send", "sum"),
        fail_nll=("nll_fail", "sum")
    )
    .reset_index()
)

weekly_load_info["n_fails"] = weekly_load_info["n_attempts"] - weekly_load_info["n_sends"]

print("\nDaily information load:")
print(daily_load_info.head())

print("\nWeekly information load:")
print(weekly_load_info.head())

plt.figure(figsize=(11, 5))

plt.plot(
    daily_load_info["day"],
    daily_load_info["mean_load"],
    marker="o",
    linewidth=1.5
)

plt.xlabel("Day")
plt.ylabel(f"Mean information load per attempt [{unit_label}]")
plt.title("Daily mean load: send surprise + failure surprise")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

plt.figure(figsize=(11, 5))

plt.plot(
    weekly_load_info["week"],
    weekly_load_info["mean_load"],
    marker="o",
    linewidth=1.5
)

plt.xlabel("Week")
plt.ylabel(f"Mean information load per attempt [{unit_label}]")
plt.title("Weekly mean load: send surprise + failure surprise")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

plt.figure(figsize=(10, 5))

plt.hist(
    daily_load_info["mean_load"],
    bins=30,
    alpha=0.7,
    edgecolor="black"
)

plt.xlabel(f"Daily mean information load per attempt [{unit_label}]")
plt.ylabel("Number of days")
plt.title("Histogram of daily mean load")

plt.tight_layout()
plt.show()


plt.figure(figsize=(10, 5))

plt.hist(
    weekly_load_info["mean_load"],
    bins=20,
    alpha=0.7,
    edgecolor="black"
)

plt.xlabel(f"Weekly mean information load per attempt [{unit_label}]")
plt.ylabel("Number of weeks")
plt.title("Histogram of weekly mean load")

plt.tight_layout()
plt.show()

plt.figure(figsize=(10, 5))

plt.hist(
    daily_load_info["total_load"],
    bins=30,
    alpha=0.7,
    edgecolor="black"
)

plt.xlabel(f"Daily total information load [{unit_label}]")
plt.ylabel("Number of days")
plt.title("Histogram of daily total load")

plt.tight_layout()
plt.show()


plt.figure(figsize=(10, 5))

plt.hist(
    weekly_load_info["total_load"],
    bins=20,
    alpha=0.7,
    edgecolor="black"
)

plt.xlabel(f"Weekly total information load [{unit_label}]")
plt.ylabel("Number of weeks")
plt.title("Histogram of weekly total load")

plt.tight_layout()
plt.show()

plt.figure(figsize=(11, 5))

plt.bar(
    weekly_load_info["week"],
    weekly_load_info["total_load"],
    width=5
)

plt.xlabel("Week")
plt.ylabel(f"Total information load [{unit_label}]")
plt.title("Weekly total information load")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

# ============================================================
# ACWR: acute load / chronic load
#
# Acute  = trailing 7-day load
# Chronic = trailing 28-day load
#
# For total_load: rolling sums
# For mean_load: rolling means over active/calendar days
# ============================================================

acute_days = 7
chronic_days = 28

injury_dates = pd.to_datetime([
    "2025-09-02",
    "2025-09-12",
    "2025-11-14",
    "2025-11-16",
    "2025-08-19",
    "2025-04-18",
    "2025-02-04",
    "2026-01-23",
    "2026-01-16",
    "2025-07-10",
    "2025-05-09",
    "2025-04-25",
    "2025-03-04",
    "2025-02-07",
    "2024-03-26",
    "2023-05-16",
    "2023-04-06",
])

# Start from daily information load
acwr_df = daily_load_info.copy()
acwr_df["day"] = pd.to_datetime(acwr_df["day"])
acwr_df = acwr_df.sort_values("day")

# Fill missing calendar days so rolling windows mean actual 7d / 28d windows
full_days = pd.date_range(acwr_df["day"].min(), acwr_df["day"].max(), freq="D")

acwr_df = (
    acwr_df
    .set_index("day")
    .reindex(full_days)
    .rename_axis("day")
    .reset_index()
)

# For total load, missing days are zero-load rest days
acwr_df["total_load"] = acwr_df["total_load"].fillna(0)
acwr_df["n_attempts"] = acwr_df["n_attempts"].fillna(0)
acwr_df["n_sends"] = acwr_df["n_sends"].fillna(0)
acwr_df["n_fails"] = acwr_df["n_fails"].fillna(0)

# For mean load, missing days are rest days.
# You have two reasonable options:
#   1. treat rest days as 0 mean load
#   2. ignore rest days in the rolling mean
#
# This uses option 1 by default.
mean_load_rest_value = 0
acwr_df["mean_load"] = acwr_df["mean_load"].fillna(mean_load_rest_value)

# ----------------------------
# ACWR for total load
# ----------------------------

acwr_df["acute_total_load"] = (
    acwr_df["total_load"]
    .rolling(acute_days, min_periods=acute_days)
    .sum()
)

acwr_df["chronic_total_load"] = (
    acwr_df["total_load"]
    .rolling(chronic_days, min_periods=chronic_days)
    .sum()
)

acwr_df["acwr_total_load"] = (
    acwr_df["acute_total_load"] /
    acwr_df["chronic_total_load"]
)

# ----------------------------
# ACWR for mean load
# ----------------------------

acwr_df["acute_mean_load"] = (
    acwr_df["mean_load"]
    .rolling(acute_days, min_periods=acute_days)
    .mean()
)

acwr_df["chronic_mean_load"] = (
    acwr_df["mean_load"]
    .rolling(chronic_days, min_periods=chronic_days)
    .mean()
)

acwr_df["acwr_mean_load"] = (
    acwr_df["acute_mean_load"] /
    acwr_df["chronic_mean_load"]
)

# Avoid divide-by-zero goblins
acwr_df = acwr_df.replace([np.inf, -np.inf], np.nan)

print("\nACWR dataframe:")
print(acwr_df.head(35))

# ============================================================
# Helper: plot ACWR with injury X markers
# ============================================================

def plot_acwr_with_injuries(data, y_col, ylabel, title):
    plot_df = data.dropna(subset=[y_col]).copy()

    plt.figure(figsize=(12, 5))

    plt.plot(
        plot_df["day"],
        plot_df[y_col],
        marker="o",
        linewidth=1.5,
        markersize=3,
        label=ylabel
    )

    # ACWR reference lines
    plt.axhline(0.8, linestyle=":", linewidth=2, label="ACWR = 0.8")
    plt.axhline(1.3, linestyle=":", linewidth=2, label="ACWR = 1.3")

    # Injury markers: put X at the ACWR value on/near that date
    for injury_date in injury_dates:
        nearest_idx = (plot_df["day"] - injury_date).abs().idxmin()

        x = plot_df.loc[nearest_idx, "day"]
        y = plot_df.loc[nearest_idx, y_col]

        plt.scatter(
            x,
            y,
            marker="x",
            s=120,
            linewidths=3,
            zorder=5
        )

        plt.text(
            x,
            y,
            " injury",
            fontsize=9,
            va="bottom",
            ha="left"
        )

    plt.xlabel("Date")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(rotation=45, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.show()

    # ============================================================
# ACWR vs time: mean load
# ============================================================

plot_acwr_with_injuries(
    acwr_df,
    y_col="acwr_mean_load",
    ylabel="ACWR: mean load",
    title="ACWR over time for mean information load"
)

# ============================================================
# ACWR vs time: total load
# ============================================================

plot_acwr_with_injuries(
    acwr_df,
    y_col="acwr_total_load",
    ylabel="ACWR: total load",
    title="ACWR over time for total information load"
)

# ============================================================
# Histograms of ACWR
# ============================================================

plt.figure(figsize=(10, 5))

plt.hist(
    acwr_df["acwr_mean_load"].dropna(),
    bins=25,
    edgecolor="black",
    alpha=0.75
)

plt.axvline(0.8, linestyle=":", linewidth=2, label="ACWR = 0.8")
plt.axvline(1.3, linestyle=":", linewidth=2, label="ACWR = 1.3")

plt.xlabel("ACWR: mean load")
plt.ylabel("Count")
plt.title("Histogram of ACWR for mean information load")
plt.legend()
plt.tight_layout()
plt.show()


plt.figure(figsize=(10, 5))

plt.hist(
    acwr_df["acwr_total_load"].dropna(),
    bins=25,
    edgecolor="black",
    alpha=0.75
)

plt.axvline(0.8, linestyle=":", linewidth=2, label="ACWR = 0.8")
plt.axvline(1.3, linestyle=":", linewidth=2, label="ACWR = 1.3")

plt.xlabel("ACWR: total load")
plt.ylabel("Count")
plt.title("Histogram of ACWR for total information load")
plt.legend()
plt.tight_layout()
plt.show()

# ============================================================
# Load values on injury dates
# ============================================================


# Make sure week column is datetime
weekly_load_info = weekly_load_info.copy()
weekly_load_info["week"] = pd.to_datetime(weekly_load_info["week"])

# Match the same weekly convention used earlier:
# df["datetime"].dt.to_period("W-MON").dt.start_time
injury_df = pd.DataFrame({"injury_date": injury_dates})
injury_df["week"] = injury_df["injury_date"].dt.to_period("W-MON").dt.start_time

injury_week_loads = injury_df.merge(
    weekly_load_info[["week", "mean_load", "total_load", "n_attempts", "n_sends", "n_fails"]],
    on="week",
    how="left"
)

print("\nWeekly loads at injury dates:")
print(injury_week_loads)

# ============================================================
# Histogram of mean weekly loads at injury dates
# ============================================================

injury_mean_loads = injury_week_loads["mean_load"].dropna()

plt.figure(figsize=(10, 5))

plt.hist(
    injury_mean_loads,
    bins=10,
    edgecolor="black"
)

plt.xlabel(f"Mean weekly load at injury date [{unit_label}]")
plt.ylabel("Number of injuries")
plt.title("Histogram of mean weekly load at injury dates")

plt.tight_layout()
plt.show()
# ============================================================
# Histogram of total weekly loads at injury dates
# ============================================================

injury_total_loads = injury_week_loads["total_load"].dropna()

plt.figure(figsize=(10, 5))

plt.hist(
    injury_total_loads,
    bins=10,
    edgecolor="black"
)

plt.xlabel(f"Total weekly load at injury date [{unit_label}]")
plt.ylabel("Number of injuries")
plt.title("Histogram of total weekly load at injury dates")

plt.tight_layout()
plt.show()

# ============================================================
# Weekly mean load histogram with injury-week loads overlaid
# ============================================================

plt.figure(figsize=(10, 5))

counts, bins, patches = plt.hist(
    weekly_load_info["mean_load"].dropna(),
    bins=20,
    alpha=0.7,
    edgecolor="black",
    label="all weeks"
)

# Plot injury loads as red Xs along the bottom
y_x = np.full(len(injury_mean_loads), max(counts) * 0.05)

plt.scatter(
    injury_mean_loads,
    y_x,
    marker="x",
    s=90,
    linewidths=2,
    label="injury weeks"
)

plt.xlabel(f"Mean weekly load [{unit_label}]")
plt.ylabel("Number of weeks")
plt.title("Weekly mean load distribution with injury weeks")
plt.legend()

plt.tight_layout()
plt.show()

# ============================================================
# Weekly total load histogram with injury-week loads overlaid
# ============================================================

plt.figure(figsize=(10, 5))

counts, bins, patches = plt.hist(
    weekly_load_info["total_load"].dropna(),
    bins=20,
    alpha=0.7,
    edgecolor="black",
    label="all weeks"
)

# Plot injury loads as red Xs along the bottom
y_x = np.full(len(injury_total_loads), max(counts) * 0.05)

plt.scatter(
    injury_total_loads,
    y_x,
    marker="x",
    s=90,
    linewidths=2,
    label="injury weeks"
)

plt.xlabel(f"Total weekly load [{unit_label}]")
plt.ylabel("Number of weeks")
plt.title("Weekly total load distribution with injury weeks")
plt.legend()

plt.tight_layout()
plt.show()