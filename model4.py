import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, minimize
from scipy.stats import chi2, f, linregress, mannwhitneyu, pearsonr, spearmanr, t, ttest_ind


# ---- settings ----
csv_path = "climb_data (4).csv"
date_col = "time"
group_by_outside = True
past_month_days = 28
next_week_days = 7
rolling_x50_days = 60
min_rolling_fit_attempts = 30
log_base = "e"
min_probability = 1e-6

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


def logistic(grade, x50, scale):
    return 1 / (1 + np.exp((grade - x50) / scale))


def fit_one(data, label):
    summary = (
        data
        .groupby("grade")
        .agg(
            n=("send", "size"),
            sends=("send", "sum"),
            p_send=("send", "mean")
        )
        .reset_index()
        .sort_values("grade")
    )

    summary["se"] = np.sqrt(summary["p_send"] * (1 - summary["p_send"]) / summary["n"])
    summary["se_fit"] = summary["se"].replace(0, np.nan)
    fallback_se = 1 / np.sqrt(4 * summary["n"])
    summary["se_fit"] = summary["se_fit"].fillna(fallback_se)

    x = summary["grade"].to_numpy()
    y = summary["p_send"].to_numpy()
    sigma = summary["se_fit"].to_numpy()

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

    print(f"\nFit for {label}")
    print(f"  x50   = {popt[0]:.3f} +/- {perr[0]:.3f}")
    print(f"  scale = {popt[1]:.3f} +/- {perr[1]:.3f}")

    return summary, popt, perr, label


def fit_window_x50(data):
    if (
        len(data) < min_rolling_fit_attempts or
        data["grade"].nunique() < 3 or
        data["send"].nunique() < 2
    ):
        return np.nan, np.nan, len(data)

    summary = (
        data
        .groupby("grade")
        .agg(
            n=("send", "size"),
            p_send=("send", "mean")
        )
        .reset_index()
        .sort_values("grade")
    )

    if len(summary) < 3:
        return np.nan, np.nan, len(data)

    summary["se"] = np.sqrt(summary["p_send"] * (1 - summary["p_send"]) / summary["n"])
    summary["se_fit"] = summary["se"].replace(0, np.nan)
    fallback_se = 1 / np.sqrt(4 * summary["n"])
    summary["se_fit"] = summary["se_fit"].fillna(fallback_se)

    try:
        popt, _ = curve_fit(
            logistic,
            summary["grade"].to_numpy(),
            summary["p_send"].to_numpy(),
            p0=[summary["grade"].median(), 1.0],
            sigma=summary["se_fit"].to_numpy(),
            absolute_sigma=True,
            bounds=([-np.inf, 1e-6], [np.inf, np.inf]),
            maxfev=10000
        )
    except (RuntimeError, ValueError, FloatingPointError):
        return np.nan, np.nan, len(data)

    return popt[0], popt[1], len(data)


def expected_send_probability(row):
    pars = fit_params[row["label"]]
    return logistic(row["grade"], pars["x50"], pars["scale"])


def test_predictor(data, predictor_col, outcome_col):
    test_data = data[[predictor_col, outcome_col]].dropna().copy()
    x = test_data[predictor_col].to_numpy(dtype=float)
    y = test_data[outcome_col].to_numpy(dtype=float)

    if len(test_data) < 3 or len(np.unique(x)) < 2:
        return {
            "predictor": predictor_col,
            "n": len(test_data),
            "slope": np.nan,
            "intercept": np.nan,
            "r": np.nan,
            "r_squared": np.nan,
            "linear_p": np.nan,
            "pearson_r": np.nan,
            "pearson_p": np.nan,
            "spearman_r": np.nan,
            "spearman_p": np.nan
        }

    linear = linregress(x, y)
    pearson = pearsonr(x, y)
    spearman = spearmanr(x, y)

    return {
        "predictor": predictor_col,
        "n": len(test_data),
        "slope": linear.slope,
        "intercept": linear.intercept,
        "r": linear.rvalue,
        "r_squared": linear.rvalue ** 2,
        "linear_p": linear.pvalue,
        "pearson_r": pearson.statistic,
        "pearson_p": pearson.pvalue,
        "spearman_r": spearman.statistic,
        "spearman_p": spearman.pvalue
    }


def multiple_linear_regression(data, predictor_cols, outcome_col):
    test_data = data[predictor_cols + [outcome_col]].dropna().copy()
    n = len(test_data)
    p = len(predictor_cols)

    if n <= p + 1:
        empty_coef = pd.DataFrame({
            "predictor": predictor_cols,
            "coef": np.nan,
            "std_error": np.nan,
            "t": np.nan,
            "p": np.nan,
            "standardized_coef": np.nan
        })
        return {
            "data": test_data,
            "coef_table": empty_coef,
            "intercept": np.nan,
            "n": n,
            "r_squared": np.nan,
            "adj_r_squared": np.nan,
            "f_p": np.nan,
            "predicted": np.full(n, np.nan)
        }

    x = test_data[predictor_cols].to_numpy(dtype=float)
    y = test_data[outcome_col].to_numpy(dtype=float)
    design = np.column_stack([np.ones(n), x])

    beta, residuals, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    y_hat = design @ beta
    residual = y - y_hat
    dof = n - p - 1
    sse = np.sum(residual ** 2)
    sst = np.sum((y - y.mean()) ** 2)
    mse = sse / dof
    xtx_inv = np.linalg.pinv(design.T @ design)
    std_errors = np.sqrt(np.diag(xtx_inv) * mse)
    t_stats = beta / std_errors
    p_values = 2 * t.sf(np.abs(t_stats), df=dof)
    r_squared = 1 - sse / sst
    adj_r_squared = 1 - (1 - r_squared) * (n - 1) / dof

    if p > 0 and sse > 0:
        f_stat = ((sst - sse) / p) / (sse / dof)
        f_p = f.sf(f_stat, p, dof)
    else:
        f_p = np.nan

    y_sd = y.std(ddof=0)
    x_sd = test_data[predictor_cols].std(ddof=0).to_numpy(dtype=float)
    standardized = beta[1:] * x_sd / y_sd

    coef_table = pd.DataFrame({
        "predictor": predictor_cols,
        "coef": beta[1:],
        "std_error": std_errors[1:],
        "t": t_stats[1:],
        "p": p_values[1:],
        "standardized_coef": standardized
    })

    return {
        "data": test_data,
        "coef_table": coef_table,
        "intercept": beta[0],
        "n": n,
        "r_squared": r_squared,
        "adj_r_squared": adj_r_squared,
        "f_p": f_p,
        "predicted": y_hat
    }


