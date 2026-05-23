import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.optimize import curve_fit, minimize
from scipy.stats import chi2, mannwhitneyu

# ---- settings ----
csv_path = "climb_data (4).csv"
group_by_outside = True   # set False to fit all climbs together
plot_output_dir = Path("model3_plot_outputs")

plt.rcParams["figure.max_open_warning"] = 0

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


def slugify_title(title):
    title = title.lower().strip()
    chars = []

    for char in title:
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "_":
            chars.append("_")

    slug = "".join(chars).strip("_")
    return slug[:80] or "plot"


def figure_title(fig):
    if fig._suptitle is not None:
        title = fig._suptitle.get_text()
        if title:
            return title

    for ax in fig.axes:
        title = ax.get_title()
        if title:
            return title

    return "plot"


def save_all_figures(output_dir=plot_output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    for index, fig_num in enumerate(plt.get_fignums(), start=1):
        fig = plt.figure(fig_num)
        title = figure_title(fig)
        file_name = f"{index:02d}_{slugify_title(title)}.png"
        output_path = output_dir / file_name

        fig.savefig(output_path, dpi=200, bbox_inches="tight")
        saved_paths.append(output_path)

    plt.close("all")

    print()
    print(f"Saved {len(saved_paths)} plot PNG files to {output_dir}:")
    for output_path in saved_paths:
        print(f"  {output_path}")


def add_injury_markers(data, x_col, y_cols, ax=None, label="injury", annotate=False):
    if ax is None:
        ax = plt.gca()

    if isinstance(y_cols, str):
        y_cols = [y_cols]

    label_added = False

    for y_col in y_cols:
        if x_col not in data.columns or y_col not in data.columns:
            continue

        plot_df = data[[x_col, y_col]].dropna().copy()
        if plot_df.empty:
            continue

        plot_df[x_col] = pd.to_datetime(plot_df[x_col])
        plot_df = plot_df.sort_values(x_col)

        for injury_date in injury_dates:
            nearest_idx = (plot_df[x_col] - injury_date).abs().idxmin()
            x = plot_df.loc[nearest_idx, x_col]
            y = plot_df.loc[nearest_idx, y_col]
            marker_label = label if label and not label_added else None

            ax.scatter(
                x,
                y,
                marker="x",
                s=120,
                linewidths=3,
                color="red",
                zorder=5,
                label=marker_label
            )

            if annotate:
                ax.text(
                    x,
                    y,
                    " injury",
                    fontsize=9,
                    va="bottom",
                    ha="left"
                )

            if marker_label:
                label_added = True

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

add_injury_markers(weekly_vpoints, "week", "total_vpoints")

plt.xlabel("Week")
plt.ylabel("Total V-points")
plt.title("Total V-points per week")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

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

add_injury_markers(
    weekly_transformed_vpoints,
    "week",
    "total_transformed_vpoints"
)

plt.xlabel("Week")
plt.ylabel("Total inverse-logistic transformed V-points")
plt.title("Weekly climbing load weighted by inverse expected send probability")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

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

add_injury_markers(
    weekly_transformed_vpoints,
    "week",
    "total_transformed_vpoints",
    ax=ax1
)
add_injury_markers(
    weekly_transformed_vpoints,
    "week",
    "total_raw_vpoints",
    ax=ax2
)

plt.title("Raw vs inverse-logistic transformed weekly V-points")

fig.tight_layout()

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

add_injury_markers(
    weekly_weighted_transformed_vpoints,
    "week",
    "total_weighted_transformed_vpoints"
)

plt.xlabel("Week")
plt.ylabel("Weighted inverse-logistic transformed V-points")
plt.title(
    f"Weekly transformed climbing load\n"
    f"sends = 1, failures = {failure_weight}"
)
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

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
    add_injury_markers(sub, "week", "weekly_load", label=None)

plt.xlabel("Week")
plt.ylabel("Weekly untransformed load")
plt.title("Weekly climbing load across failure weights")
plt.xticks(rotation=45, ha="right")
plt.legend(title="Failure weight", bbox_to_anchor=(1.05, 1), loc="upper left")

plt.tight_layout()

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

# Prevent log(0).
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

# ============================================================
# Performance/load/surprise vs duration-normalized session time
#
# Session start = first climb of the day
# Session end   = last climb of the day
# Duration      = end - start
#
# performance = surprise_send - surprise_fail
# load        = surprise_send + surprise_fail
# ============================================================

phase_bin_width = 0.05

df_session_phase = df_nll.copy()
df_session_phase["session_date"] = df_session_phase["datetime"].dt.date

session_summary = (
    df_session_phase
    .groupby("session_date")
    .agg(
        session_start=("datetime", "min"),
        session_end=("datetime", "max"),
        mean_time=("datetime", "mean"),
        n_attempts=("datetime", "size")
    )
    .reset_index()
)

session_summary["session_duration_min"] = (
    session_summary["session_end"] - session_summary["session_start"]
).dt.total_seconds() / 60

df_session_phase = df_session_phase.merge(
    session_summary,
    on="session_date",
    how="left"
)

df_session_phase["minutes_from_session_mean"] = (
    df_session_phase["datetime"] - df_session_phase["mean_time"]
).dt.total_seconds() / 60

df_session_phase["session_phase_centered"] = (
    df_session_phase["minutes_from_session_mean"] /
    df_session_phase["session_duration_min"]
)

df_session_phase = (
    df_session_phase
    .replace([np.inf, -np.inf], np.nan)
    .dropna(subset=["session_phase_centered"])
    .copy()
)

df_session_phase["performance"] = (
    df_session_phase["nll_send"] - df_session_phase["nll_fail"]
)
df_session_phase["load"] = (
    df_session_phase["nll_send"] + df_session_phase["nll_fail"]
)
df_session_phase["surprise_send"] = df_session_phase["nll_send"]
df_session_phase["surprise_fail"] = df_session_phase["nll_fail"]

def standard_error(values):
    if len(values) <= 1:
        return np.nan
    return values.std(ddof=1) / np.sqrt(len(values))

phase_plot_specs = [
    ("mean_performance", "se_performance", "Performance"),
    ("mean_load", "se_load", "Load"),
    ("mean_surprise_send", "se_surprise_send", "Surprise send"),
    ("mean_surprise_fail", "se_surprise_fail", "Surprise fail")
]


def plot_session_phase_metrics(data, title, summary_label):
    plot_df = data.copy()

    if plot_df.empty:
        print(f"\nNo session phase data for {summary_label}.")
        return

    phase_max = np.nanpercentile(
        np.abs(plot_df["session_phase_centered"]),
        99
    )

    if not np.isfinite(phase_max) or phase_max <= 0:
        print(f"\nNo usable session phase range for {summary_label}.")
        return

    phase_bins = np.arange(
        -phase_max,
        phase_max + phase_bin_width,
        phase_bin_width
    )

    plot_df["phase_bin"] = pd.cut(
        plot_df["session_phase_centered"],
        bins=phase_bins,
        include_lowest=True
    )

    session_phase_summary = (
        plot_df
        .groupby("phase_bin", observed=True)
        .agg(
            n=("send", "size"),
            mean_phase=("session_phase_centered", "mean"),
            mean_performance=("performance", "mean"),
            se_performance=("performance", standard_error),
            mean_load=("load", "mean"),
            se_load=("load", standard_error),
            mean_surprise_send=("surprise_send", "mean"),
            se_surprise_send=("surprise_send", standard_error),
            mean_surprise_fail=("surprise_fail", "mean"),
            se_surprise_fail=("surprise_fail", standard_error)
        )
        .reset_index()
    )

    print(f"\nDuration-normalized session phase summary ({summary_label}):")
    print(session_phase_summary.head())

    plt.figure(figsize=(12, 6))

    for mean_col, se_col, label in phase_plot_specs:
        plt.errorbar(
            session_phase_summary["mean_phase"],
            session_phase_summary[mean_col],
            yerr=session_phase_summary[se_col],
            marker="o",
            capsize=2,
            linewidth=1.5,
            label=label
        )

    plt.axvline(0, linestyle="--", linewidth=1)
    plt.axhline(0, linestyle=":", linewidth=1)

    plt.xlabel("Centered session phase: (time - session mean) / session duration")
    plt.ylabel(f"Mean value per attempt [{unit_label}]")
    plt.title(title)
    plt.legend()
    plt.tight_layout()


plot_session_phase_metrics(
    df_session_phase,
    "Performance, load, and surprise vs duration-normalized session time",
    "all attempts"
)

plot_session_phase_metrics(
    df_session_phase[df_session_phase["outside"] == 0],
    "Inside performance, load, and surprise vs duration-normalized session time",
    "inside"
)

plot_session_phase_metrics(
    df_session_phase[df_session_phase["outside"] == 1],
    "Outside performance, load, and surprise vs duration-normalized session time",
    "outside"
)

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

add_injury_markers(weekly_nll, "week", "weekly_send_nll")

plt.xlabel("Week")
plt.ylabel(f"Weekly send negative log probability [{unit_label}]")
plt.title(r"Weekly total $-\log(p_i(\mathrm{send}\mid g))$ for sends")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

# ============================================================
# Weekly fail NLL
# ============================================================

plt.figure(figsize=(11, 5))

plt.bar(
    weekly_nll["week"],
    weekly_nll["weekly_fail_nll"],
    width=5
)

add_injury_markers(weekly_nll, "week", "weekly_fail_nll")

plt.xlabel("Week")
plt.ylabel(f"Weekly fail negative log probability [{unit_label}]")
plt.title(r"Weekly total $-\log(p_i(\mathrm{fail}\mid g))$ for failures")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

# ============================================================
# Weekly total NL 
# ============================================================
plt.figure(figsize=(11, 5))

plt.bar(
    weekly_nll["week"],
    weekly_nll["weekly_fail_nll"]+weekly_nll["weekly_send_nll"],
    width=5
)

add_injury_markers(weekly_nll, "week", "weekly_total_nll")

plt.xlabel("Week")
plt.ylabel(f"Weekly total negative log probability [{unit_label}]")
plt.title(r"Weekly total $-\log(p_i(\mathrm{fail}\mid g))$")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

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

add_injury_markers(daily_perf, "day", "mean_performance")

plt.xlabel("Day")
plt.ylabel(f"Mean performance per attempt [{unit_label}]")
plt.title("Daily mean performance: send surprisal minus failure surprisal")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

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

add_injury_markers(weekly_perf, "week", "mean_performance")

plt.xlabel("Week")
plt.ylabel(f"Mean performance per attempt [{unit_label}]")
plt.title("Weekly mean performance: send surprisal minus failure surprisal")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

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
df_load_info["attempt_send_surprise"] = -log_fun(df_load_info["p_send_expected"])
df_load_info["failure_as_send_surprise"] = np.where(
    df_load_info["send"] == 0,
    df_load_info["attempt_send_surprise"],
    0.0
)

df_load_info["day"] = df_load_info["datetime"].dt.date
df_load_info["week"] = df_load_info["datetime"].dt.to_period("W-MON").dt.start_time

daily_load_info = (
    df_load_info
    .groupby("day")
    .agg(
        mean_load=("info_load", "mean"),
        total_load=("info_load", "sum"),
        mean_attempt_send_surprise=("attempt_send_surprise", "mean"),
        total_attempt_send_surprise=("attempt_send_surprise", "sum"),
        mean_failure_as_send_surprise=("failure_as_send_surprise", "mean"),
        total_failure_as_send_surprise=("failure_as_send_surprise", "sum"),
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
        mean_attempt_send_surprise=("attempt_send_surprise", "mean"),
        total_attempt_send_surprise=("attempt_send_surprise", "sum"),
        mean_failure_as_send_surprise=("failure_as_send_surprise", "mean"),
        total_failure_as_send_surprise=("failure_as_send_surprise", "sum"),
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

add_injury_markers(daily_load_info, "day", "mean_load")

plt.xlabel("Day")
plt.ylabel(f"Mean information load per attempt [{unit_label}]")
plt.title("Daily mean load: send surprise + failure surprise")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

plt.figure(figsize=(11, 5))

plt.plot(
    weekly_load_info["week"],
    weekly_load_info["mean_load"],
    marker="o",
    linewidth=1.5
)

add_injury_markers(weekly_load_info, "week", "mean_load")

plt.xlabel("Week")
plt.ylabel(f"Mean information load per attempt [{unit_label}]")
plt.title("Weekly mean load: send surprise + failure surprise")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

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

plt.figure(figsize=(11, 5))

plt.bar(
    weekly_load_info["week"],
    weekly_load_info["total_load"],
    width=5
)

add_injury_markers(weekly_load_info, "week", "total_load")

plt.xlabel("Week")
plt.ylabel(f"Total information load [{unit_label}]")
plt.title("Weekly total information load")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()

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
acwr_df["total_attempt_send_surprise"] = (
    acwr_df["total_attempt_send_surprise"].fillna(0)
)
acwr_df["total_failure_as_send_surprise"] = (
    acwr_df["total_failure_as_send_surprise"].fillna(0)
)
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
acwr_df["mean_attempt_send_surprise"] = (
    acwr_df["mean_attempt_send_surprise"].fillna(mean_load_rest_value)
)
acwr_df["mean_failure_as_send_surprise"] = (
    acwr_df["mean_failure_as_send_surprise"].fillna(mean_load_rest_value)
)

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

acwr_df["acute_total_attempt_send_surprise"] = (
    acwr_df["total_attempt_send_surprise"]
    .rolling(acute_days, min_periods=acute_days)
    .sum()
)

acwr_df["chronic_total_attempt_send_surprise"] = (
    acwr_df["total_attempt_send_surprise"]
    .rolling(chronic_days, min_periods=chronic_days)
    .sum()
)

acwr_df["acwr_total_attempt_send_surprise"] = (
    acwr_df["acute_total_attempt_send_surprise"] /
    acwr_df["chronic_total_attempt_send_surprise"]
)

acwr_df["acute_total_failure_as_send_surprise"] = (
    acwr_df["total_failure_as_send_surprise"]
    .rolling(acute_days, min_periods=acute_days)
    .sum()
)

acwr_df["chronic_total_failure_as_send_surprise"] = (
    acwr_df["total_failure_as_send_surprise"]
    .rolling(chronic_days, min_periods=chronic_days)
    .sum()
)

acwr_df["acwr_total_failure_as_send_surprise"] = (
    acwr_df["acute_total_failure_as_send_surprise"] /
    acwr_df["chronic_total_failure_as_send_surprise"]
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

acwr_df["acute_mean_attempt_send_surprise"] = (
    acwr_df["mean_attempt_send_surprise"]
    .rolling(acute_days, min_periods=acute_days)
    .mean()
)

acwr_df["chronic_mean_attempt_send_surprise"] = (
    acwr_df["mean_attempt_send_surprise"]
    .rolling(chronic_days, min_periods=chronic_days)
    .mean()
)

acwr_df["acwr_mean_attempt_send_surprise"] = (
    acwr_df["acute_mean_attempt_send_surprise"] /
    acwr_df["chronic_mean_attempt_send_surprise"]
)

acwr_df["acute_mean_failure_as_send_surprise"] = (
    acwr_df["mean_failure_as_send_surprise"]
    .rolling(acute_days, min_periods=acute_days)
    .mean()
)

acwr_df["chronic_mean_failure_as_send_surprise"] = (
    acwr_df["mean_failure_as_send_surprise"]
    .rolling(chronic_days, min_periods=chronic_days)
    .mean()
)

acwr_df["acwr_mean_failure_as_send_surprise"] = (
    acwr_df["acute_mean_failure_as_send_surprise"] /
    acwr_df["chronic_mean_failure_as_send_surprise"]
)

# Avoid divide-by-zero values
acwr_df = acwr_df.replace([np.inf, -np.inf], np.nan)

print("\nACWR dataframe:")
print(acwr_df.head(35))

# ============================================================
# Max ACWR in the 7 days before each injury date
# ============================================================

acwr_injury_lookback_days = 7


def max_value_before_injury(data, y_col):
    values = []
    value_lookup = data[["day", y_col]].dropna().copy()

    for injury_date in injury_dates:
        lookback_start = injury_date - pd.Timedelta(days=acwr_injury_lookback_days - 1)
        lookback_window = value_lookup[
            (value_lookup["day"] >= lookback_start) &
            (value_lookup["day"] <= injury_date)
        ]

        values.append({
            "injury_date": injury_date,
            "lookback_start": lookback_start,
            f"max_{y_col}_past_7_days": lookback_window[y_col].max()
        })

    return pd.DataFrame(values)


injury_acwr_mean = max_value_before_injury(acwr_df, "acwr_mean_load")
injury_acwr_total = max_value_before_injury(acwr_df, "acwr_total_load")
injury_daily_mean_load = max_value_before_injury(acwr_df, "mean_load")
injury_daily_total_load = max_value_before_injury(acwr_df, "total_load")

print("\nMax ACWR in the 7 days before injury dates:")
print(
    injury_acwr_mean
    .merge(
        injury_acwr_total,
        on=["injury_date", "lookback_start"],
        how="outer"
    )
)

print("\nMax daily load in the 7 days before injury dates:")
print(
    injury_daily_mean_load
    .merge(
        injury_daily_total_load,
        on=["injury_date", "lookback_start"],
        how="outer"
    )
)

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

    add_injury_markers(plot_df, "day", y_col, annotate=True)

    plt.xlabel("Date")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(rotation=45, ha="right")
    plt.legend()
    plt.tight_layout()

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
    injury_acwr_mean["max_acwr_mean_load_past_7_days"].dropna(),
    bins=10,
    edgecolor="black",
    alpha=0.75
)

plt.axvline(0.8, linestyle=":", linewidth=2, label="ACWR = 0.8")
plt.axvline(1.3, linestyle=":", linewidth=2, label="ACWR = 1.3")

plt.xlabel("Max ACWR in prior 7 days: mean load")
plt.ylabel("Number of injuries")
plt.title("Histogram of max mean-load ACWR before injury dates")
plt.legend()
plt.tight_layout()


plt.figure(figsize=(10, 5))

plt.hist(
    injury_acwr_total["max_acwr_total_load_past_7_days"].dropna(),
    bins=10,
    edgecolor="black",
    alpha=0.75
)

plt.axvline(0.8, linestyle=":", linewidth=2, label="ACWR = 0.8")
plt.axvline(1.3, linestyle=":", linewidth=2, label="ACWR = 1.3")

plt.xlabel("Max ACWR in prior 7 days: total load")
plt.ylabel("Number of injuries")
plt.title("Histogram of max total-load ACWR before injury dates")
plt.legend()
plt.tight_layout()

# ============================================================
# Histograms of max daily load in the 7 days before injury
# ============================================================

plt.figure(figsize=(10, 5))

plt.hist(
    injury_daily_mean_load["max_mean_load_past_7_days"].dropna(),
    bins=10,
    edgecolor="black",
    alpha=0.75
)

plt.xlabel(f"Max daily mean load in prior 7 days [{unit_label}]")
plt.ylabel("Number of injuries")
plt.title("Histogram of max daily mean load before injury dates")
plt.tight_layout()


plt.figure(figsize=(10, 5))

plt.hist(
    injury_daily_total_load["max_total_load_past_7_days"].dropna(),
    bins=10,
    edgecolor="black",
    alpha=0.75
)

plt.xlabel(f"Max daily total load in prior 7 days [{unit_label}]")
plt.ylabel("Number of injuries")
plt.title("Histogram of max daily total load before injury dates")
plt.tight_layout()

# ============================================================
# Box plots of max ACWR in the prior week at injury dates
# ============================================================

daily_acwr_inputs = df_nll.copy()
daily_acwr_inputs["day"] = daily_acwr_inputs["datetime"].dt.normalize()
daily_acwr_inputs["performance"] = (
    daily_acwr_inputs["nll_send"] - daily_acwr_inputs["nll_fail"]
)

daily_acwr_inputs = (
    daily_acwr_inputs
    .groupby("day")
    .agg(
        total_vpoints=("grade", "sum"),
        avg_vpoints=("grade", "mean"),
        performance=("performance", "mean"),
        send_surprise=("nll_send", "mean"),
        fail_surprise=("nll_fail", "mean")
    )
    .reset_index()
)

daily_session_duration = (
    df_nll
    .assign(day=df_nll["datetime"].dt.normalize())
    .groupby("day")
    .agg(
        session_start=("datetime", "min"),
        session_end=("datetime", "max")
    )
    .reset_index()
)
daily_session_duration["session_duration_min"] = (
    daily_session_duration["session_end"] -
    daily_session_duration["session_start"]
).dt.total_seconds() / 60
daily_session_duration = daily_session_duration[["day", "session_duration_min"]]

additional_acwr_df = (
    pd.DataFrame({"day": full_days})
    .merge(daily_acwr_inputs, on="day", how="left")
    .merge(daily_session_duration, on="day", how="left")
)

additional_acwr_specs = [
    ("total_vpoints", "sum", "Total V-points"),
    ("avg_vpoints", "mean", "Average V-points"),
    ("session_duration_min", "mean", "Session duration"),
    ("performance", "mean", "Performance"),
    ("send_surprise", "mean", "Send surprise"),
    ("fail_surprise", "mean", "Fail surprise")
]

for value_col, acwr_mode, _ in additional_acwr_specs:
    additional_acwr_df[value_col] = additional_acwr_df[value_col].fillna(0)

    if acwr_mode == "sum":
        acute_values = (
            additional_acwr_df[value_col]
            .rolling(acute_days, min_periods=acute_days)
            .sum()
        )
        chronic_values = (
            additional_acwr_df[value_col]
            .rolling(chronic_days, min_periods=chronic_days)
            .sum()
        )
    else:
        acute_values = (
            additional_acwr_df[value_col]
            .rolling(acute_days, min_periods=acute_days)
            .mean()
        )
        chronic_values = (
            additional_acwr_df[value_col]
            .rolling(chronic_days, min_periods=chronic_days)
            .mean()
        )

    additional_acwr_df[f"acwr_{value_col}"] = acute_values / chronic_values

additional_acwr_df = additional_acwr_df.replace([np.inf, -np.inf], np.nan)

box_acwr_specs = [
    ("acwr_total_load", "Total info load", acwr_df),
    ("acwr_mean_load", "Mean info load", acwr_df),
]

box_acwr_specs.extend(
    (f"acwr_{value_col}", label, additional_acwr_df)
    for value_col, _, label in additional_acwr_specs
)

box_rows = []

for acwr_col, label, source_df in box_acwr_specs:
    acwr_lookup = source_df[["day", acwr_col]].copy()
    acwr_lookup["day"] = pd.to_datetime(acwr_lookup["day"])
    acwr_lookup = acwr_lookup.sort_values("day")
    acwr_lookup["injury"] = (
        acwr_lookup["day"].dt.normalize().isin(injury_dates.normalize()).astype(int)
    )
    acwr_lookup["max_acwr_past_7_days"] = (
        acwr_lookup[acwr_col]
        .rolling(acwr_injury_lookback_days, min_periods=1)
        .max()
    )

    for _, row in acwr_lookup.dropna(subset=["max_acwr_past_7_days"]).iterrows():
        box_rows.append({
            "metric": label,
            "injury": row["injury"],
            "max_acwr_past_7_days": row["max_acwr_past_7_days"]
        })

acwr_box_df = pd.DataFrame(box_rows)

print("\nMax prior-week ACWR values for injury/non-injury box plots:")
print(acwr_box_df.head())


def binary_logistic_lrt_p(feature_values, injury_flags):
    x = np.asarray(feature_values, dtype=float)
    y = np.asarray(injury_flags, dtype=float)

    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]

    if len(np.unique(y)) < 2 or len(np.unique(x)) < 2:
        return np.nan

    x_mean = x.mean()
    x_sd = x.std(ddof=0)
    z = (x - x_mean) / x_sd

    def neg_log_likelihood(beta):
        logits = beta[0] + beta[1] * z
        probs = 1 / (1 + np.exp(-logits))
        probs = np.clip(probs, 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(probs) + (1 - y) * np.log(1 - probs))

    injury_rate = np.clip(y.mean(), 1e-9, 1 - 1e-9)
    null_intercept = np.log(injury_rate / (1 - injury_rate))
    null_log_likelihood = -neg_log_likelihood([null_intercept, 0])

    result = minimize(
        neg_log_likelihood,
        x0=np.array([null_intercept, 0.0]),
        method="BFGS"
    )

    full_log_likelihood = -result.fun
    likelihood_ratio = max(0, 2 * (full_log_likelihood - null_log_likelihood))
    return chi2.sf(likelihood_ratio, df=1)


fig, axes = plt.subplots(2, 4, figsize=(17, 8))
axes = axes.ravel()
rng = np.random.default_rng(42)

for ax, (metric, sub) in zip(axes, acwr_box_df.groupby("metric", sort=False)):
    non_injury_values = sub.loc[
        sub["injury"] == 0,
        "max_acwr_past_7_days"
    ]
    injury_values = sub.loc[
        sub["injury"] == 1,
        "max_acwr_past_7_days"
    ]

    mann_result = mannwhitneyu(
        injury_values,
        non_injury_values,
        alternative="two-sided"
    )
    auc = mann_result.statistic / (len(injury_values) * len(non_injury_values))
    logistic_p = binary_logistic_lrt_p(
        sub["max_acwr_past_7_days"],
        sub["injury"]
    )

    ax.boxplot(
        [non_injury_values, injury_values],
        labels=["Non-injury days", "Injury dates"],
        showfliers=False
    )
    ax.scatter(
        rng.normal(1, 0.035, len(non_injury_values)),
        non_injury_values,
        alpha=0.18,
        s=16,
        zorder=2
    )
    ax.scatter(
        rng.normal(2, 0.035, len(injury_values)),
        injury_values,
        marker="x",
        s=70,
        linewidths=2,
        color="red",
        zorder=3
    )
    ax.axhline(0.8, linestyle=":", linewidth=1)
    ax.axhline(1.3, linestyle=":", linewidth=1)
    ax.set_title(
        f"{metric}\n"
        f"MW p={mann_result.pvalue:.3g}, "
        f"logit p={logistic_p:.3g}, AUC={auc:.2f}"
    )
    ax.set_ylabel("Max ACWR in prior 7 days")

for ax in axes[acwr_box_df["metric"].nunique():]:
    ax.axis("off")

fig.suptitle("Max prior-week ACWR on injury dates vs non-injury days")
fig.tight_layout()

# ============================================================
# Statistical tests: 7-day predictors of injury
# ============================================================

injury_test_df = acwr_df[
    [
        "day",
        "acwr_mean_load",
        "acwr_total_load",
        "acwr_mean_attempt_send_surprise",
        "acwr_total_attempt_send_surprise",
        "acwr_mean_failure_as_send_surprise",
        "acwr_total_failure_as_send_surprise",
        "mean_load",
        "total_load",
        "mean_attempt_send_surprise",
        "total_attempt_send_surprise",
        "mean_failure_as_send_surprise",
        "total_failure_as_send_surprise"
    ]
].copy()
injury_test_df["day"] = pd.to_datetime(injury_test_df["day"])
injury_test_df = injury_test_df.sort_values("day")

injury_days = pd.Series(injury_dates).dt.normalize()
injury_test_df["injury"] = injury_test_df["day"].dt.normalize().isin(injury_days).astype(int)

injury_test_df["max_acwr_mean_7d"] = (
    injury_test_df["acwr_mean_load"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_acwr_total_7d"] = (
    injury_test_df["acwr_total_load"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_acwr_mean_attempt_send_surprise_7d"] = (
    injury_test_df["acwr_mean_attempt_send_surprise"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_acwr_total_attempt_send_surprise_7d"] = (
    injury_test_df["acwr_total_attempt_send_surprise"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_acwr_mean_failure_as_send_surprise_7d"] = (
    injury_test_df["acwr_mean_failure_as_send_surprise"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_acwr_total_failure_as_send_surprise_7d"] = (
    injury_test_df["acwr_total_failure_as_send_surprise"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_mean_load_7d"] = (
    injury_test_df["mean_load"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_total_load_7d"] = (
    injury_test_df["total_load"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)

performance_lookup = daily_perf[["day", "mean_performance"]].copy()
performance_lookup["day"] = pd.to_datetime(performance_lookup["day"])
injury_test_df = injury_test_df.merge(performance_lookup, on="day", how="left")
injury_test_df["mean_performance"] = injury_test_df["mean_performance"].fillna(0)
injury_test_df["max_mean_performance_7d"] = (
    injury_test_df["mean_performance"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .max()
)

daily_vgrade_attempts = df.copy()
daily_vgrade_attempts["datetime"] = pd.to_datetime(daily_vgrade_attempts[date_col])
daily_vgrade_attempts["day"] = daily_vgrade_attempts["datetime"].dt.normalize()
daily_vgrade_attempts = (
    daily_vgrade_attempts
    .dropna(subset=["day", "grade"])
    .groupby("day")
    .agg(daily_total_vgrades=("grade", "sum"))
    .reset_index()
)

injury_test_df = injury_test_df.merge(daily_vgrade_attempts, on="day", how="left")
injury_test_df["daily_total_vgrades"] = injury_test_df["daily_total_vgrades"].fillna(0)
injury_test_df["total_vgrades_7d"] = (
    injury_test_df["daily_total_vgrades"]
    .rolling(acwr_injury_lookback_days, min_periods=1)
    .sum()
)


def logistic_lrt_test(data, feature_col):
    test_data = data[[feature_col, "injury"]].dropna().copy()
    x = test_data[feature_col].to_numpy(dtype=float)
    y = test_data["injury"].to_numpy(dtype=float)

    if len(np.unique(y)) < 2 or len(np.unique(x)) < 2:
        return {
            "n": len(test_data),
            "n_injuries": int(y.sum()),
            "odds_ratio_per_sd": np.nan,
            "logistic_lrt_p": np.nan,
            "mann_whitney_p": np.nan,
            "auc": np.nan,
            "beta": np.nan,
            "intercept": np.nan,
            "x_mean": np.nan,
            "x_sd": np.nan
        }

    x_mean = x.mean()
    x_sd = x.std(ddof=0)
    z = (x - x_mean) / x_sd

    def neg_log_likelihood(beta):
        logits = beta[0] + beta[1] * z
        probs = 1 / (1 + np.exp(-logits))
        probs = np.clip(probs, 1e-9, 1 - 1e-9)
        return -np.sum(y * np.log(probs) + (1 - y) * np.log(1 - probs))

    injury_rate = np.clip(y.mean(), 1e-9, 1 - 1e-9)
    null_intercept = np.log(injury_rate / (1 - injury_rate))
    null_log_likelihood = -neg_log_likelihood([null_intercept, 0])

    result = minimize(
        neg_log_likelihood,
        x0=np.array([null_intercept, 0.0]),
        method="BFGS"
    )

    full_log_likelihood = -result.fun
    likelihood_ratio = max(0, 2 * (full_log_likelihood - null_log_likelihood))
    logistic_lrt_p = chi2.sf(likelihood_ratio, df=1)

    injury_values = x[y == 1]
    non_injury_values = x[y == 0]
    mann_result = mannwhitneyu(
        injury_values,
        non_injury_values,
        alternative="two-sided"
    )
    auc = mann_result.statistic / (len(injury_values) * len(non_injury_values))

    return {
        "n": len(test_data),
        "n_injuries": int(y.sum()),
        "odds_ratio_per_sd": np.exp(result.x[1]),
        "logistic_lrt_p": logistic_lrt_p,
        "mann_whitney_p": mann_result.pvalue,
        "auc": auc,
        "beta": result.x[1],
        "intercept": result.x[0],
        "x_mean": x_mean,
        "x_sd": x_sd
    }


injury_predictor_specs = [
    ("max_acwr_mean_7d", "Max ACWR mean load"),
    ("max_acwr_total_7d", "Max ACWR total load"),
    (
        "max_acwr_mean_attempt_send_surprise_7d",
        "Max ACWR mean attempt send surprise"
    ),
    (
        "max_acwr_total_attempt_send_surprise_7d",
        "Max ACWR total attempt send surprise"
    ),
    (
        "max_acwr_mean_failure_as_send_surprise_7d",
        "Max ACWR mean failure-as-send surprise"
    ),
    (
        "max_acwr_total_failure_as_send_surprise_7d",
        "Max ACWR total failure-as-send surprise"
    ),
    ("max_mean_load_7d", "Max mean load"),
    ("max_total_load_7d", "Max total load"),
    ("max_mean_performance_7d", "Max mean performance"),
    ("total_vgrades_7d", "Total V-grades attempted")
]

injury_test_results = []

for feature_col, label in injury_predictor_specs:
    result = logistic_lrt_test(injury_test_df, feature_col)
    result["feature"] = feature_col
    result["label"] = label
    injury_test_results.append(result)

injury_test_results = pd.DataFrame(injury_test_results)

print("\n7-day predictors of injury:")
print(
    injury_test_results[
        [
            "label",
            "n",
            "n_injuries",
            "odds_ratio_per_sd",
            "logistic_lrt_p",
            "mann_whitney_p",
            "auc"
        ]
    ]
)

fig, axes = plt.subplots(4, 3, figsize=(15, 14))
axes = axes.ravel()
rng = np.random.default_rng(42)

for ax, (feature_col, label) in zip(axes, injury_predictor_specs):
    plot_data = injury_test_df[[feature_col, "injury"]].dropna().copy()
    injury_values = plot_data.loc[plot_data["injury"] == 1, feature_col]
    non_injury_values = plot_data.loc[plot_data["injury"] == 0, feature_col]
    result = injury_test_results.loc[
        injury_test_results["feature"] == feature_col
    ].iloc[0]

    ax.boxplot(
        [non_injury_values, injury_values],
        labels=["No injury", "Injury"],
        showfliers=False
    )
    ax.scatter(
        rng.normal(1, 0.035, len(non_injury_values)),
        non_injury_values,
        alpha=0.18,
        s=16
    )
    ax.scatter(
        rng.normal(2, 0.035, len(injury_values)),
        injury_values,
        alpha=0.75,
        s=36,
        marker="x",
        color="red"
    )
    ax.set_title(
        f"{label}\n"
        f"MW p={result['mann_whitney_p']:.3g}, "
        f"logit p={result['logistic_lrt_p']:.3g}"
    )
    ax.set_ylabel("7-day predictor value")

for ax in axes[len(injury_predictor_specs):]:
    ax.axis("off")

fig.suptitle("Injury vs non-injury days: 7-day predictors")
fig.tight_layout()


fig, axes = plt.subplots(4, 3, figsize=(15, 14))
axes = axes.ravel()

for ax, (feature_col, label) in zip(axes, injury_predictor_specs):
    plot_data = injury_test_df[[feature_col, "injury"]].dropna().copy()
    result = injury_test_results.loc[
        injury_test_results["feature"] == feature_col
    ].iloc[0]

    x = plot_data[feature_col].to_numpy(dtype=float)
    y = plot_data["injury"].to_numpy(dtype=float)

    ax.scatter(
        x,
        y + rng.normal(0, 0.025, len(y)),
        alpha=0.35,
        s=18
    )

    if np.isfinite(result["beta"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        z_grid = (x_grid - result["x_mean"]) / result["x_sd"]
        probability = 1 / (
            1 + np.exp(-(result["intercept"] + result["beta"] * z_grid))
        )
        ax.plot(x_grid, probability, linewidth=2, color="red")

    ax.set_ylim(-0.08, 1.08)
    ax.set_xlabel(label)
    ax.set_ylabel("Injury probability")
    ax.set_title(
        f"OR/SD={result['odds_ratio_per_sd']:.2f}, "
        f"LRT p={result['logistic_lrt_p']:.3g}, "
        f"AUC={result['auc']:.2f}"
    )

for ax in axes[len(injury_predictor_specs):]:
    ax.axis("off")

fig.suptitle("Univariate logistic injury tests")
fig.tight_layout()

# ============================================================
# Statistical tests: weekly-smoothed predictors, max over 3 weeks
# ============================================================

weekly_average_days = 7
three_week_lookback_days = 21

injury_test_df["weekly_avg_acwr_mean"] = (
    injury_test_df["acwr_mean_load"]
    .rolling(weekly_average_days, min_periods=1)
    .mean()
)
injury_test_df["weekly_avg_acwr_total"] = (
    injury_test_df["acwr_total_load"]
    .rolling(weekly_average_days, min_periods=1)
    .mean()
)
injury_test_df["weekly_avg_mean_load"] = (
    injury_test_df["mean_load"]
    .rolling(weekly_average_days, min_periods=1)
    .mean()
)
injury_test_df["weekly_avg_total_load"] = (
    injury_test_df["total_load"]
    .rolling(weekly_average_days, min_periods=1)
    .mean()
)
injury_test_df["weekly_avg_mean_performance"] = (
    injury_test_df["mean_performance"]
    .rolling(weekly_average_days, min_periods=1)
    .mean()
)
injury_test_df["weekly_total_vgrades"] = (
    injury_test_df["daily_total_vgrades"]
    .rolling(weekly_average_days, min_periods=1)
    .sum()
)

injury_test_df["max_weekly_avg_acwr_mean_3w"] = (
    injury_test_df["weekly_avg_acwr_mean"]
    .rolling(three_week_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_weekly_avg_acwr_total_3w"] = (
    injury_test_df["weekly_avg_acwr_total"]
    .rolling(three_week_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_weekly_avg_mean_load_3w"] = (
    injury_test_df["weekly_avg_mean_load"]
    .rolling(three_week_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_weekly_avg_total_load_3w"] = (
    injury_test_df["weekly_avg_total_load"]
    .rolling(three_week_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_weekly_avg_mean_performance_3w"] = (
    injury_test_df["weekly_avg_mean_performance"]
    .rolling(three_week_lookback_days, min_periods=1)
    .max()
)
injury_test_df["max_weekly_total_vgrades_3w"] = (
    injury_test_df["weekly_total_vgrades"]
    .rolling(three_week_lookback_days, min_periods=1)
    .max()
)

weekly_predictor_specs = [
    ("max_weekly_avg_acwr_mean_3w", "Max 7-day avg ACWR mean load"),
    ("max_weekly_avg_acwr_total_3w", "Max 7-day avg ACWR total load"),
    ("max_weekly_avg_mean_load_3w", "Max 7-day avg mean load"),
    ("max_weekly_avg_total_load_3w", "Max 7-day avg total load"),
    ("max_weekly_avg_mean_performance_3w", "Max 7-day avg mean performance"),
    ("max_weekly_total_vgrades_3w", "Max 7-day total V-grades attempted")
]

weekly_test_results = []

for feature_col, label in weekly_predictor_specs:
    result = logistic_lrt_test(injury_test_df, feature_col)
    result["feature"] = feature_col
    result["label"] = label
    weekly_test_results.append(result)

weekly_test_results = pd.DataFrame(weekly_test_results)

print("\nWeekly-smoothed predictors of injury, max over prior 3 weeks:")
print(
    weekly_test_results[
        [
            "label",
            "n",
            "n_injuries",
            "odds_ratio_per_sd",
            "logistic_lrt_p",
            "mann_whitney_p",
            "auc"
        ]
    ]
)

fig, axes = plt.subplots(2, 3, figsize=(15, 8))
axes = axes.ravel()

for ax, (feature_col, label) in zip(axes, weekly_predictor_specs):
    plot_data = injury_test_df[[feature_col, "injury"]].dropna().copy()
    injury_values = plot_data.loc[plot_data["injury"] == 1, feature_col]
    non_injury_values = plot_data.loc[plot_data["injury"] == 0, feature_col]
    result = weekly_test_results.loc[
        weekly_test_results["feature"] == feature_col
    ].iloc[0]

    ax.boxplot(
        [non_injury_values, injury_values],
        labels=["No injury", "Injury"],
        showfliers=False
    )
    ax.scatter(
        rng.normal(1, 0.035, len(non_injury_values)),
        non_injury_values,
        alpha=0.18,
        s=16
    )
    ax.scatter(
        rng.normal(2, 0.035, len(injury_values)),
        injury_values,
        alpha=0.75,
        s=36,
        marker="x",
        color="red"
    )
    ax.set_title(
        f"{label}\n"
        f"MW p={result['mann_whitney_p']:.3g}, "
        f"logit p={result['logistic_lrt_p']:.3g}"
    )
    ax.set_ylabel("Predictor value")

fig.suptitle("Injury vs non-injury days: weekly predictors, 3-week max")
fig.tight_layout()


fig, axes = plt.subplots(2, 3, figsize=(15, 8))
axes = axes.ravel()

for ax, (feature_col, label) in zip(axes, weekly_predictor_specs):
    plot_data = injury_test_df[[feature_col, "injury"]].dropna().copy()
    result = weekly_test_results.loc[
        weekly_test_results["feature"] == feature_col
    ].iloc[0]

    x = plot_data[feature_col].to_numpy(dtype=float)
    y = plot_data["injury"].to_numpy(dtype=float)

    ax.scatter(
        x,
        y + rng.normal(0, 0.025, len(y)),
        alpha=0.35,
        s=18
    )

    if np.isfinite(result["beta"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        z_grid = (x_grid - result["x_mean"]) / result["x_sd"]
        probability = 1 / (
            1 + np.exp(-(result["intercept"] + result["beta"] * z_grid))
        )
        ax.plot(x_grid, probability, linewidth=2, color="red")

    ax.set_ylim(-0.08, 1.08)
    ax.set_xlabel(label)
    ax.set_ylabel("Injury probability")
    ax.set_title(
        f"OR/SD={result['odds_ratio_per_sd']:.2f}, "
        f"LRT p={result['logistic_lrt_p']:.3g}, "
        f"AUC={result['auc']:.2f}"
    )

fig.suptitle("Univariate logistic tests: weekly predictors, 3-week max")
fig.tight_layout()

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
save_all_figures()
