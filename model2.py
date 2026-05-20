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

# ============================================================
# Rolling-window logistic fits through time
# ============================================================

rolling_window_days = 60   # tunable: e.g. 14, 30, 60
min_attempts = 20          # minimum attempts inside each window
min_grades = 4             # minimum distinct grades inside each window
date_col = "time"          # your file uses "time"
min_r2 = 0.2

df["date"] = pd.to_datetime(df[date_col]).dt.date
df["date"] = pd.to_datetime(df["date"])

def r_squared(y, yhat):
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    if ss_tot == 0:
        return np.nan
    return 1 - ss_res / ss_tot

def rolling_fit_one(data, label):
    results = []

    all_days = pd.date_range(data["date"].min(), data["date"].max(), freq="D")

    for day in all_days:
        start_day = day - pd.Timedelta(days=rolling_window_days)

        window = data[
            (data["date"] > start_day) &
            (data["date"] <= day)
        ].copy()

        if len(window) < min_attempts:
            continue

        summary = (
            window.groupby("grade")
            .agg(
                n=("send", "size"),
                sends=("send", "sum"),
                p_send=("send", "mean")
            )
            .reset_index()
            .sort_values("grade")
        )

        if summary["grade"].nunique() < min_grades:
            continue

        summary["se"] = np.sqrt(summary["p_send"] * (1 - summary["p_send"]) / summary["n"])

        # Avoid zero uncertainty when p is exactly 0 or 1
        summary["se_fit"] = summary["se"].replace(0, np.nan)
        fallback_se = 1 / np.sqrt(4 * summary["n"])
        summary["se_fit"] = summary["se_fit"].fillna(fallback_se)

        x = summary["grade"].to_numpy()
        y = summary["p_send"].to_numpy()
        sigma = summary["se_fit"].to_numpy()

        try:
            popt, pcov = curve_fit(
                logistic,
                x,
                y,
                p0=[np.median(x), 1.0],
                sigma=sigma,
                absolute_sigma=True,
                bounds=([-np.inf, 1e-6], [np.inf, np.inf]),
                maxfev=10000
            )

            perr = np.sqrt(np.diag(pcov))
            yhat = logistic(x, *popt)
            r2 = r_squared(y, yhat)

            r2 = r_squared(y, yhat)

            if np.isnan(r2) or r2 < min_r2:
                continue

            results.append({
                "date": day,
                "label": label,
                "x50": popt[0],
                "x50_err": perr[0],
                "scale": popt[1],
                "scale_err": perr[1],
                "r2": r2,
                "n_attempts": len(window),
                "n_grades": summary["grade"].nunique()
            })

        except Exception:
            continue

    return pd.DataFrame(results)


# ---- run rolling fits ----
rolling_results = []

if group_by_outside:
    for outside_value, sub in df.groupby("outside"):
        label = "outside" if outside_value == 1 else "inside"
        rolling_results.append(rolling_fit_one(sub, label))
else:
    rolling_results.append(rolling_fit_one(df, "all climbs"))

rolling_results = pd.concat(rolling_results, ignore_index=True)

print("\nRolling fit results:")
print(rolling_results.head())


# ---- plot helper ----
def plot_rolling_parameter(results, param, param_err, ylabel):
    if results.empty:
        print("No rolling fits succeeded. Try increasing rolling_window_days or lowering min_attempts/min_grades.")
        return

    for label, sub in results.groupby("label"):
        plt.figure(figsize=(10, 5))

        sc = plt.scatter(
            sub["date"],
            sub[param],
            c=sub["r2"],
            s=45,
            vmin=0,
            vmax=1,
            zorder=3
        )

        # Plot error bars, but do NOT let them determine y-axis limits
        plt.errorbar(
            sub["date"],
            sub[param],
            yerr=sub[param_err],
            fmt="none",
            alpha=0.25,
            capsize=2,
            zorder=2
        )

        # Set y-limits using the fitted parameter values only
        y = sub[param].replace([np.inf, -np.inf], np.nan).dropna()

        if len(y) > 0:
            y_min = y.min()
            y_max = y.max()
            y_pad = 0.1 * (y_max - y_min)

            if y_pad == 0:
                y_pad = 0.5

            plt.ylim(y_min - y_pad, y_max + y_pad)

        plt.xlabel("Date")
        plt.ylabel(ylabel)
        plt.title(f"Rolling {rolling_window_days}-day logistic fit: {label}")

        cbar = plt.colorbar(sc)
        cbar.set_label(r"$R^2$")

        plt.tight_layout()


plot_rolling_parameter(
    rolling_results,
    param="x50",
    param_err="x50_err",
    ylabel="x50: grade with 50% send probability"
)

plot_rolling_parameter(
    rolling_results,
    param="scale",
    param_err="scale_err",
    ylabel="Logistic scale"
)



def plot_rolling_parameter_combined(results, param, param_err, ylabel):
    if results.empty:
        print("No rolling fits succeeded. Try increasing rolling_window_days or lowering min_attempts/min_grades.")
        return

    plt.figure(figsize=(10, 5))

    # Force consistent plotting order if both are present
    label_order = ["inside", "outside"]
    labels = [lab for lab in label_order if lab in results["label"].unique()]

    # Small date offsets so error bars don't perfectly overlap
    offsets = {
        "inside": -0.15,
        "outside": 0.15
    }

    all_y = []

    for label in labels:
        sub = results[results["label"] == label].copy()

        if sub.empty:
            continue

        x_dates = sub["date"] + pd.to_timedelta(offsets.get(label, 0), unit="D")

        plt.scatter(
            x_dates,
            sub[param],
            s=45,
            label=label,
            zorder=3
        )

        plt.errorbar(
            x_dates,
            sub[param],
            yerr=sub[param_err],
            fmt="none",
            alpha=0.25,
            capsize=2,
            zorder=2
        )

        all_y.append(sub[param])

    # Set y-limits using the fitted parameter values only, not error bars
    if len(all_y) > 0:
        y = pd.concat(all_y).replace([np.inf, -np.inf], np.nan).dropna()

        if len(y) > 0:
            y_min = y.min()
            y_max = y.max()
            y_pad = 0.1 * (y_max - y_min)

            if y_pad == 0:
                y_pad = 0.5

            plt.ylim(y_min - y_pad, y_max + y_pad)

    plt.xlabel("Date")
    plt.ylabel(ylabel)
    plt.title(f"Rolling {rolling_window_days}-day logistic fit")
    plt.legend(title="Climb type")
    plt.tight_layout()

plot_rolling_parameter_combined(
rolling_results,
param="x50",
param_err="x50_err",
ylabel="x50: grade with 50% send probability"
)

plot_rolling_parameter_combined(
    rolling_results,
    param="scale",
    param_err="scale_err",
    ylabel="Logistic scale"
)

# ============================================================
# Sequential surprisal using all-time logistic fits as priors
# ============================================================

from collections import defaultdict

# Tunable prior strength:
# larger = all-time logistic prior is harder to move
# smaller = recent observations update faster
prior_strength = 10

surprisal_window_days = 14  # for rolling surprise plots

# Build dictionary of all-time logistic fit params from previous `fits`
# fits contains: summary, popt, perr, label
all_time_params = {}

for summary, popt, perr, label in fits:
    all_time_params[label] = {
        "x50": popt[0],
        "scale": popt[1],
        "x50_err": perr[0],
        "scale_err": perr[1],
    }