def test_binary_outcome_predictor(data, predictor_col, outcome_col):
    test_data = data[[predictor_col, outcome_col]].dropna().copy()
    x = test_data[predictor_col].to_numpy(dtype=float)
    y = test_data[outcome_col].to_numpy(dtype=float)

    if len(test_data) < 3 or len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
        return {
            "predictor": predictor_col,
            "n": len(test_data),
            "n_positive": int(y.sum()) if len(test_data) else 0,
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

    event_rate = np.clip(y.mean(), 1e-9, 1 - 1e-9)
    null_intercept = np.log(event_rate / (1 - event_rate))
    null_log_likelihood = -neg_log_likelihood([null_intercept, 0])

    result = minimize(
        neg_log_likelihood,
        x0=np.array([null_intercept, 0.0]),
        method="BFGS"
    )

    full_log_likelihood = -result.fun
    likelihood_ratio = max(0, 2 * (full_log_likelihood - null_log_likelihood))
    logistic_lrt_p = chi2.sf(likelihood_ratio, df=1)

    positive_values = x[y == 1]
    negative_values = x[y == 0]
    mann_result = mannwhitneyu(
        positive_values,
        negative_values,
        alternative="two-sided"
    )
    auc = mann_result.statistic / (len(positive_values) * len(negative_values))

    return {
        "predictor": predictor_col,
        "n": len(test_data),
        "n_positive": int(y.sum()),
        "odds_ratio_per_sd": np.exp(result.x[1]),
        "logistic_lrt_p": logistic_lrt_p,
        "mann_whitney_p": mann_result.pvalue,
        "auc": auc,
        "beta": result.x[1],
        "intercept": result.x[0],
        "x_mean": x_mean,
        "x_sd": x_sd
    }


def forward_rolling_sum(series, window):
    return (
        series
        .iloc[::-1]
        .shift(1)
        .rolling(window, min_periods=1)
        .sum()
        .iloc[::-1]
    )


def forward_rolling_sum_including_current(series, window):
    return (
        series
        .iloc[::-1]
        .rolling(window, min_periods=1)
        .sum()
        .iloc[::-1]
    )


# ---- load / clean ----
df = pd.read_csv(csv_path)

df = df[df["send/reps"].isin([0, 1])].copy()
df["datetime"] = pd.to_datetime(df[date_col])
df["day"] = df["datetime"].dt.normalize()
df["grade"] = pd.to_numeric(df["grade"], errors="coerce")
df["send"] = df["send/reps"].astype(float)
df = df.dropna(subset=["datetime", "day", "grade", "send"])


# ---- fit send-probability model ----
fits = []

if group_by_outside:
    for outside_value, sub in df.groupby("outside"):
        label = "outside" if outside_value == 1 else "inside"
        fits.append(fit_one(sub, label))
else:
    fits.append(fit_one(df, "all climbs"))

fit_params = {}

for summary, popt, perr, label in fits:
    fit_params[label] = {
        "x50": popt[0],
        "scale": popt[1]
    }

if group_by_outside:
    df["label"] = df["outside"].apply(
        lambda x: "outside" if x == 1 else "inside"
    )
else:
    df["label"] = "all climbs"

df["p_send_expected"] = df.apply(expected_send_probability, axis=1)
df["p_send_expected"] = df["p_send_expected"].clip(
    lower=min_probability,
    upper=1 - min_probability
)
df["p_fail_expected"] = 1 - df["p_send_expected"]

if log_base == "2":
    log_fun = np.log2
    unit_label = "bits"
else:
    log_fun = np.log
    unit_label = "nats"


# ---- attempt-level performance ----
df["surprise_send"] = np.where(
    df["send"] == 1,
    -log_fun(df["p_send_expected"]),
    0.0
)
df["surprise_fail"] = np.where(
    df["send"] == 0,
    -log_fun(df["p_fail_expected"]),
    0.0
)
df["performance"] = df["surprise_send"] - df["surprise_fail"]
df["info_load"] = df["surprise_send"] + df["surprise_fail"]

daily_performance = (
    df
    .groupby("day")
    .agg(
        mean_performance=("performance", "mean"),
        total_performance=("performance", "sum"),
        n_attempts=("performance", "size"),
        n_sends=("send", "sum")
    )
    .reset_index()
)
daily_performance["n_fails"] = (
    daily_performance["n_attempts"] - daily_performance["n_sends"]
)

daily_load = (
    df
    .groupby("day")
    .agg(
        daily_total_info_load=("info_load", "sum"),
        daily_mean_info_load=("info_load", "mean"),
        daily_mean_send_surprise=("surprise_send", "mean")
    )
    .reset_index()
)


# ---- past-month V-grade predictors ----
daily_vgrades = df.copy()
daily_vgrades["attempt_vgrades"] = daily_vgrades["grade"]
daily_vgrades["send_vgrades"] = np.where(
    daily_vgrades["send"] == 1,
    daily_vgrades["grade"],
    0.0
)
daily_vgrades["fail_vgrades"] = np.where(
    daily_vgrades["send"] == 0,
    daily_vgrades["grade"],
    0.0
)

daily_vgrades = (
    daily_vgrades
    .groupby("day")
    .agg(
        daily_attempt_vgrades=("attempt_vgrades", "sum"),
        daily_send_vgrades=("send_vgrades", "sum"),
        daily_fail_vgrades=("fail_vgrades", "sum")
    )
    .reset_index()
)

daily_outside = df.copy()
daily_outside["outside_attempt"] = np.where(daily_outside["outside"] == 1, 1.0, 0.0)

daily_outside = (
    daily_outside
    .groupby("day")
    .agg(
        daily_outside_attempts=("outside_attempt", "sum"),
        daily_total_attempts=("outside_attempt", "size")
    )
    .reset_index()
)

daily_sessions = (
    df
    .groupby("day")
    .agg(
        session_start=("datetime", "min"),
        session_end=("datetime", "max")
    )
    .reset_index()
)
daily_sessions["session_duration_min"] = (
    daily_sessions["session_end"] - daily_sessions["session_start"]
).dt.total_seconds() / 60
daily_sessions = daily_sessions[["day", "session_duration_min"]]

full_days = pd.date_range(df["day"].min(), df["day"].max(), freq="D")

analysis_df = (
    pd.DataFrame({"day": full_days})
    .merge(daily_vgrades, on="day", how="left")
    .merge(daily_load, on="day", how="left")
    .merge(daily_outside, on="day", how="left")
    .merge(daily_sessions, on="day", how="left")
    .merge(daily_performance, on="day", how="left")
)

vgrade_cols = [
    "daily_attempt_vgrades",
    "daily_send_vgrades",
    "daily_fail_vgrades"
]
analysis_df[vgrade_cols] = analysis_df[vgrade_cols].fillna(0)
analysis_df["daily_total_info_load"] = analysis_df["daily_total_info_load"].fillna(0)
analysis_df["daily_mean_info_load"] = analysis_df["daily_mean_info_load"].fillna(0)
analysis_df["daily_mean_send_surprise"] = analysis_df["daily_mean_send_surprise"].fillna(0)
analysis_df["daily_outside_attempts"] = analysis_df["daily_outside_attempts"].fillna(0)
analysis_df["daily_total_attempts"] = analysis_df["daily_total_attempts"].fillna(0)
analysis_df["daily_avg_attempt_vgrade"] = (
    analysis_df["daily_attempt_vgrades"] /
    analysis_df["daily_total_attempts"].replace(0, np.nan)
)
analysis_df["daily_outside_attempt_share"] = (
    analysis_df["daily_outside_attempts"] /
    analysis_df["daily_total_attempts"].replace(0, np.nan)
)
analysis_df["daily_venue"] = np.where(
    analysis_df["daily_outside_attempt_share"] >= 0.5,
    "outside",
    "inside"
)

past_month_outside_attempts = (
    analysis_df["daily_outside_attempts"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
past_month_total_attempts = (
    analysis_df["daily_total_attempts"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
analysis_df["past_month_outside_attempts"] = past_month_outside_attempts
analysis_df["past_month_outside_attempt_share"] = (
    past_month_outside_attempts /
    past_month_total_attempts.replace(0, np.nan)
)

injury_days = pd.Series(injury_dates).dt.normalize()
analysis_df["injury"] = (
    analysis_df["day"].dt.normalize().isin(injury_days).astype(int)
)

analysis_df["acute_total_info_load"] = (
    analysis_df["daily_total_info_load"]
    .rolling(next_week_days, min_periods=next_week_days)
    .sum()
)
analysis_df["chronic_total_info_load"] = (
    analysis_df["daily_total_info_load"]
    .rolling(past_month_days, min_periods=past_month_days)
    .sum()
)
analysis_df["acwr_total_info_load"] = (
    analysis_df["acute_total_info_load"] /
    analysis_df["chronic_total_info_load"]
)

analysis_df["acute_mean_info_load"] = (
    analysis_df["daily_mean_info_load"]
    .rolling(next_week_days, min_periods=next_week_days)
    .mean()
)
analysis_df["chronic_mean_info_load"] = (
    analysis_df["daily_mean_info_load"]
    .rolling(past_month_days, min_periods=past_month_days)
    .mean()
)
analysis_df["acwr_mean_info_load"] = (
    analysis_df["acute_mean_info_load"] /
    analysis_df["chronic_mean_info_load"]
)
analysis_df["acute_mean_send_surprise"] = (
    analysis_df["daily_mean_send_surprise"]
    .rolling(next_week_days, min_periods=next_week_days)
    .mean()
)
analysis_df["chronic_mean_send_surprise"] = (
    analysis_df["daily_mean_send_surprise"]
    .rolling(past_month_days, min_periods=past_month_days)
    .mean()
)
analysis_df["acwr_mean_send_surprise"] = (
    analysis_df["acute_mean_send_surprise"] /
    analysis_df["chronic_mean_send_surprise"]
)
analysis_df["acute_total_vpoints"] = (
    analysis_df["daily_attempt_vgrades"]
    .rolling(next_week_days, min_periods=next_week_days)
    .sum()
)
analysis_df["chronic_total_vpoints"] = (
    analysis_df["daily_attempt_vgrades"]
    .rolling(past_month_days, min_periods=past_month_days)
    .sum()
)
analysis_df["acwr_total_vpoints"] = (
    analysis_df["acute_total_vpoints"] /
    analysis_df["chronic_total_vpoints"]
)
analysis_df["acute_avg_vpoints"] = (
    analysis_df["daily_avg_attempt_vgrade"]
    .fillna(0)
    .rolling(next_week_days, min_periods=next_week_days)
    .mean()
)
analysis_df["chronic_avg_vpoints"] = (
    analysis_df["daily_avg_attempt_vgrade"]
    .fillna(0)
    .rolling(past_month_days, min_periods=past_month_days)
    .mean()
)
analysis_df["acwr_avg_vpoints"] = (
    analysis_df["acute_avg_vpoints"] /
    analysis_df["chronic_avg_vpoints"]
)
analysis_df = analysis_df.replace([np.inf, -np.inf], np.nan)

analysis_df["past_month_attempt_vgrades"] = (
    analysis_df["daily_attempt_vgrades"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
analysis_df["past_month_send_vgrades"] = (
    analysis_df["daily_send_vgrades"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
analysis_df["past_month_fail_vgrades"] = (
    analysis_df["daily_fail_vgrades"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
analysis_df["past_month_avg_attempt_vgrade"] = (
    analysis_df["past_month_attempt_vgrades"] /
    analysis_df["n_attempts"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
    .replace(0, np.nan)
)
analysis_df["past_month_total_info_load"] = (
    analysis_df["daily_total_info_load"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
analysis_df["past_month_mean_info_load"] = (
    analysis_df["daily_mean_info_load"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .mean()
)
analysis_df["past_month_avg_session_duration_min"] = (
    analysis_df["session_duration_min"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .mean()
)
analysis_df["past_week_total_acwr"] = (
    analysis_df["acwr_total_info_load"]
    .shift(1)
    .rolling(next_week_days, min_periods=1)
    .mean()
)
analysis_df["past_week_mean_acwr"] = (
    analysis_df["acwr_mean_info_load"]
    .shift(1)
    .rolling(next_week_days, min_periods=1)
    .mean()
)
analysis_df["past_month_send_surprise_acwr"] = (
    analysis_df["acwr_mean_send_surprise"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .mean()
)
analysis_df["past_month_total_vpoints_acwr"] = (
    analysis_df["acwr_total_vpoints"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .mean()
)
analysis_df["past_month_avg_vpoints_acwr"] = (
    analysis_df["acwr_avg_vpoints"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .mean()
)

calendar_analysis_df = analysis_df.copy()
for col in ["total_performance", "n_attempts", "n_sends", "n_fails"]:
    calendar_analysis_df[col] = calendar_analysis_df[col].fillna(0)

calendar_analysis_df["rested_yesterday"] = (
    calendar_analysis_df["n_attempts"].shift(1).fillna(0) == 0
).astype(int)

past_month_total_performance = (
    calendar_analysis_df["total_performance"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
past_month_attempts = (
    calendar_analysis_df["n_attempts"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
calendar_analysis_df["past_month_performance"] = (
    past_month_total_performance /
    past_month_attempts.replace(0, np.nan)
)

past_60d_total_performance = (
    calendar_analysis_df["total_performance"]
    .shift(1)
    .rolling(rolling_x50_days, min_periods=1)
    .sum()
)
past_60d_attempts = (
    calendar_analysis_df["n_attempts"]
    .shift(1)
    .rolling(rolling_x50_days, min_periods=1)
    .sum()
)
calendar_analysis_df["past_60d_performance"] = (
    past_60d_total_performance /
    past_60d_attempts.replace(0, np.nan)
)

rolling_x50_rows = []

for day in full_days:
    window_start = day - pd.Timedelta(days=rolling_x50_days)
    window_data = df[
        (df["day"] >= window_start) &
        (df["day"] < day)
    ]
    x50, scale, n_attempts = fit_window_x50(window_data)
    rolling_x50_rows.append({
        "day": day,
        "rolling_60d_x50": x50,
        "rolling_60d_scale": scale,
        "rolling_60d_fit_attempts": n_attempts
    })

rolling_x50_df = pd.DataFrame(rolling_x50_rows)
calendar_analysis_df = calendar_analysis_df.merge(
    rolling_x50_df,
    on="day",
    how="left"
)

next_day_total_performance = forward_rolling_sum(
    calendar_analysis_df["total_performance"],
    1
)
next_day_attempts = forward_rolling_sum(
    calendar_analysis_df["n_attempts"],
    1
)
calendar_analysis_df["next_day_mean_performance"] = (
    next_day_total_performance /
    next_day_attempts.replace(0, np.nan)
)

next_week_total_performance = forward_rolling_sum(
    calendar_analysis_df["total_performance"],
    next_week_days
)
next_week_attempts = forward_rolling_sum(
    calendar_analysis_df["n_attempts"],
    next_week_days
)
calendar_analysis_df["next_week_mean_performance"] = (
    next_week_total_performance /
    next_week_attempts.replace(0, np.nan)
)

current_week_total_performance = forward_rolling_sum_including_current(
    calendar_analysis_df["total_performance"],
    next_week_days
)
current_week_attempts = forward_rolling_sum_including_current(
    calendar_analysis_df["n_attempts"],
    next_week_days
)
calendar_analysis_df["current_week_mean_performance"] = (
    current_week_total_performance /
    current_week_attempts.replace(0, np.nan)
)
weekly_anchor_df = calendar_analysis_df[
    calendar_analysis_df["day"].dt.dayofweek == 0
].copy()
weekly_anchor_df["next_week_mean_performance"] = (
    weekly_anchor_df["current_week_mean_performance"]
)

analysis_df = analysis_df.dropna(subset=["mean_performance"]).copy()

predictor_specs = [
    ("past_month_attempt_vgrades", "Past-month attempted V-grade total"),
    ("past_month_avg_attempt_vgrade", "Past-month average attempted V-grade"),
    ("past_month_send_vgrades", "Past-month sent V-grade total"),
    ("past_month_fail_vgrades", "Past-month failed V-grade total"),
    ("past_month_total_info_load", "Past-month total information load"),
    ("past_month_mean_info_load", "Past-month mean information load"),
    ("past_month_avg_session_duration_min", "Past-month average session duration")
]

test_results = pd.DataFrame([
    {
        **test_predictor(analysis_df, predictor_col, "mean_performance"),
        "label": label
    }
    for predictor_col, label in predictor_specs
])

print("\nPast-month volume/load predictors of daily mean performance")
print("Performance = surprise_send - surprise_fail")
print("Past-month predictors use the previous 28 calendar days, excluding the current day.")
print(
    test_results[
        [
            "label",
            "n",
            "slope",
            "r_squared",
            "linear_p",
            "pearson_r",
            "pearson_p",
            "spearman_r",
            "spearman_p"
        ]
    ]
)

next_week_test_results = pd.DataFrame([
    {
        **test_predictor(
            calendar_analysis_df,
            predictor_col,
            "next_week_mean_performance"
        ),
        "label": label
    }
    for predictor_col, label in predictor_specs
])

print("\nPast-month volume/load predictors of next-7-day mean performance")
print("Outcome is attempt-weighted performance over the next 7 calendar days.")
print("Predictors use the previous 28 calendar days, excluding the current day.")
print(
    next_week_test_results[
        [
            "label",
            "n",
            "slope",
            "r_squared",
            "linear_p",
            "pearson_r",
            "pearson_p",
            "spearman_r",
            "spearman_p"
        ]
    ]
)

performance_momentum_specs = [
    (
        calendar_analysis_df,
        "past_month_performance",
        "next_day_mean_performance",
        "Previous 28-day performance predicts next-day performance"
    ),
    (
        weekly_anchor_df,
        "past_month_performance",
        "next_week_mean_performance",
        "Previous 28-day performance predicts next-week performance"
    )
]

performance_momentum_results = pd.DataFrame([
    {
        **test_predictor(test_df, predictor_col, outcome_col),
        "outcome": outcome_col,
        "label": label
    }
    for test_df, predictor_col, outcome_col, label in performance_momentum_specs
])

multi_predictor_cols = [
    "past_month_attempt_vgrades",
    "past_month_avg_session_duration_min",
    "past_month_performance"
]

daily_multi_regression = multiple_linear_regression(
    calendar_analysis_df,
    multi_predictor_cols,
    "mean_performance"
)
weekly_multi_regression = multiple_linear_regression(
    weekly_anchor_df,
    multi_predictor_cols,
    "next_week_mean_performance"
)

x50_performance_specs = [
    (
        calendar_analysis_df,
        "rolling_60d_x50",
        "mean_performance",
        "Prior 60-day x50 predicts today's performance"
    ),
    (
        calendar_analysis_df,
        "past_60d_performance",
        "rolling_60d_x50",
        "Prior 60-day performance predicts rolling x50"
    )
]

x50_performance_results = pd.DataFrame([
    {
        **test_predictor(test_df, predictor_col, outcome_col),
        "outcome": outcome_col,
        "label": label
    }
    for test_df, predictor_col, outcome_col, label in x50_performance_specs
])

acwr_predictor_specs = [
    ("past_week_total_acwr", "Past-week mean total-load ACWR"),
    ("past_week_mean_acwr", "Past-week mean mean-load ACWR"),
    ("past_month_send_surprise_acwr", "Past-month mean send-surprise ACWR"),
    ("past_month_total_vpoints_acwr", "Past-month mean total V-points ACWR"),
    ("past_month_avg_vpoints_acwr", "Past-month mean average V-points ACWR")
]

next_day_acwr_results = pd.DataFrame([
    {
        **test_predictor(
            calendar_analysis_df,
            predictor_col,
            "next_day_mean_performance"
        ),
        "outcome": "next_day_mean_performance",
        "label": label
    }
    for predictor_col, label in acwr_predictor_specs
])

next_week_acwr_results = pd.DataFrame([
    {
        **test_predictor(
            weekly_anchor_df,
            predictor_col,
            "next_week_mean_performance"
        ),
        "outcome": "next_week_mean_performance",
        "label": label
    }
    for predictor_col, label in acwr_predictor_specs
])

print("\nPast-28-day performance predicting future performance")
print("Past performance is attempt-weighted and excludes the current day.")
print("Daily outcome is the next calendar day; weekly outcome is Monday-through-Sunday.")
print(
    performance_momentum_results[
        [
            "label",
            "n",
            "slope",
            "r_squared",
            "linear_p",
            "pearson_r",
            "pearson_p",
            "spearman_r",
            "spearman_p"
        ]
    ]
)

print("\nMultiple linear regression: past month predictors -> daily performance")
print(
    pd.DataFrame([
        {
            "n": daily_multi_regression["n"],
            "r_squared": daily_multi_regression["r_squared"],
            "adj_r_squared": daily_multi_regression["adj_r_squared"],
            "model_f_p": daily_multi_regression["f_p"],
            "intercept": daily_multi_regression["intercept"]
        }
    ])
)
print(daily_multi_regression["coef_table"])

print("\nMultiple linear regression: past month predictors -> weekly performance")
print(
    pd.DataFrame([
        {
            "n": weekly_multi_regression["n"],
            "r_squared": weekly_multi_regression["r_squared"],
            "adj_r_squared": weekly_multi_regression["adj_r_squared"],
            "model_f_p": weekly_multi_regression["f_p"],
            "intercept": weekly_multi_regression["intercept"]
        }
    ])
)
print(weekly_multi_regression["coef_table"])

print("\nRolling 60-day x50 and performance")
print("Rolling x50 uses the previous 60 calendar days, excluding the current day.")
print(
    x50_performance_results[
        [
            "label",
            "n",
            "slope",
            "r_squared",
            "linear_p",
            "pearson_r",
            "pearson_p",
            "spearman_r",
            "spearman_p"
        ]
    ]
)

rest_test_df = calendar_analysis_df[
    ["rested_yesterday", "mean_performance"]
].dropna().copy()
rested_performance = rest_test_df.loc[
    rest_test_df["rested_yesterday"] == 1,
    "mean_performance"
]
not_rested_performance = rest_test_df.loc[
    rest_test_df["rested_yesterday"] == 0,
    "mean_performance"
]
rest_ttest = ttest_ind(
    rested_performance,
    not_rested_performance,
    equal_var=False,
    nan_policy="omit"
)
rest_mann = mannwhitneyu(
    rested_performance,
    not_rested_performance,
    alternative="two-sided"
)
rest_result = test_predictor(
    rest_test_df,
    "rested_yesterday",
    "mean_performance"
)

print("\nDoes resting yesterday predict today's performance?")
print("Resting yesterday means zero climb attempts on the previous calendar day.")
print(
    pd.DataFrame([
        {
            "n_rested": len(rested_performance),
            "n_not_rested": len(not_rested_performance),
            "mean_after_rest": rested_performance.mean(),
            "mean_after_climbing": not_rested_performance.mean(),
            "mean_difference": (
                rested_performance.mean() -
                not_rested_performance.mean()
            ),
            "welch_t_p": rest_ttest.pvalue,
            "mann_whitney_p": rest_mann.pvalue,
            "linear_slope": rest_result["slope"],
            "linear_p": rest_result["linear_p"]
        }
    ])
)

print("\nPast-week ACWR predicting next-day performance")
print("ACWR predictors are prior-7-day averages, excluding the current day.")
print(
    next_day_acwr_results[
        [
            "label",
            "n",
            "slope",
            "r_squared",
            "linear_p",
            "pearson_r",
            "pearson_p",
            "spearman_r",
            "spearman_p"
        ]
    ]
)

print("\nPast-week ACWR predicting next-week performance")
print("Weekly outcome is Monday-through-Sunday performance at Monday anchors.")
print(
    next_week_acwr_results[
        [
            "label",
            "n",
            "slope",
            "r_squared",
            "linear_p",
            "pearson_r",
            "pearson_p",
            "spearman_r",
            "spearman_p"
        ]
    ]
)

outside_injury_specs = [
    ("past_month_outside_attempt_share", "Past-month outside attempt share"),
    ("past_month_outside_attempts", "Past-month outside attempt count")
]

outside_injury_results = pd.DataFrame([
    {
        **test_binary_outcome_predictor(analysis_df, predictor_col, "injury"),
        "label": label
    }
    for predictor_col, label in outside_injury_specs
])

print("\nDoes climbing outside predict injury?")
print("Predictors use outside climbing in the previous 28 days, excluding the current day.")
print(
    outside_injury_results[
        [
            "label",
            "n",
            "n_positive",
            "odds_ratio_per_sd",
            "logistic_lrt_p",
            "mann_whitney_p",
            "auc"
        ]
    ]
)


# ---- past-month inside/outside performance cross-prediction ----
venue_perf = df.copy()
venue_perf["venue"] = np.where(venue_perf["outside"] == 1, "outside", "inside")

daily_venue_perf = (
    venue_perf
    .groupby(["day", "venue"])
    .agg(
        total_performance=("performance", "sum"),
        n_attempts=("performance", "size")
    )
    .reset_index()
)

daily_venue_perf = (
    daily_venue_perf
    .pivot(index="day", columns="venue", values=["total_performance", "n_attempts"])
)
daily_venue_perf.columns = [
    f"{metric}_{venue}" for metric, venue in daily_venue_perf.columns
]
daily_venue_perf = daily_venue_perf.reset_index()

venue_analysis_df = (
    pd.DataFrame({"day": full_days})
    .merge(daily_venue_perf, on="day", how="left")
)

for col in [
    "total_performance_inside",
    "total_performance_outside",
    "n_attempts_inside",
    "n_attempts_outside"
]:
    if col not in venue_analysis_df.columns:
        venue_analysis_df[col] = 0

venue_analysis_df[
    [
        "total_performance_inside",
        "total_performance_outside",
        "n_attempts_inside",
        "n_attempts_outside"
    ]
] = venue_analysis_df[
    [
        "total_performance_inside",
        "total_performance_outside",
        "n_attempts_inside",
        "n_attempts_outside"
    ]
].fillna(0)

venue_analysis_df["mean_performance_inside"] = (
    venue_analysis_df["total_performance_inside"] /
    venue_analysis_df["n_attempts_inside"].replace(0, np.nan)
)
venue_analysis_df["mean_performance_outside"] = (
    venue_analysis_df["total_performance_outside"] /
    venue_analysis_df["n_attempts_outside"].replace(0, np.nan)
)

past_month_inside_total_performance = (
    venue_analysis_df["total_performance_inside"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
past_month_inside_attempts = (
    venue_analysis_df["n_attempts_inside"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
past_month_outside_total_performance = (
    venue_analysis_df["total_performance_outside"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)
past_month_outside_attempts = (
    venue_analysis_df["n_attempts_outside"]
    .shift(1)
    .rolling(past_month_days, min_periods=1)
    .sum()
)

venue_analysis_df["past_month_inside_performance"] = (
    past_month_inside_total_performance /
    past_month_inside_attempts.replace(0, np.nan)
)
venue_analysis_df["past_month_outside_performance"] = (
    past_month_outside_total_performance /
    past_month_outside_attempts.replace(0, np.nan)
)

next_week_inside_total_performance = forward_rolling_sum(
    venue_analysis_df["total_performance_inside"],
    next_week_days
)
next_week_inside_attempts = forward_rolling_sum(
    venue_analysis_df["n_attempts_inside"],
    next_week_days
)
next_week_outside_total_performance = forward_rolling_sum(
    venue_analysis_df["total_performance_outside"],
    next_week_days
)
next_week_outside_attempts = forward_rolling_sum(
    venue_analysis_df["n_attempts_outside"],
    next_week_days
)

venue_analysis_df["next_week_inside_performance"] = (
    next_week_inside_total_performance /
    next_week_inside_attempts.replace(0, np.nan)
)
venue_analysis_df["next_week_outside_performance"] = (
    next_week_outside_total_performance /
    next_week_outside_attempts.replace(0, np.nan)
)

venue_predictor_specs = [
    (
        "past_month_inside_performance",
        "mean_performance_outside",
        "Past-month inside performance predicts outside performance"
    ),
    (
        "past_month_outside_performance",
        "mean_performance_inside",
        "Past-month outside performance predicts inside performance"
    )
]

next_week_venue_predictor_specs = [
    (
        "past_month_inside_performance",
        "next_week_outside_performance",
        "Past-month inside performance predicts next-week outside performance"
    ),
    (
        "past_month_outside_performance",
        "next_week_inside_performance",
        "Past-month outside performance predicts next-week inside performance"
    )
]

venue_test_results = pd.DataFrame([
    {
        **test_predictor(venue_analysis_df, predictor_col, outcome_col),
        "outcome": outcome_col,
        "label": label
    }
    for predictor_col, outcome_col, label in venue_predictor_specs
])

print("\nPast-month inside/outside performance cross-prediction")
print("Past-month performance is attempt-weighted over the previous 28 calendar days.")
print(
    venue_test_results[
        [
            "label",
            "n",
            "slope",
            "r_squared",
            "linear_p",
            "pearson_r",
            "pearson_p",
            "spearman_r",
            "spearman_p"
        ]
    ]
)

next_week_venue_test_results = pd.DataFrame([
    {
        **test_predictor(venue_analysis_df, predictor_col, outcome_col),
        "outcome": outcome_col,
        "label": label
    }
    for predictor_col, outcome_col, label in next_week_venue_predictor_specs
])

print("\nPast-month inside/outside performance predicts next-week performance")
print("Past-month performance is attempt-weighted over the previous 28 calendar days.")
print("Outcome is attempt-weighted over the next 7 calendar days.")
print(
    next_week_venue_test_results[
        [
            "label",
            "n",
            "slope",
            "r_squared",
            "linear_p",
            "pearson_r",
            "pearson_p",
            "spearman_r",
            "spearman_p"
        ]
    ]
)


# ---- plots ----
fig, axes = plt.subplots(3, 3, figsize=(16, 12))
axes = axes.ravel()
grade_color_min = analysis_df["daily_avg_attempt_vgrade"].min()
grade_color_max = analysis_df["daily_avg_attempt_vgrade"].max()
grade_norm = plt.Normalize(vmin=grade_color_min, vmax=grade_color_max)
grade_cmap = "viridis"
venue_markers = {
    "inside": "o",
    "outside": "^"
}
venue_marker_labels = {
    "inside": "mostly inside",
    "outside": "mostly outside"
}
grade_mappable = plt.cm.ScalarMappable(norm=grade_norm, cmap=grade_cmap)
grade_mappable.set_array([])

for ax, (predictor_col, label) in zip(axes, predictor_specs):
    plot_df = analysis_df[
        [
            predictor_col,
            "mean_performance",
            "daily_avg_attempt_vgrade",
            "daily_venue"
        ]
    ].dropna().copy()
    result = test_results.loc[test_results["predictor"] == predictor_col].iloc[0]

    x = plot_df[predictor_col].to_numpy(dtype=float)
    y = plot_df["mean_performance"].to_numpy(dtype=float)

    for venue, marker in venue_markers.items():
        venue_df = plot_df[plot_df["daily_venue"] == venue]
        ax.scatter(
            venue_df[predictor_col],
            venue_df["mean_performance"],
            c=venue_df["daily_avg_attempt_vgrade"],
            cmap=grade_cmap,
            norm=grade_norm,
            marker=marker,
            alpha=0.55,
            s=28,
            edgecolors="none",
            label=venue_marker_labels[venue]
        )

    if np.isfinite(result["slope"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        y_grid = result["intercept"] + result["slope"] * x_grid
        ax.plot(x_grid, y_grid, color="red", linewidth=2)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_xlabel(label)
    ax.set_ylabel(f"Daily mean performance [{unit_label}]")
    ax.set_title(
        f"R2={result['r_squared']:.3f}, "
        f"p={result['linear_p']:.3g}"
    )

for ax in axes[len(predictor_specs):]:
    ax.axis("off")

axes[0].legend(title="Today's venue", loc="best")
fig.colorbar(
    grade_mappable,
    ax=axes.tolist(),
    shrink=0.8,
    label="Today's average attempted V-grade"
)
fig.suptitle("Does prior-month volume/load predict daily performance?")
fig.tight_layout(rect=[0, 0, 0.93, 1])


fig, axes = plt.subplots(3, 3, figsize=(16, 12))
axes = axes.ravel()

for ax, (predictor_col, label) in zip(axes, predictor_specs):
    plot_df = calendar_analysis_df[
        [predictor_col, "next_week_mean_performance"]
    ].dropna().copy()
    result = next_week_test_results.loc[
        next_week_test_results["predictor"] == predictor_col
    ].iloc[0]

    x = plot_df[predictor_col].to_numpy(dtype=float)
    y = plot_df["next_week_mean_performance"].to_numpy(dtype=float)

    ax.scatter(x, y, alpha=0.45, s=24)

    if np.isfinite(result["slope"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        y_grid = result["intercept"] + result["slope"] * x_grid
        ax.plot(x_grid, y_grid, color="red", linewidth=2)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_xlabel(label)
    ax.set_ylabel(f"Next-7-day mean performance [{unit_label}]")
    ax.set_title(
        f"R2={result['r_squared']:.3f}, "
        f"p={result['linear_p']:.3g}"
    )

for ax in axes[len(predictor_specs):]:
    ax.axis("off")

fig.suptitle("Does prior-month volume/load predict next-7-day performance?")
fig.tight_layout()


fig, axes = plt.subplots(1, 2, figsize=(12, 5))

for ax, (test_df, predictor_col, outcome_col, label) in zip(
    axes,
    performance_momentum_specs
):
    plot_df = test_df[[predictor_col, outcome_col]].dropna().copy()
    result = performance_momentum_results.loc[
        performance_momentum_results["label"] == label
    ].iloc[0]

    x = plot_df[predictor_col].to_numpy(dtype=float)
    y = plot_df[outcome_col].to_numpy(dtype=float)

    ax.scatter(x, y, alpha=0.45, s=24)

    if np.isfinite(result["slope"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        y_grid = result["intercept"] + result["slope"] * x_grid
        ax.plot(x_grid, y_grid, color="red", linewidth=2)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.axvline(0, linestyle="--", linewidth=1)
    ax.set_xlabel(f"Past-28-day performance [{unit_label}]")
    ax.set_ylabel(f"Future performance [{unit_label}]")
    ax.set_title(
        f"{label}\n"
        f"R2={result['r_squared']:.3f}, p={result['linear_p']:.3g}"
    )

fig.suptitle("Performance momentum tests")
fig.tight_layout()


fig, axes = plt.subplots(2, 2, figsize=(13, 10))

multi_plot_specs = [
    (
        axes[0, 0],
        daily_multi_regression,
        "mean_performance",
        "Daily performance vs multivariable score"
    ),
    (
        axes[0, 1],
        weekly_multi_regression,
        "next_week_mean_performance",
        "Weekly performance vs multivariable score"
    )
]

for ax, result, outcome_col, title in multi_plot_specs:
    plot_df = result["data"].copy()
    y = plot_df[outcome_col].to_numpy(dtype=float)
    multivariable_score = result["predicted"] - result["intercept"]

    ax.scatter(multivariable_score, y, alpha=0.5, s=28)
    x_grid = np.linspace(multivariable_score.min(), multivariable_score.max(), 200)
    ax.plot(
        x_grid,
        result["intercept"] + x_grid,
        color="red",
        linewidth=2,
        label="multivariable fit"
    )
    ax.axhline(0, linestyle=":", linewidth=1)
    ax.axvline(0, linestyle=":", linewidth=1)
    ax.set_xlabel(f"Multivariable predictor score [{unit_label}]")
    ax.set_ylabel(f"Actual performance [{unit_label}]")
    ax.set_title(
        f"{title}\n"
        f"R2={result['r_squared']:.3f}, "
        f"adj R2={result['adj_r_squared']:.3f}, "
        f"model p={result['f_p']:.3g}"
    )
    ax.legend()

for ax, result, title in [
    (axes[1, 0], daily_multi_regression, "Daily standardized coefficients"),
    (axes[1, 1], weekly_multi_regression, "Weekly standardized coefficients")
]:
    coef_table = result["coef_table"]
    ax.bar(
        coef_table["predictor"],
        coef_table["standardized_coef"]
    )
    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_ylabel("Standardized coefficient")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)

fig.suptitle("Multivariable models: past-month predictors of performance")
fig.tight_layout()


fig, axes = plt.subplots(1, 2, figsize=(12, 5))

for ax, (test_df, predictor_col, outcome_col, label) in zip(
    axes,
    x50_performance_specs
):
    plot_df = test_df[[predictor_col, outcome_col]].dropna().copy()
    result = x50_performance_results.loc[
        x50_performance_results["label"] == label
    ].iloc[0]

    x = plot_df[predictor_col].to_numpy(dtype=float)
    y = plot_df[outcome_col].to_numpy(dtype=float)

    ax.scatter(x, y, alpha=0.45, s=24)

    if np.isfinite(result["slope"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        y_grid = result["intercept"] + result["slope"] * x_grid
        ax.plot(x_grid, y_grid, color="red", linewidth=2)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_xlabel(predictor_col)
    ax.set_ylabel(outcome_col)
    ax.set_title(
        f"{label}\n"
        f"R2={result['r_squared']:.3f}, p={result['linear_p']:.3g}"
    )

fig.suptitle("Rolling x50 and performance tests")
fig.tight_layout()


fig, ax = plt.subplots(figsize=(7, 5))
rng = np.random.default_rng(42)

ax.boxplot(
    [not_rested_performance, rested_performance],
    labels=["Climbed yesterday", "Rested yesterday"],
    showfliers=False
)
ax.scatter(
    rng.normal(1, 0.035, len(not_rested_performance)),
    not_rested_performance,
    alpha=0.25,
    s=18
)
ax.scatter(
    rng.normal(2, 0.035, len(rested_performance)),
    rested_performance,
    alpha=0.5,
    s=22
)
ax.axhline(0, linestyle="--", linewidth=1)
ax.set_ylabel(f"Today's mean performance [{unit_label}]")
ax.set_title(
    "Does resting yesterday predict today's performance?\n"
    f"diff={rested_performance.mean() - not_rested_performance.mean():.3f}, "
    f"t p={rest_ttest.pvalue:.3g}, MW p={rest_mann.pvalue:.3g}"
)
fig.tight_layout()


n_acwr_predictors = len(acwr_predictor_specs)
fig, axes = plt.subplots(
    2,
    n_acwr_predictors,
    figsize=(5 * n_acwr_predictors, 9),
    squeeze=False
)

for ax, (predictor_col, label) in zip(axes[0], acwr_predictor_specs):
    plot_df = calendar_analysis_df[
        [predictor_col, "next_day_mean_performance"]
    ].dropna().copy()
    result = next_day_acwr_results.loc[
        next_day_acwr_results["predictor"] == predictor_col
    ].iloc[0]

    x = plot_df[predictor_col].to_numpy(dtype=float)
    y = plot_df["next_day_mean_performance"].to_numpy(dtype=float)

    ax.scatter(x, y, alpha=0.45, s=24)

    if np.isfinite(result["slope"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        y_grid = result["intercept"] + result["slope"] * x_grid
        ax.plot(x_grid, y_grid, color="red", linewidth=2)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_xlabel(label)
    ax.set_ylabel(f"Next-day performance [{unit_label}]")
    ax.set_title(
        f"Next day: R2={result['r_squared']:.3f}, "
        f"p={result['linear_p']:.3g}"
    )

for ax, (predictor_col, label) in zip(axes[1], acwr_predictor_specs):
    plot_df = weekly_anchor_df[
        [predictor_col, "next_week_mean_performance"]
    ].dropna().copy()
    result = next_week_acwr_results.loc[
        next_week_acwr_results["predictor"] == predictor_col
    ].iloc[0]

    x = plot_df[predictor_col].to_numpy(dtype=float)
    y = plot_df["next_week_mean_performance"].to_numpy(dtype=float)

    ax.scatter(x, y, alpha=0.45, s=24)

    if np.isfinite(result["slope"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        y_grid = result["intercept"] + result["slope"] * x_grid
        ax.plot(x_grid, y_grid, color="red", linewidth=2)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.set_xlabel(label)
    ax.set_ylabel(f"Next-week performance [{unit_label}]")
    ax.set_title(
        f"Next week: R2={result['r_squared']:.3f}, "
        f"p={result['linear_p']:.3g}"
    )

fig.suptitle("Past-week ACWR predicting future performance")
fig.tight_layout()


fig, axes = plt.subplots(1, 2, figsize=(12, 5))
rng = np.random.default_rng(42)

for ax, (predictor_col, label) in zip(axes, outside_injury_specs):
    plot_df = analysis_df[[predictor_col, "injury"]].dropna().copy()
    injury_values = plot_df.loc[plot_df["injury"] == 1, predictor_col]
    non_injury_values = plot_df.loc[plot_df["injury"] == 0, predictor_col]
    result = outside_injury_results.loc[
        outside_injury_results["predictor"] == predictor_col
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
    ax.set_ylabel(label)
    ax.set_title(
        f"OR/SD={result['odds_ratio_per_sd']:.2f}, "
        f"logit p={result['logistic_lrt_p']:.3g}\n"
        f"MW p={result['mann_whitney_p']:.3g}, AUC={result['auc']:.2f}"
    )

fig.suptitle("Does outside climbing in the prior month predict injury?")
fig.tight_layout()


fig, axes = plt.subplots(1, 2, figsize=(12, 5))

for ax, (predictor_col, outcome_col, label) in zip(axes, venue_predictor_specs):
    plot_df = venue_analysis_df[[predictor_col, outcome_col]].dropna().copy()
    result = venue_test_results.loc[
        venue_test_results["predictor"] == predictor_col
    ].iloc[0]

    x = plot_df[predictor_col].to_numpy(dtype=float)
    y = plot_df[outcome_col].to_numpy(dtype=float)

    ax.scatter(x, y, alpha=0.45, s=24)

    if np.isfinite(result["slope"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        y_grid = result["intercept"] + result["slope"] * x_grid
        ax.plot(x_grid, y_grid, color="red", linewidth=2)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.axvline(0, linestyle="--", linewidth=1)
    ax.set_xlabel(f"Past-month predictor [{unit_label}]")
    ax.set_ylabel(f"Daily outcome performance [{unit_label}]")
    ax.set_title(
        f"{label}\n"
        f"R2={result['r_squared']:.3f}, p={result['linear_p']:.3g}"
    )

fig.suptitle("Inside/outside performance cross-prediction")
fig.tight_layout()


fig, axes = plt.subplots(1, 2, figsize=(12, 5))

for ax, (predictor_col, outcome_col, label) in zip(
    axes,
    next_week_venue_predictor_specs
):
    plot_df = venue_analysis_df[[predictor_col, outcome_col]].dropna().copy()
    result = next_week_venue_test_results.loc[
        next_week_venue_test_results["predictor"] == predictor_col
    ].iloc[0]

    x = plot_df[predictor_col].to_numpy(dtype=float)
    y = plot_df[outcome_col].to_numpy(dtype=float)

    ax.scatter(x, y, alpha=0.45, s=24)

    if np.isfinite(result["slope"]):
        x_grid = np.linspace(x.min(), x.max(), 200)
        y_grid = result["intercept"] + result["slope"] * x_grid
        ax.plot(x_grid, y_grid, color="red", linewidth=2)

    ax.axhline(0, linestyle="--", linewidth=1)
    ax.axvline(0, linestyle="--", linewidth=1)
    ax.set_xlabel(f"Past-month predictor [{unit_label}]")
    ax.set_ylabel(f"Next-7-day outcome performance [{unit_label}]")
    ax.set_title(
        f"{label}\n"
        f"R2={result['r_squared']:.3f}, p={result['linear_p']:.3g}"
    )

fig.suptitle("Inside/outside next-week performance cross-prediction")
fig.tight_layout()


fig, axes = plt.subplots(1, 2, figsize=(12, 5))

axes[0].bar(
    venue_test_results["label"],
    venue_test_results["slope"]
)
axes[0].axhline(0, linestyle="--", linewidth=1)
axes[0].set_ylabel("Slope")
axes[0].set_title("Cross-prediction slope")
axes[0].tick_params(axis="x", rotation=25)

venue_neg_log_p = -np.log10(venue_test_results["linear_p"])
axes[1].bar(
    venue_test_results["label"],
    venue_neg_log_p
)
axes[1].axhline(-np.log10(0.05), linestyle="--", linewidth=1, label="p = 0.05")
axes[1].set_ylabel("-log10(p-value)")
axes[1].set_title("Evidence against zero slope")
axes[1].tick_params(axis="x", rotation=25)
axes[1].legend()

fig.tight_layout()


fig, axes = plt.subplots(1, 2, figsize=(12, 5))

axes[0].bar(
    test_results["label"],
    test_results["slope"]
)
axes[0].axhline(0, linestyle="--", linewidth=1)
axes[0].set_ylabel(f"Slope [{unit_label} per V-grade]")
axes[0].set_title("Linear regression slope")
axes[0].tick_params(axis="x", rotation=30)

neg_log_p = -np.log10(test_results["linear_p"])
axes[1].bar(
    test_results["label"],
    neg_log_p
)
axes[1].axhline(-np.log10(0.05), linestyle="--", linewidth=1, label="p = 0.05")
axes[1].set_ylabel("-log10(p-value)")
axes[1].set_title("Evidence against zero slope")
axes[1].tick_params(axis="x", rotation=30)
axes[1].legend()

fig.tight_layout()

plt.show()
