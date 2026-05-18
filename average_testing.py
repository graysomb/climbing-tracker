import pandas as pd
import matplotlib.pyplot as plt

csv_path = "climb_data (4).csv"

df = pd.read_csv(csv_path)

df["time"] = pd.to_datetime(df["time"])
df["date"] = df["time"].dt.floor("D")

df = df[df["type"] == 0].copy()

df["tries"] = 1
df["score"] = df["tries"] * df["grade"]

daily = (
    df.groupby("date", as_index=False)
      .agg(
          daily_score=("score", "sum"),
          attempts=("tries", "sum")
      )
)

daily = daily.sort_values("date")
daily = daily.set_index("date").asfreq("D", fill_value=0)

# Past-only calendar-day moving averages
daily["ma_7"] = daily["daily_score"].shift(1).rolling(window=7, min_periods=1).mean()
daily["ma_30"] = daily["daily_score"].shift(1).rolling(window=30, min_periods=1).mean()
daily["ma_90"] = daily["daily_score"].shift(1).rolling(window=90, min_periods=1).mean()

plt.figure(figsize=(12, 6))

plt.plot(
    daily.index,
    daily["daily_score"],
    marker="o",
    linewidth=1,
    alpha=0.5,
    label="Daily score"
)

plt.plot(daily.index, daily["ma_7"], linewidth=2, label="Past-only 7-day MA")
plt.plot(daily.index, daily["ma_30"], linewidth=3, label="Past-only 30-day MA")
plt.plot(daily.index, daily["ma_90"], linewidth=3, label="Past-only 90-day MA")

plt.xlabel("Date")
plt.ylabel("Score = attempts × grade")
plt.title("Climbing score per calendar day with past-only moving averages")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()