print("\nAll-time logistic priors:")
for label, pars in all_time_params.items():
    print(
        f"{label}: x50 = {pars['x50']:.3f}, "
        f"scale = {pars['scale']:.3f}"
    )


def label_from_outside(outside_value):
    return "outside" if outside_value == 1 else "inside"


def safe_prob(p, eps=1e-6):
    return np.clip(p, eps, 1 - eps)


# Sort attempts in time order
df_seq = df.copy()
df_seq["date"] = pd.to_datetime(df_seq[date_col])
df_seq = df_seq.sort_values("date").reset_index(drop=True)

# Only keep rows whose inside/outside label has a fitted prior
df_seq["label"] = df_seq["outside"].apply(label_from_outside)
df_seq = df_seq[df_seq["label"].isin(all_time_params.keys())].copy()

# Beta posterior state for each inside/outside x grade pair
# Each key gets initialized using logistic prior pseudo-counts
posterior_state = {}

rows = []

for idx, row in df_seq.iterrows():
    grade = row["grade"]
    y = row["send"]
    label = row["label"]
    date = row["date"]

    pars = all_time_params[label]

    # Prior predictive probability from all-time logistic fit
    p_logistic = logistic(grade, pars["x50"], pars["scale"])
    p_logistic = safe_prob(p_logistic)

    # Surprisal under static all-time prior
    if y == 1:
        surprisal_prior = -np.log2(p_logistic)
    else:
        surprisal_prior = -np.log2(1 - p_logistic)

    # Initialize grade/type-specific Beta posterior if needed
    key = (label, grade)

    if key not in posterior_state:
        alpha0 = prior_strength * p_logistic
        beta0 = prior_strength * (1 - p_logistic)
        posterior_state[key] = [alpha0, beta0]

    alpha, beta = posterior_state[key]

    # Posterior predictive before seeing current attempt
    p_posterior = alpha / (alpha + beta)
    p_posterior = safe_prob(p_posterior)

    if y == 1:
        surprisal_posterior = -np.log2(p_posterior)
    else:
        surprisal_posterior = -np.log2(1 - p_posterior)

    rows.append({
        "date": date,
        "grade": grade,
        "send": y,
        "label": label,
        "p_logistic_prior": p_logistic,
        "p_posterior_predictive": p_posterior,
        "surprisal_prior": surprisal_prior,
        "surprisal_posterior": surprisal_posterior,
        "alpha_before": alpha,
        "beta_before": beta,
    })

    # Update posterior after observing current attempt
    posterior_state[key][0] += y
    posterior_state[key][1] += 1 - y


surprise_df = pd.DataFrame(rows)

print("\nSurprisal dataframe:")
print(surprise_df.head())

# ============================================================
# Plot surprisal over time
# ============================================================

plt.figure(figsize=(11, 5))

for label, sub in surprise_df.groupby("label"):
    plt.scatter(
        sub["date"],
        sub["surprisal_prior"],
        s=35,
        alpha=0.65,
        label=label
    )

plt.xlabel("Date")
plt.ylabel("Surprisal under all-time logistic prior [bits]")
plt.title("Attempt-level surprise through time")
plt.legend(title="Climb type")
plt.tight_layout()

# ============================================================
# Rolling average surprise
# ============================================================

surprise_daily = (
    surprise_df
    .set_index("date")
    .groupby("label")
    .rolling(f"{surprisal_window_days}D")["surprisal_prior"]
    .mean()
    .reset_index()
    .rename(columns={"surprisal_prior": "rolling_surprisal_prior"})
)

plt.figure(figsize=(11, 5))

for label, sub in surprise_daily.groupby("label"):
    plt.plot(
        sub["date"],
        sub["rolling_surprisal_prior"],
        marker="o",
        markersize=3,
        label=label
    )

plt.xlabel("Date")
plt.ylabel(f"{surprisal_window_days}-day rolling mean surprise [bits]")
plt.title("Rolling surprise relative to all-time logistic prior")
plt.legend(title="Climb type")
plt.tight_layout()

# ============================================================
# Compare static-prior surprise vs updated-posterior surprise
# ============================================================

surprise_daily_compare = (
    surprise_df
    .set_index("date")
    .groupby("label")
    .rolling(f"{surprisal_window_days}D")[["surprisal_prior", "surprisal_posterior"]]
    .mean()
    .reset_index()
)

for label, sub in surprise_daily_compare.groupby("label"):
    plt.figure(figsize=(11, 5))

    plt.plot(
        sub["date"],
        sub["surprisal_prior"],
        marker="o",
        markersize=3,
        label="static logistic prior"
    )

    plt.plot(
        sub["date"],
        sub["surprisal_posterior"],
        marker="o",
        markersize=3,
        label="sequential posterior"
    )

    plt.xlabel("Date")
    plt.ylabel(f"{surprisal_window_days}-day rolling mean surprise [bits]")
    plt.title(f"Static vs updated surprise: {label}")
    plt.legend()
    plt.tight_layout()

    # ============================================================
# Information gain from sequential updating
# ============================================================

surprise_df["info_gain_bits"] = (
    surprise_df["surprisal_prior"] -
    surprise_df["surprisal_posterior"]
)

info_daily = (
    surprise_df
    .set_index("date")
    .groupby("label")
    .rolling(f"{surprisal_window_days}D")["info_gain_bits"]
    .mean()
    .reset_index()
)

plt.figure(figsize=(11, 5))

for label, sub in info_daily.groupby("label"):
    plt.plot(
        sub["date"],
        sub["info_gain_bits"],
        marker="o",
        markersize=3,
        label=label
    )

plt.axhline(0, linestyle="--", linewidth=1)

plt.xlabel("Date")
plt.ylabel(f"{surprisal_window_days}-day rolling mean information gain [bits]")
plt.title("How much recent history improves prediction")
plt.legend(title="Climb type")
plt.tight_layout()

# ============================================================
# Within-day attempt timing histogram
# ============================================================

time_bin_minutes = 30   # tunable: e.g. 10, 15, 30, 60
date_col = "time"      # same as before

df_daytime = df.copy()
df_daytime["datetime"] = pd.to_datetime(df_daytime[date_col])

# minutes since midnight
df_daytime["minute_of_day"] = (
    df_daytime["datetime"].dt.hour * 60 +
    df_daytime["datetime"].dt.minute +
    df_daytime["datetime"].dt.second / 60
)

# optional labels
df_daytime["label"] = df_daytime["outside"].apply(
    lambda x: "outside" if x == 1 else "inside"
)

bins = np.arange(0, 24 * 60 + time_bin_minutes, time_bin_minutes)
bin_centers = (bins[:-1] + bins[1:]) / 2

plt.figure(figsize=(11, 5))

for label, sub in df_daytime.groupby("label"):
    counts, _ = np.histogram(sub["minute_of_day"], bins=bins)

    plt.plot(
        bin_centers / 60,
        counts,
        marker="o",
        label=label
    )

plt.xlabel("Time of day")
plt.ylabel("Number of attempts")
plt.title(f"Attempts by time of day, binned every {time_bin_minutes} min")
plt.xticks(np.arange(0, 25, 2))
plt.xlim(0, 24)
plt.legend(title="Climb type")
plt.tight_layout()

