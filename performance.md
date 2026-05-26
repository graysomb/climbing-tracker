# Performance

`model4.py` defines performance from how surprising each attempt was relative to the fitted send-probability curve.

## Expected send probability

First, the script fits a logistic model of send probability by grade:

```text
p_send_expected = 1 / (1 + exp((grade - x50) / scale))
```

When `group_by_outside = True`, separate curves are fit for inside and outside climbs. Each attempt uses the matching inside/outside curve.

The expected failure probability is:

```text
p_fail_expected = 1 - p_send_expected
```

Probabilities are clipped away from 0 and 1 to avoid taking `log(0)`.

## Surprise values

For a send:

```text
surprise_send = -log(p_send_expected)
surprise_fail = 0
```

For a fail:

```text
surprise_send = 0
surprise_fail = -log(p_fail_expected)
```

With the current `model4.py` settings, `log_base = "e"`, so these values are in nats. If `log_base` is changed to `"2"`, they are in bits.

## Performance

Attempt-level performance is:

```text
performance = surprise_send - surprise_fail
```

So:

```text
send performance = -log(p_send_expected)
fail performance = log(p_fail_expected)
```

This makes unexpectedly hard sends strongly positive, easy sends mildly positive, expected failures mildly negative, and surprising failures strongly negative.

Daily performance is usually calculated as the mean attempt-level performance for that day:

```text
daily_mean_performance = mean(performance for all attempts that day)
```

Weekly and future-performance tests use attempt-weighted averages, which means summed performance divided by the number of attempts in the relevant window.
