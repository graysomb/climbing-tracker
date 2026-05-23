# ACWR Notes

## V-point ACWR calculations

Both V-point ACWR metrics use attempted V-points, not sent V-points.

### Total V-points ACWR

Daily total V-points is the sum of the V-grade for every attempt on that day:

```text
daily_total_vpoints = sum(grade for all attempts that day)
```

The ACWR is then:

```text
acute_total_vpoints = sum(daily_total_vpoints over trailing 7 calendar days)
chronic_total_vpoints = sum(daily_total_vpoints over trailing 28 calendar days)

total_vpoints_acwr = acute_total_vpoints / chronic_total_vpoints
```

For injury plots, the value used is the maximum total V-points ACWR in the 7 days ending on the injury date.

Across injury dates with enough prior data:

```text
n = 14
mean max prior-7-day total V-points ACWR = 0.5084
sample variance = 0.0603
```

### Average V-points ACWR

Daily average V-points is the mean attempted V-grade for that day:

```text
daily_avg_vpoints = sum(grade for all attempts that day) / number of attempts that day
```

Rest days are treated as 0 before the rolling windows are calculated.

The ACWR is then:

```text
acute_avg_vpoints = mean(daily_avg_vpoints over trailing 7 calendar days)
chronic_avg_vpoints = mean(daily_avg_vpoints over trailing 28 calendar days)

avg_vpoints_acwr = acute_avg_vpoints / chronic_avg_vpoints
```

For injury plots, the value used is the maximum average V-points ACWR in the 7 days ending on the injury date.

Across injury dates with enough prior data:

```text
n = 14
mean max prior-7-day average V-points ACWR = 1.9742
sample variance = 1.0113
```