# ============================================================
# Align attempts within daily sessions
# Session start = first climb of the day
# Session end   = last climb of the day
# Duration      = end - start
# Attempts are centered by subtracting the mean attempt time
# ============================================================

session_bin_minutes = 10   # tunable
date_col = "time"

df_session = df.copy()
df_session["datetime"] = pd.to_datetime(df_session[date_col])
df_session["session_date"] = df_session["datetime"].dt.date

df_session["label"] = df_session["outside"].apply(
    lambda x: "outside" if x == 1 else "inside"
)

# Session-level summaries
session_summary = (
    df_session
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

# Attach session info back to every attempt
df_session = df_session.merge(session_summary, on="session_date", how="left")

# Time relative to that session's mean attempt time
df_session["minutes_from_session_mean"] = (
    df_session["datetime"] - df_session["mean_time"]
).dt.total_seconds() / 60

print("\nSession summary:")
print(session_summary.head())

# ============================================================
# Histogram of attempts aligned by session mean time
# ============================================================

max_abs_time = np.nanpercentile(
    np.abs(df_session["minutes_from_session_mean"]),
    99
)

bins = np.arange(
    -max_abs_time,
    max_abs_time + session_bin_minutes,
    session_bin_minutes
)

plt.figure(figsize=(11, 5))

for label, sub in df_session.groupby("label"):
    plt.hist(
        sub["minutes_from_session_mean"],
        bins=bins,
        alpha=0.6,
        label=label
    )

plt.axvline(0, linestyle="--", linewidth=1)

plt.xlabel("Minutes from session mean attempt time")
plt.ylabel("Number of attempts")
plt.title(f"Attempts aligned by daily session mean, binned every {session_bin_minutes} min")
plt.legend(title="Climb type")
plt.tight_layout()

# ============================================================
# Duration-normalized session time
# ============================================================

# Avoid divide-by-zero for one-attempt sessions
df_session["session_phase_centered"] = (
    df_session["minutes_from_session_mean"] /
    df_session["session_duration_min"]
)

df_session_norm = df_session.replace([np.inf, -np.inf], np.nan).dropna(
    subset=["session_phase_centered"]
)

phase_bin_width = 0.05

phase_max = np.nanpercentile(
    np.abs(df_session_norm["session_phase_centered"]),
    99
)

phase_bins = np.arange(
    -phase_max,
    phase_max + phase_bin_width,
    phase_bin_width
)

plt.figure(figsize=(11, 5))

for label, sub in df_session_norm.groupby("label"):
    plt.hist(
        sub["session_phase_centered"],
        bins=phase_bins,
        alpha=0.6,
        label=label
    )

plt.axvline(0, linestyle="--", linewidth=1)

plt.xlabel("Centered session phase: (time - session mean) / session duration")
plt.ylabel("Number of attempts")
plt.title("Attempts aligned and normalized by daily session duration")
plt.legend(title="Climb type")
plt.tight_layout()


# ============================================================
# Surprisal and information gain vs duration-normalized session time
# ============================================================

prior_strength = 10      # higher = logistic prior is harder to update
phase_bin_width = 0.05   # tunable bin width for session phase plots

df_phase = df_session_norm.copy()

# Make sure these exist
df_phase["datetime"] = pd.to_datetime(df_phase[date_col])
df_phase = df_phase.sort_values("datetime").reset_index(drop=True)

df_phase["label"] = df_phase["outside"].apply(
    lambda x: "outside" if x == 1 else "inside"
)

df_phase = df_phase[df_phase["label"].isin(all_time_params.keys())].copy()


def safe_prob(p, eps=1e-6):
    return np.clip(p, eps, 1 - eps)


# Sequential posterior state, one Beta posterior for each inside/outside x grade pair
posterior_state = {}

rows = []

for idx, row in df_phase.iterrows():
    grade = row["grade"]
    y = row["send"]
    label = row["label"]
    phase = row["session_phase_centered"]

    pars = all_time_params[label]

    # Static all-time logistic prior
    p_logistic = logistic(grade, pars["x50"], pars["scale"])
    p_logistic = safe_prob(p_logistic)

    if y == 1:
        surprisal_prior = -np.log2(p_logistic)
    else:
        surprisal_prior = -np.log2(1 - p_logistic)

    # Sequential Beta posterior, updated in chronological order
    key = (label, grade)

    if key not in posterior_state:
        alpha0 = prior_strength * p_logistic
        beta0 = prior_strength * (1 - p_logistic)
        posterior_state[key] = [alpha0, beta0]

    alpha, beta = posterior_state[key]

    # Predict current attempt before seeing its outcome
    p_posterior = alpha / (alpha + beta)
    p_posterior = safe_prob(p_posterior)

    if y == 1:
        surprisal_posterior = -np.log2(p_posterior)
    else:
        surprisal_posterior = -np.log2(1 - p_posterior)

    info_gain_bits = surprisal_prior - surprisal_posterior

    rows.append({
        "datetime": row["datetime"],
        "session_date": row["session_date"],
        "session_phase_centered": phase,
        "grade": grade,
        "send": y,
        "label": label,
        "p_logistic_prior": p_logistic,
        "p_posterior_predictive": p_posterior,
        "surprisal_prior": surprisal_prior,
        "surprisal_posterior": surprisal_posterior,
        "info_gain_bits": info_gain_bits,
    })

    # Update after observing current attempt
    posterior_state[key][0] += y
    posterior_state[key][1] += 1 - y


phase_surprise_df = pd.DataFrame(rows)

print("\nPhase surprise dataframe:")
print(phase_surprise_df.head())
# ============================================================
# Bin by duration-normalized session phase
# ============================================================

phase_max = np.nanpercentile(
    np.abs(phase_surprise_df["session_phase_centered"]),
    99
)

phase_bins = np.arange(
    -phase_max,
    phase_max + phase_bin_width,
    phase_bin_width
)

phase_surprise_df["phase_bin"] = pd.cut(
    phase_surprise_df["session_phase_centered"],
    bins=phase_bins,
    include_lowest=True
)

phase_summary = (
    phase_surprise_df
    .groupby(["label", "phase_bin"], observed=True)
    .agg(
        n=("send", "size"),
        mean_phase=("session_phase_centered", "mean"),
        mean_surprisal_prior=("surprisal_prior", "mean"),
        se_surprisal_prior=("surprisal_prior", lambda x: x.std(ddof=1) / np.sqrt(len(x))),
        mean_surprisal_posterior=("surprisal_posterior", "mean"),
        se_surprisal_posterior=("surprisal_posterior", lambda x: x.std(ddof=1) / np.sqrt(len(x))),
        mean_info_gain=("info_gain_bits", "mean"),
        se_info_gain=("info_gain_bits", lambda x: x.std(ddof=1) / np.sqrt(len(x))),
    )
    .reset_index()
)

print("\nPhase-binned summary:")
print(phase_summary.head())
# ============================================================
# Plot surprise vs duration-normalized session time
# ============================================================

plt.figure(figsize=(11, 5))

for label, sub in phase_summary.groupby("label"):
    plt.errorbar(
        sub["mean_phase"],
        sub["mean_surprisal_prior"],
        yerr=sub["se_surprisal_prior"],
        marker="o",
        capsize=2,
        label=f"{label}: static logistic prior"
    )

plt.axvline(0, linestyle="--", linewidth=1)

plt.xlabel("Centered session phase: (time - session mean) / session duration")
plt.ylabel("Mean surprisal [bits]")
plt.title("Surprise vs duration-normalized session time")
plt.legend()
plt.tight_layout()

# ============================================================
# Plot posterior surprise vs duration-normalized session time
# ============================================================

plt.figure(figsize=(11, 5))

for label, sub in phase_summary.groupby("label"):
    plt.errorbar(
        sub["mean_phase"],
        sub["mean_surprisal_posterior"],
        yerr=sub["se_surprisal_posterior"],
        marker="o",
        capsize=2,
        label=f"{label}: sequential posterior"
    )

plt.axvline(0, linestyle="--", linewidth=1)

plt.xlabel("Centered session phase: (time - session mean) / session duration")
plt.ylabel("Mean posterior surprisal [bits]")
plt.title("Sequentially updated surprise vs duration-normalized session time")
plt.legend()
plt.tight_layout()

# ============================================================
# Plot information gain vs duration-normalized session time
# ============================================================

plt.figure(figsize=(11, 5))

for label, sub in phase_summary.groupby("label"):
    plt.errorbar(
        sub["mean_phase"],
        sub["mean_info_gain"],
        yerr=sub["se_info_gain"],
        marker="o",
        capsize=2,
        label=label
    )

plt.axhline(0, linestyle="--", linewidth=1)
plt.axvline(0, linestyle="--", linewidth=1)

plt.xlabel("Centered session phase: (time - session mean) / session duration")
plt.ylabel("Mean information gain [bits]")
plt.title("Information gain from sequential updating vs session phase")
plt.legend(title="Climb type")
plt.tight_layout()

# ============================================================
# Raw scatter: information gain vs session phase
# ============================================================

plt.figure(figsize=(11, 5))

for label, sub in phase_surprise_df.groupby("label"):
    plt.scatter(
        sub["session_phase_centered"],
        sub["info_gain_bits"],
        alpha=0.35,
        s=25,
        label=label
    )

plt.axhline(0, linestyle="--", linewidth=1)
plt.axvline(0, linestyle="--", linewidth=1)

plt.xlabel("Centered session phase: (time - session mean) / session duration")
plt.ylabel("Information gain [bits]")
plt.title("Raw information gain vs duration-normalized session time")
plt.legend(title="Climb type")
plt.tight_layout()

# ============================================================
# Histogram of intervals between consecutive attempts
# Uses all data, ignores inside/outside
# ============================================================

date_col = "time"

df_intervals = df.copy()
df_intervals["datetime"] = pd.to_datetime(df_intervals[date_col])
df_intervals = df_intervals.dropna(subset=["datetime"]).sort_values("datetime")

df_intervals["dt_minutes"] = (
    df_intervals["datetime"].diff().dt.total_seconds() / 60
)

# Drop the first row, which has no previous attempt
dt = df_intervals["dt_minutes"].dropna()

plt.figure(figsize=(11, 5))

plt.hist(dt, bins=100)

plt.xlabel("Minutes between consecutive attempts")
plt.ylabel("Count")
plt.title("Intervals between consecutive attempts")
plt.tight_layout()

# ============================================================
# Log-scale histogram of intervals between attempts
# ============================================================

dt_positive = dt[dt > 0]

plt.figure(figsize=(11, 5))

plt.hist(dt_positive, bins=np.logspace(np.log10(dt_positive.min()), np.log10(dt_positive.max()), 100))

plt.xscale("log")

plt.xlabel("Minutes between consecutive attempts, log scale")
plt.ylabel("Count")
plt.title("Intervals between consecutive attempts, log x-axis")

# Useful reference lines
plt.axvline(10, linestyle="--", linewidth=1, label="10 min")
plt.axvline(60, linestyle="--", linewidth=1, label="1 hour")
plt.axvline(24 * 60, linestyle="--", linewidth=1, label="1 day")
plt.axvline(7 * 24 * 60, linestyle="--", linewidth=1, label="1 week")

plt.legend()
plt.tight_layout()

# ============================================================
# Log-scale interval histogram split by inside/outside
# Intervals are computed separately within each group
# ============================================================

date_col = "time"

df_intervals_split = df.copy()
df_intervals_split["datetime"] = pd.to_datetime(df_intervals_split[date_col])
df_intervals_split = df_intervals_split.dropna(subset=["datetime"]).copy()

df_intervals_split["label"] = df_intervals_split["outside"].apply(
    lambda x: "outside" if x == 1 else "inside"
)

interval_dfs = []

for label, sub in df_intervals_split.groupby("label"):
    sub = sub.sort_values("datetime").copy()

    sub["dt_minutes"] = (
        sub["datetime"].diff().dt.total_seconds() / 60
    )

    interval_dfs.append(sub)

df_intervals_split = pd.concat(interval_dfs, ignore_index=True)

dt_positive_all = df_intervals_split.loc[
    df_intervals_split["dt_minutes"] > 0,
    "dt_minutes"
]

bins = np.logspace(
    np.log10(dt_positive_all.min()),
    np.log10(dt_positive_all.max()),
    100
)

plt.figure(figsize=(11, 5))

for label, sub in df_intervals_split.groupby("label"):
    dt_positive = sub.loc[sub["dt_minutes"] > 0, "dt_minutes"]

    plt.hist(
        dt_positive,
        bins=bins,
        alpha=0.6,
        label=label
    )

plt.xscale("log")

plt.xlabel("Minutes between consecutive attempts, log scale")
plt.ylabel("Count")
plt.title("Intervals between consecutive attempts, split by inside/outside")

# Useful reference lines
plt.axvline(10, linestyle="--", linewidth=1, label="10 min")
plt.axvline(60, linestyle="--", linewidth=1, label="1 hour")
plt.axvline(24 * 60, linestyle="--", linewidth=1, label="1 day")
plt.axvline(7 * 24 * 60, linestyle="--", linewidth=1, label="1 week")

plt.legend()
plt.tight_layout()

# ============================================================
# Log-scale interval histograms by inside/outside and event ordering
# Categories:
#   fail-send, send-fail, fail-fail, send-send
# ============================================================

date_col = "time"

df_order_intervals = df.copy()
df_order_intervals["datetime"] = pd.to_datetime(df_order_intervals[date_col])
df_order_intervals = df_order_intervals.dropna(subset=["datetime"]).copy()

# Keep only binary attempts
df_order_intervals = df_order_intervals[df_order_intervals["send"].isin([0, 1])].copy()

df_order_intervals["label"] = df_order_intervals["outside"].apply(
    lambda x: "outside" if x == 1 else "inside"
)

interval_dfs = []

for label, sub in df_order_intervals.groupby("label"):
    sub = sub.sort_values("datetime").copy()

    sub["dt_minutes"] = sub["datetime"].diff().dt.total_seconds() / 60

    # previous and current outcomes
    sub["prev_send"] = sub["send"].shift(1)
    sub["curr_send"] = sub["send"]

    def ordering_name(row):
        if pd.isna(row["prev_send"]):
            return np.nan

        prev = "send" if row["prev_send"] == 1 else "fail"
        curr = "send" if row["curr_send"] == 1 else "fail"

        return f"{prev}-{curr}"

    sub["ordering"] = sub.apply(ordering_name, axis=1)

    interval_dfs.append(sub)

df_order_intervals = pd.concat(interval_dfs, ignore_index=True)

# Keep positive intervals only
df_order_intervals = df_order_intervals[
    df_order_intervals["dt_minutes"] > 0
].copy()

# Shared bins across both inside/outside and all ordering classes
bins = np.logspace(
    np.log10(df_order_intervals["dt_minutes"].min()),
    np.log10(df_order_intervals["dt_minutes"].max()),
    100
)

ordering_order = [
    "fail-send",
    "send-fail",
    "fail-fail",
    "send-send"
]

# ============================================================
# Plot: separate axes for inside and outside
# ============================================================

fig, axes = plt.subplots(
    nrows=2,
    ncols=1,
    figsize=(11, 8),
    sharex=True,
    sharey=True
)

for ax, label in zip(axes, ["inside", "outside"]):
    sub_label = df_order_intervals[df_order_intervals["label"] == label]

    for ordering in ordering_order:
        sub = sub_label[sub_label["ordering"] == ordering]

        if sub.empty:
            continue

        ax.hist(
            sub["dt_minutes"],
            bins=bins,
            alpha=0.55,
            label=ordering
        )

    ax.set_xscale("log")
    ax.set_ylabel("Count")
    ax.set_title(f"{label}: intervals between consecutive attempts")

    # Useful reference lines
    ax.axvline(10, linestyle="--", linewidth=1)
    ax.axvline(60, linestyle="--", linewidth=1)
    ax.axvline(24 * 60, linestyle="--", linewidth=1)
    ax.axvline(7 * 24 * 60, linestyle="--", linewidth=1)

    ax.legend(title="Event ordering")

axes[-1].set_xlabel("Minutes between consecutive attempts, log scale")

plt.tight_layout()

# ============================================================
# Are sends more likely after longer wait intervals?
# Keeps intervals <= 400 min
# Plots P(current send | wait interval)
# Tests current send ~ log(wait interval)
# ============================================================

import statsmodels.api as sm

date_col = "time"
max_interval_minutes = 400
n_log_bins = 18

df_wait = df.copy()
df_wait["datetime"] = pd.to_datetime(df_wait[date_col])
df_wait = df_wait.dropna(subset=["datetime"]).sort_values("datetime").copy()

# Make sure send is binary
if "send" not in df_wait.columns:
    df_wait = df_wait[df_wait["send/reps"].isin([0, 1])].copy()
    df_wait["send"] = df_wait["send/reps"].astype(int)
else:
    df_wait = df_wait[df_wait["send"].isin([0, 1])].copy()
    df_wait["send"] = df_wait["send"].astype(int)

# Consecutive-attempt intervals across all data
df_wait["dt_minutes"] = df_wait["datetime"].diff().dt.total_seconds() / 60
df_wait["prev_send"] = df_wait["send"].shift(1)
df_wait["curr_send"] = df_wait["send"]

# Keep usable intervals
df_wait = df_wait[
    (df_wait["dt_minutes"] > 0) &
    (df_wait["dt_minutes"] <= max_interval_minutes) &
    (~df_wait["prev_send"].isna())
].copy()

df_wait["prev_send"] = df_wait["prev_send"].astype(int)

def ordering_name(row):
    prev = "send" if row["prev_send"] == 1 else "fail"
    curr = "send" if row["curr_send"] == 1 else "fail"
    return f"{prev}-{curr}"

df_wait["ordering"] = df_wait.apply(ordering_name, axis=1)

# ============================================================
# Bin intervals on a log scale
# ============================================================

bins = np.logspace(
    np.log10(df_wait["dt_minutes"].min()),
    np.log10(df_wait["dt_minutes"].max()),
    n_log_bins + 1
)

df_wait["dt_bin"] = pd.cut(
    df_wait["dt_minutes"],
    bins=bins,
    include_lowest=True
)

wait_summary = (
    df_wait
    .groupby("dt_bin", observed=True)
    .agg(
        n_total=("curr_send", "size"),
        n_sends=("curr_send", "sum"),
        p_send=("curr_send", "mean"),
        mean_dt=("dt_minutes", "mean")
    )
    .reset_index()
)

wait_summary["se_p_send"] = np.sqrt(
    wait_summary["p_send"] *
    (1 - wait_summary["p_send"]) /
    wait_summary["n_total"]
)

# For plotting on log axis
wait_summary["bin_center"] = wait_summary["dt_bin"].apply(
    lambda x: np.sqrt(x.left * x.right)
).astype(float)

print("\nWait interval summary:")
print(wait_summary)

# ============================================================
# Plot normalized send probability vs wait interval
# ============================================================

plt.figure(figsize=(11, 5))

plt.errorbar(
    wait_summary["bin_center"],
    wait_summary["p_send"],
    yerr=wait_summary["se_p_send"],
    marker="o",
    capsize=3,
    linewidth=1.5,
    label="P(current attempt is send)"
)

plt.xscale("log")

plt.xlabel("Minutes since previous attempt, log scale")
plt.ylabel("P(send)")
plt.title(f"Send probability vs wait interval, intervals ≤ {max_interval_minutes} min")
plt.ylim(-0.05, 1.05)

plt.axvline(10, linestyle="--", linewidth=1, label="10 min")
plt.axvline(60, linestyle="--", linewidth=1, label="1 hour")

plt.legend()
plt.tight_layout()

# ============================================================
# Normalized fail-send probability vs wait interval
# Numerator: fail-send only
# Denominator: all orderings
# ============================================================

fail_send_summary = (
    df_wait
    .groupby("dt_bin", observed=True)
    .agg(
        n_total=("ordering", "size"),
        n_fail_send=("ordering", lambda x: np.sum(x == "fail-send")),
        mean_dt=("dt_minutes", "mean")
    )
    .reset_index()
)

fail_send_summary["p_fail_send"] = (
    fail_send_summary["n_fail_send"] /
    fail_send_summary["n_total"]
)

fail_send_summary["se_fail_send"] = np.sqrt(
    fail_send_summary["p_fail_send"] *
    (1 - fail_send_summary["p_fail_send"]) /
    fail_send_summary["n_total"]
)

fail_send_summary["bin_center"] = fail_send_summary["dt_bin"].apply(
    lambda x: np.sqrt(x.left * x.right)
).astype(float)

print("\nFail-send summary:")
print(fail_send_summary)

plt.figure(figsize=(11, 5))

plt.errorbar(
    fail_send_summary["bin_center"],
    fail_send_summary["p_fail_send"],
    yerr=fail_send_summary["se_fail_send"],
    marker="o",
    capsize=3,
    linewidth=1.5,
    label="P(fail-send ordering)"
)

plt.xscale("log")

plt.xlabel("Minutes since previous attempt, log scale")
plt.ylabel("P(fail-send)")
plt.title(f"Normalized fail-send probability vs wait interval, intervals ≤ {max_interval_minutes} min")

plt.axvline(10, linestyle="--", linewidth=1, label="10 min")
plt.axvline(60, linestyle="--", linewidth=1, label="1 hour")

plt.ylim(-0.05, max(0.2, fail_send_summary["p_fail_send"].max() * 1.2))

plt.legend()
plt.tight_layout()

# ============================================================
# After a fail, are sends more likely after longer wait intervals?
# Keeps only intervals where previous attempt was a fail
# Keeps intervals <= 400 min
# Tests current send ~ log(wait interval)
# ============================================================

import statsmodels.api as sm

max_interval_minutes = 400
n_log_bins = 18

# Start from df_wait if you already made it
# Otherwise, rebuild it safely
df_after_fail = df.copy()
df_after_fail["datetime"] = pd.to_datetime(df_after_fail[date_col])
df_after_fail = df_after_fail.dropna(subset=["datetime"]).sort_values("datetime").copy()

# Make sure send is binary
if "send" not in df_after_fail.columns:
    df_after_fail = df_after_fail[df_after_fail["send/reps"].isin([0, 1])].copy()
    df_after_fail["send"] = df_after_fail["send/reps"].astype(int)
else:
    df_after_fail = df_after_fail[df_after_fail["send"].isin([0, 1])].copy()
    df_after_fail["send"] = df_after_fail["send"].astype(int)

df_after_fail["dt_minutes"] = (
    df_after_fail["datetime"].diff().dt.total_seconds() / 60
)

df_after_fail["prev_send"] = df_after_fail["send"].shift(1)
df_after_fail["curr_send"] = df_after_fail["send"]

df_after_fail = df_after_fail[
    (df_after_fail["dt_minutes"] > 0) &
    (df_after_fail["dt_minutes"] <= max_interval_minutes) &
    (~df_after_fail["prev_send"].isna())
].copy()

df_after_fail["prev_send"] = df_after_fail["prev_send"].astype(int)
df_after_fail["curr_send"] = df_after_fail["curr_send"].astype(int)

# Keep only attempts immediately following a failure
df_after_fail = df_after_fail[df_after_fail["prev_send"] == 0].copy()

df_after_fail["ordering"] = np.where(
    df_after_fail["curr_send"] == 1,
    "fail-send",
    "fail-fail"
)

print("\nAfter-fail interval data:")
print(df_after_fail[["datetime", "dt_minutes", "prev_send", "curr_send", "ordering"]].head())
print(f"\nNumber of after-fail intervals: {len(df_after_fail)}")
print(df_after_fail["ordering"].value_counts())

# ============================================================
# Bin on log interval axis
# ============================================================

bins = np.logspace(
    np.log10(df_after_fail["dt_minutes"].min()),
    np.log10(df_after_fail["dt_minutes"].max()),
    n_log_bins + 1
)

df_after_fail["dt_bin"] = pd.cut(
    df_after_fail["dt_minutes"],
    bins=bins,
    include_lowest=True
)

after_fail_summary = (
    df_after_fail
    .groupby("dt_bin", observed=True)
    .agg(
        n_total=("curr_send", "size"),
        n_sends=("curr_send", "sum"),
        p_send_after_fail=("curr_send", "mean"),
        mean_dt=("dt_minutes", "mean")
    )
    .reset_index()
)

after_fail_summary["se_p_send_after_fail"] = np.sqrt(
    after_fail_summary["p_send_after_fail"] *
    (1 - after_fail_summary["p_send_after_fail"]) /
    after_fail_summary["n_total"]
)

after_fail_summary["bin_center"] = after_fail_summary["dt_bin"].apply(
    lambda x: np.sqrt(x.left * x.right)
).astype(float)

print("\nAfter-fail summary:")
print(after_fail_summary)

# ============================================================
# Plot P(send | previous fail, wait interval)
# ============================================================

plt.figure(figsize=(11, 5))

plt.errorbar(
    after_fail_summary["bin_center"],
    after_fail_summary["p_send_after_fail"],
    yerr=after_fail_summary["se_p_send_after_fail"],
    marker="o",
    capsize=3,
    linewidth=1.5,
    label="P(send | previous fail)"
)

plt.xscale("log")

plt.xlabel("Minutes since failed attempt, log scale")
plt.ylabel("P(send | previous fail)")
plt.title(f"After a fail, does longer rest predict sends? intervals ≤ {max_interval_minutes} min")

plt.axvline(10, linestyle="--", linewidth=1, label="10 min")
plt.axvline(60, linestyle="--", linewidth=1, label="1 hour")

plt.ylim(-0.05, 1.05)

plt.legend()
plt.tight_layout()

# ============================================================
# Grade-split wait interval plots
# 1. P(send | previous fail, dt)
# 2. P(current send | dt)
# ============================================================

date_col = "time"
max_interval_minutes = 400
n_log_bins = 12          # fewer bins helps when splitting by grade
min_bin_attempts = 3     # hide noisy bins with too little data

df_grade_wait = df.copy()
df_grade_wait["datetime"] = pd.to_datetime(df_grade_wait[date_col])
df_grade_wait = df_grade_wait.dropna(subset=["datetime", "grade"]).sort_values("datetime").copy()

# Make sure send is binary
if "send" not in df_grade_wait.columns:
    df_grade_wait = df_grade_wait[df_grade_wait["send/reps"].isin([0, 1])].copy()
    df_grade_wait["send"] = df_grade_wait["send/reps"].astype(int)
else:
    df_grade_wait = df_grade_wait[df_grade_wait["send"].isin([0, 1])].copy()
    df_grade_wait["send"] = df_grade_wait["send"].astype(int)

df_grade_wait["grade"] = pd.to_numeric(df_grade_wait["grade"], errors="coerce")
df_grade_wait = df_grade_wait.dropna(subset=["grade"])

# Consecutive intervals across all data
df_grade_wait["dt_minutes"] = (
    df_grade_wait["datetime"].diff().dt.total_seconds() / 60
)

df_grade_wait["prev_send"] = df_grade_wait["send"].shift(1)
df_grade_wait["curr_send"] = df_grade_wait["send"]

df_grade_wait = df_grade_wait[
    (df_grade_wait["dt_minutes"] > 0) &
    (df_grade_wait["dt_minutes"] <= max_interval_minutes) &
    (~df_grade_wait["prev_send"].isna())
].copy()

df_grade_wait["prev_send"] = df_grade_wait["prev_send"].astype(int)
df_grade_wait["curr_send"] = df_grade_wait["curr_send"].astype(int)

# Shared log bins
bins = np.logspace(
    np.log10(df_grade_wait["dt_minutes"].min()),
    np.log10(df_grade_wait["dt_minutes"].max()),
    n_log_bins + 1
)

df_grade_wait["dt_bin"] = pd.cut(
    df_grade_wait["dt_minutes"],
    bins=bins,
    include_lowest=True
)

df_grade_wait["bin_center"] = df_grade_wait["dt_bin"].apply(
    lambda x: np.sqrt(x.left * x.right)
).astype(float)

# ============================================================
# P(send | previous fail, dt), split by grade
# ============================================================

df_after_fail_by_grade = df_grade_wait[df_grade_wait["prev_send"] == 0].copy()

after_fail_grade_summary = (
    df_after_fail_by_grade
    .groupby(["grade", "dt_bin"], observed=True)
    .agg(
        n_total=("curr_send", "size"),
        n_sends=("curr_send", "sum"),
        p_send_after_fail=("curr_send", "mean"),
        bin_center=("bin_center", "mean")
    )
    .reset_index()
)

after_fail_grade_summary["se"] = np.sqrt(
    after_fail_grade_summary["p_send_after_fail"] *
    (1 - after_fail_grade_summary["p_send_after_fail"]) /
    after_fail_grade_summary["n_total"]
)

after_fail_grade_summary = after_fail_grade_summary[
    after_fail_grade_summary["n_total"] >= min_bin_attempts
].copy()

plt.figure(figsize=(11, 6))

for grade, sub in after_fail_grade_summary.groupby("grade"):
    plt.errorbar(
        sub["bin_center"],
        sub["p_send_after_fail"],
        yerr=sub["se"],
        marker="o",
        capsize=2,
        linewidth=1.5,
        label=f"grade {grade:g}"
    )

plt.xscale("log")

plt.xlabel("Minutes since failed attempt, log scale")
plt.ylabel("P(send | previous fail)")
plt.title(
    f"P(send | previous fail, wait interval), split by grade\n"
    f"intervals ≤ {max_interval_minutes} min"
)

plt.axvline(10, linestyle="--", linewidth=1, label="10 min")
plt.axvline(60, linestyle="--", linewidth=1, label="1 hour")

plt.ylim(-0.05, 1.05)
plt.legend(title="Grade", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()

# ============================================================
# P(current send | dt), split by grade
# ============================================================

send_by_grade_summary = (
    df_grade_wait
    .groupby(["grade", "dt_bin"], observed=True)
    .agg(
        n_total=("curr_send", "size"),
        n_sends=("curr_send", "sum"),
        p_send=("curr_send", "mean"),
        bin_center=("bin_center", "mean")
    )
    .reset_index()
)

send_by_grade_summary["se"] = np.sqrt(
    send_by_grade_summary["p_send"] *
    (1 - send_by_grade_summary["p_send"]) /
    send_by_grade_summary["n_total"]
)

send_by_grade_summary = send_by_grade_summary[
    send_by_grade_summary["n_total"] >= min_bin_attempts
].copy()

plt.figure(figsize=(11, 6))

for grade, sub in send_by_grade_summary.groupby("grade"):
    plt.errorbar(
        sub["bin_center"],
        sub["p_send"],
        yerr=sub["se"],
        marker="o",
        capsize=2,
        linewidth=1.5,
        label=f"grade {grade:g}"
    )

plt.xscale("log")

plt.xlabel("Minutes since previous attempt, log scale")
plt.ylabel("P(current attempt is send)")
plt.title(
    f"P(current send | wait interval), split by grade\n"
    f"intervals ≤ {max_interval_minutes} min"
)

plt.axvline(10, linestyle="--", linewidth=1, label="10 min")
plt.axvline(60, linestyle="--", linewidth=1, label="1 hour")

plt.ylim(-0.05, 1.05)
plt.legend(title="Grade", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()

# ============================================================
# Attempts until next send
# Raw histogram
# ============================================================

date_col = "time"

df_trials = df.copy()
df_trials["datetime"] = pd.to_datetime(df_trials[date_col])
df_trials = df_trials.dropna(subset=["datetime", "grade"]).sort_values("datetime").copy()

# Make sure send is binary
if "send" not in df_trials.columns:
    df_trials = df_trials[df_trials["send/reps"].isin([0, 1])].copy()
    df_trials["send"] = df_trials["send/reps"].astype(int)
else:
    df_trials = df_trials[df_trials["send"].isin([0, 1])].copy()
    df_trials["send"] = df_trials["send"].astype(int)

df_trials["grade"] = pd.to_numeric(df_trials["grade"], errors="coerce")
df_trials = df_trials.dropna(subset=["grade"])

rows = []

attempts_since_last_send = None
last_send_time = None
last_send_grade = None

for idx, row in df_trials.iterrows():
    y = row["send"]

    # Before the first send, we do not know what cycle we are in
    if attempts_since_last_send is None:
        if y == 1:
            attempts_since_last_send = 0
            last_send_time = row["datetime"]
            last_send_grade = row["grade"]
        continue

    # Count this attempt
    attempts_since_last_send += 1

    # If this attempt is a send, close the cycle
    if y == 1:
        rows.append({
            "send_time": row["datetime"],
            "trials_to_send": attempts_since_last_send,
            "target_send_grade": row["grade"],
            "previous_send_grade": last_send_grade,
            "grade_change": row["grade"] - last_send_grade,
            "minutes_since_previous_send": (
                row["datetime"] - last_send_time
            ).total_seconds() / 60
        })

        # Reset for next cycle
        attempts_since_last_send = 0
        last_send_time = row["datetime"]
        last_send_grade = row["grade"]

trials_to_send_df = pd.DataFrame(rows)

print("\nTrials-to-send data:")
print(trials_to_send_df.head())

print("\nTrials-to-send summary:")
print(trials_to_send_df["trials_to_send"].describe())

# ============================================================
# Raw histogram: attempts until next send
# ============================================================

max_trials_to_plot = trials_to_send_df["trials_to_send"].max()

bins = np.arange(0.5, max_trials_to_plot + 1.5, 1)

plt.figure(figsize=(10, 5))

plt.hist(
    trials_to_send_df["trials_to_send"],
    bins=bins,
    edgecolor="black"
)

plt.xlabel("Number of attempts until next send")
plt.ylabel("Count")
plt.title("Attempts until next send")
plt.xscale("log")
plt.yscale("log")
plt.xticks(np.arange(1, max_trials_to_plot + 1))
plt.tight_layout()

# ============================================================
# Probability histogram: attempts until next send
# ============================================================

trial_prob = (
    trials_to_send_df
    .groupby("trials_to_send")
    .size()
    .reset_index(name="n")
)

trial_prob["p"] = trial_prob["n"] / trial_prob["n"].sum()

plt.figure(figsize=(10, 5))

plt.bar(
    trial_prob["trials_to_send"],
    trial_prob["p"]
)

plt.xlabel("Number of attempts until next send")
plt.ylabel("Probability")
plt.xscale("log")
plt.yscale("log")
plt.title("Probability distribution of attempts until next send")
plt.xticks(trial_prob["trials_to_send"])
plt.tight_layout()

# ============================================================
# Grade-controlled attempts-to-send distribution
# Equal-weight average over target send grades
# ============================================================

min_sends_per_grade = 5

valid_grades = (
    trials_to_send_df
    .groupby("target_send_grade")
    .size()
    .loc[lambda x: x >= min_sends_per_grade]
    .index
)

trials_grade_control = trials_to_send_df[
    trials_to_send_df["target_send_grade"].isin(valid_grades)
].copy()

# Count trials_to_send within each grade
grade_trial_counts = (
    trials_grade_control
    .groupby(["target_send_grade", "trials_to_send"])
    .size()
    .reset_index(name="n")
)

# Normalize within grade
grade_totals = (
    grade_trial_counts
    .groupby("target_send_grade")["n"]
    .transform("sum")
)

grade_trial_counts["p_within_grade"] = grade_trial_counts["n"] / grade_totals

# Average probabilities across grades
grade_controlled_prob = (
    grade_trial_counts
    .groupby("trials_to_send")
    .agg(
        p_grade_controlled=("p_within_grade", "mean"),
        se_grade_controlled=("p_within_grade", lambda x: x.std(ddof=1) / np.sqrt(len(x))),
        n_grades=("target_send_grade", "nunique")
    )
    .reset_index()
)

print("\nGrade-controlled trials-to-send distribution:")
print(grade_controlled_prob)
# ============================================================
# Plot grade-controlled probability distribution
# ============================================================

plt.figure(figsize=(10, 5))

plt.errorbar(
    grade_controlled_prob["trials_to_send"],
    grade_controlled_prob["p_grade_controlled"],
    yerr=grade_controlled_prob["se_grade_controlled"],
    marker="o",
    capsize=3,
    linewidth=1.5
)

plt.xlabel("Number of attempts until next send")
plt.ylabel("Grade-controlled probability")
plt.title(
    "Attempts until next send, controlling for grade\n"
    "Equal-weight average over target send grades"
)
plt.xscale("log")
plt.yscale("log")
plt.xticks(grade_controlled_prob["trials_to_send"])
plt.tight_layout()

# ============================================================
# Attempts-to-send distribution split by target send grade
# ============================================================

plt.figure(figsize=(11, 6))

for grade, sub in grade_trial_counts.groupby("target_send_grade"):
    plt.plot(
        sub["trials_to_send"],
        sub["p_within_grade"],
        marker="o",
        linewidth=1.5,
        label=f"grade {grade:g}"
    )

plt.xlabel("Number of attempts until next send")
plt.ylabel("Probability within grade")
plt.title("Attempts until next send, split by target send grade")
plt.xscale("log")
plt.yscale("log")
plt.legend(title="Target send grade", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()

# ============================================================
# Attempts-to-send distribution split by target send grade
# Separate axes for inside/outside
# Log-log scale
# ============================================================

date_col = "time"

df_trials_io = df.copy()
df_trials_io["datetime"] = pd.to_datetime(df_trials_io[date_col])
df_trials_io = df_trials_io.dropna(subset=["datetime", "grade"]).sort_values("datetime").copy()

# Make sure send is binary
if "send" not in df_trials_io.columns:
    df_trials_io = df_trials_io[df_trials_io["send/reps"].isin([0, 1])].copy()
    df_trials_io["send"] = df_trials_io["send/reps"].astype(int)
else:
    df_trials_io = df_trials_io[df_trials_io["send"].isin([0, 1])].copy()
    df_trials_io["send"] = df_trials_io["send"].astype(int)

df_trials_io["grade"] = pd.to_numeric(df_trials_io["grade"], errors="coerce")
df_trials_io = df_trials_io.dropna(subset=["grade"])

df_trials_io["label"] = df_trials_io["outside"].apply(
    lambda x: "outside" if x == 1 else "inside"
)

rows = []

# Do the send-to-send cycle calculation separately for inside/outside
# so indoor/outdoor attempts do not cross-contaminate cycles
for label, subdf in df_trials_io.groupby("label"):
    subdf = subdf.sort_values("datetime").copy()

    attempts_since_last_send = None
    last_send_time = None
    last_send_grade = None

    for idx, row in subdf.iterrows():
        y = row["send"]

        # Ignore attempts before first send in this label
        if attempts_since_last_send is None:
            if y == 1:
                attempts_since_last_send = 0
                last_send_time = row["datetime"]
                last_send_grade = row["grade"]
            continue

        # Count current attempt
        attempts_since_last_send += 1

        # If current attempt is a send, close the cycle
        if y == 1:
            rows.append({
                "label": label,
                "send_time": row["datetime"],
                "trials_to_send": attempts_since_last_send,
                "target_send_grade": row["grade"],
                "previous_send_grade": last_send_grade,
                "grade_change": row["grade"] - last_send_grade,
                "minutes_since_previous_send": (
                    row["datetime"] - last_send_time
                ).total_seconds() / 60
            })

            # Reset
            attempts_since_last_send = 0
            last_send_time = row["datetime"]
            last_send_grade = row["grade"]

trials_to_send_io_df = pd.DataFrame(rows)

print("\nTrials-to-send by inside/outside:")
print(trials_to_send_io_df.head())
print(trials_to_send_io_df.groupby("label")["trials_to_send"].describe())

# ============================================================
# Within-grade distributions, separately for inside/outside
# ============================================================

min_sends_per_grade = 5

# Keep only label-grade combinations with enough completed send cycles
valid_label_grades = (
    trials_to_send_io_df
    .groupby(["label", "target_send_grade"])
    .size()
    .reset_index(name="n")
)

valid_label_grades = valid_label_grades[
    valid_label_grades["n"] >= min_sends_per_grade
][["label", "target_send_grade"]]

trials_to_send_io_filt = trials_to_send_io_df.merge(
    valid_label_grades,
    on=["label", "target_send_grade"],
    how="inner"
)

grade_trial_counts_io = (
    trials_to_send_io_filt
    .groupby(["label", "target_send_grade", "trials_to_send"])
    .size()
    .reset_index(name="n")
)

# Normalize within each inside/outside × grade combination
grade_trial_counts_io["p_within_grade"] = (
    grade_trial_counts_io["n"] /
    grade_trial_counts_io
        .groupby(["label", "target_send_grade"])["n"]
        .transform("sum")
)

print("\nInside/outside grade-split trials-to-send distribution:")
print(grade_trial_counts_io.head())

# ============================================================
# Plot: separate axes for inside/outside, grade curves on each
# Log-log
# ============================================================

fig, axes = plt.subplots(
    nrows=2,
    ncols=1,
    figsize=(11, 9),
    sharex=True,
    sharey=True
)

label_order = ["inside", "outside"]

for ax, label in zip(axes, label_order):
    sub_label = grade_trial_counts_io[
        grade_trial_counts_io["label"] == label
    ].copy()

    if sub_label.empty:
        ax.set_title(f"{label}: no data after filtering")
        continue

    for grade, sub in sub_label.groupby("target_send_grade"):
        sub_plot = sub[sub["p_within_grade"] > 0].copy()

        if sub_plot.empty:
            continue

        ax.plot(
            sub_plot["trials_to_send"],
            sub_plot["p_within_grade"],
            marker="o",
            linewidth=1.5,
            label=f"grade {grade:g}"
        )

    ax.set_xscale("log")
    ax.set_yscale("log")

    ax.set_ylabel("Probability within grade, log scale")
    ax.set_title(f"{label}: attempts until next send by target grade")
    ax.legend(
        title="Target send grade",
        bbox_to_anchor=(1.05, 1),
        loc="upper left"
    )

axes[-1].set_xlabel("Number of attempts until next send, log scale")

plt.tight_layout()

# ============================================================
# Flash probability by grade
# flash = send occurred on first attempt after previous send
# i.e. trials_to_send == 1
# ============================================================

flash_by_grade = (
    trials_to_send_df
    .assign(flash=lambda d: d["trials_to_send"] == 1)
    .groupby("target_send_grade")
    .agg(
        n_sends=("flash", "size"),
        n_flashes=("flash", "sum"),
        p_flash=("flash", "mean")
    )
    .reset_index()
    .sort_values("target_send_grade")
)

flash_by_grade["se_flash"] = np.sqrt(
    flash_by_grade["p_flash"] *
    (1 - flash_by_grade["p_flash"]) /
    flash_by_grade["n_sends"]
)

print("\nFlash probability by grade:")
print(flash_by_grade)

# ============================================================
# Plot flash probability by grade
# ============================================================

plt.figure(figsize=(10, 5))

plt.bar(
    flash_by_grade["target_send_grade"],
    flash_by_grade["p_flash"],
    yerr=flash_by_grade["se_flash"],
    capsize=4
)

plt.xlabel("Grade")
plt.ylabel("Flash probability")
plt.title("Flash probability by grade")
plt.ylim(0, 1.05)

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

plt.xlabel("Week")
plt.ylabel("Total V-points")
plt.title("Total V-points per week")
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()
