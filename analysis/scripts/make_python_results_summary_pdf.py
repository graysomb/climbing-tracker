from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
PLOTS_DIR = ROOT / "outputs" / "plots"
WORK_DIR = ROOT / "outputs" / "report_working"
OUT_DIR = ROOT / "outputs" / "reports"
OUT_PDF = OUT_DIR / "climbing_model_results_summary.pdf"


class HR(Flowable):
    def __init__(self, width, color=colors.HexColor("#9AA3AF")):
        super().__init__()
        self.width = width
        self.color = color
        self.height = 0.08 * inch

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(0.8)
        self.canv.line(0, self.height / 2, self.width, self.height / 2)


def styles():
    base = getSampleStyleSheet()
    base["Title"].fontName = "Helvetica-Bold"
    base["Title"].fontSize = 23
    base["Title"].leading = 28
    base["Title"].textColor = colors.HexColor("#1F2937")
    base["Title"].alignment = TA_CENTER

    base["Heading1"].fontName = "Helvetica-Bold"
    base["Heading1"].fontSize = 15
    base["Heading1"].leading = 19
    base["Heading1"].spaceBefore = 14
    base["Heading1"].spaceAfter = 7
    base["Heading1"].textColor = colors.HexColor("#1F2937")

    base["Heading2"].fontName = "Helvetica-Bold"
    base["Heading2"].fontSize = 11.5
    base["Heading2"].leading = 15
    base["Heading2"].spaceBefore = 9
    base["Heading2"].spaceAfter = 5
    base["Heading2"].textColor = colors.HexColor("#374151")

    base["BodyText"].fontName = "Helvetica"
    base["BodyText"].fontSize = 9.5
    base["BodyText"].leading = 13.5
    base["BodyText"].spaceAfter = 6
    base["BodyText"].alignment = TA_LEFT

    base.add(
        ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#4B5563"),
        )
    )
    base.add(
        ParagraphStyle(
            "Compact",
            parent=base["BodyText"],
            fontSize=8.7,
            leading=11.2,
            spaceAfter=4,
        )
    )
    base.add(
        ParagraphStyle(
            "Caption",
            parent=base["Small"],
            fontName="Helvetica-Oblique",
            spaceBefore=2,
            spaceAfter=8,
        )
    )
    base.add(
        ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            backColor=colors.HexColor("#EEF6F3"),
            borderColor=colors.HexColor("#5A9A82"),
            borderWidth=0.8,
            borderPadding=8,
            leading=13.5,
            spaceBefore=7,
            spaceAfter=9,
        )
    )
    return base


S = styles()


def para(text, style="BodyText"):
    return Paragraph(text, S[style])


def bullets(items, style="BodyText"):
    return ListFlowable(
        [
            ListItem(para(item, style), leftIndent=8, bulletColor=colors.HexColor("#374151"))
            for item in items
        ],
        bulletType="bullet",
        leftIndent=14,
        bulletFontName="Helvetica",
        bulletFontSize=7,
        bulletOffsetY=2,
        spaceAfter=6,
    )


def image_block(rel_path, caption, max_width=6.7 * inch, max_height=3.5 * inch):
    path = Path(rel_path)
    if not path.is_absolute():
        path = PLOTS_DIR / path
    if not path.exists():
        return [para(f"Missing expected figure: {rel_path}", "Small")]

    img = Image(str(path))
    scale = min(max_width / img.imageWidth, max_height / img.imageHeight)
    img.drawWidth = img.imageWidth * scale
    img.drawHeight = img.imageHeight * scale
    return KeepTogether([img, para(caption, "Caption")])


def crop_figure(rel_path, output_name, box):
    source = PLOTS_DIR / rel_path
    output = WORK_DIR / "report_assets" / output_name
    output.parent.mkdir(parents=True, exist_ok=True)
    with PILImage.open(source) as img:
        img.crop(box).save(output)
    return output


def table(data, col_widths=None):
    wrapped = []
    for row_idx, row in enumerate(data):
        style = S["Small"]
        if row_idx == 0:
            style = ParagraphStyle(
                f"TableHeader{len(data)}",
                parent=S["Small"],
                fontName="Helvetica-Bold",
                textColor=colors.HexColor("#111827"),
            )
        wrapped.append([Paragraph(str(cell), style) for cell in row])

    t = Table(wrapped, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(7.5 * inch, 0.45 * inch, f"Page {doc.page}")
    canvas.drawString(0.75 * inch, 0.45 * inch, "Climbing model results summary")
    canvas.restoreState()


def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failure_volume_panel = crop_figure(
        "model4_fail/01_does_prior_month_volume_load_predict_daily_surprise_fail.png",
        "failure_attempted_vgrade_total.png",
        (50, 35, 1000, 800),
    )
    send_duration_panel = crop_figure(
        "model4_send/01_does_prior_month_volume_load_predict_daily_surprise_send.png",
        "send_average_session_duration.png",
        (50, 1580, 1000, 2350),
    )
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=letter,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.7 * inch,
        title="Climbing Model Results Summary",
    )

    story = []
    content_width = letter[0] - doc.leftMargin - doc.rightMargin

    story.append(para("Climbing Model Results Summary", "Title"))
    story.append(para("Evidence-focused edition: send probability, session behavior, performance, workload, ACWR, and injury results from model2.py, model3.py, model4.py, model4_send.py, and model4_fail.py.", "Small"))
    story.append(Spacer(1, 0.08 * inch))
    story.append(HR(content_width))
    story.append(para("<b>Plain-language bottom line:</b> Indoor and outdoor climbing differ in grade difficulty, session progression, and pacing. Short post-failure rests do not show a send-probability benefit, and the chance of reaching the next send falls sharply as more attempts accumulate. Previous performance remains the clearest performance predictor, while ACWR is more useful for injury risk than performance.", "Callout"))

    story.append(para("What The Models Measure", "Heading1"))
    story.append(bullets([
        "<b>Send probability prior:</b> model2.py and model3.py fit separate logistic send-probability curves by grade for inside and outside climbing. This becomes the prior used to decide how surprising each send or fail was.",
        "<b>Surprise send:</b> for a send, surprise is -log(expected send probability). Harder-than-expected sends score higher.",
        "<b>Surprise fail:</b> for a fail, surprise is -log(expected fail probability). Unexpected failures score higher as failure surprise.",
        "<b>Performance:</b> performance = surprise_send - surprise_fail. Positive days contain more unexpectedly good sends; negative days contain more unexpectedly bad failures.",
        "<b>Load:</b> many models use surprise_send + surprise_fail or related V-point/session-duration totals as workload.",
        "<b>ACWR:</b> acute:chronic workload ratio. In the current injury tests, the acute window is usually the last week and the chronic baseline is roughly the prior month, depending on the specific plot.",
    ], style="Compact"))
    story.append(PageBreak())
    story.append(para("Executive Findings", "Heading1"))
    story.append(bullets([
        "<b>Send probability is logistic by grade, and inside climbing is softer (Figure 1).</b> The indoor fitted curve sits roughly one V-grade to the right of the outdoor curve, so the same nominal grade has a higher fitted send probability inside.",
        "<b>Session progression differs by venue (Figure M2-1).</b> Model 2 posterior surprisal generally rises through indoor sessions and falls through outdoor sessions. This is consistent with the signed-performance analysis tending downward inside and upward outside, although surprisal itself is unsigned.",
        "<b>Outdoor attempt intervals are longer (Figure M2-2).</b> The outside interval distribution is shifted toward longer rests than the inside distribution.",
        "<b>Waiting less than about 10-11 minutes after a failure does not improve send probability (Figure M2-3).</b> The short-rest bins show no clear upward relationship between rest duration and the next-attempt send rate.",
        "<b>The first post-send attempt is the most favorable, and probability declines with more attempts (Figures M2-4 to M2-7).</b> The decline survives grade control and is visually clearer inside and at lower grades. Flash probability also falls at higher grades.",
        "<b>Performance mostly predicts performance (Figures 2-3).</b> Previous performance is the strongest variable in the daily multivariable model and remains important in the weekly model. Attempted V-grade volume contributes to the weekly model, but the total explained variance remains modest.",
        "<b>Resting yesterday does not improve performance today (Figure 4).</b> Rested-yesterday days were lower by 0.167 nats on average in this sample. This does not mean rest is harmful; rest-day selection and accumulated fatigue are confounders.",
        "<b>ACWR is more useful as an injury marker than a performance strategy (Figures 5-7).</b> Several load-based ACWR definitions are elevated on injury dates, while none of the tested ACWR measures significantly predict better next-day or next-week performance.",
        "<b>High ACWR is not the same as certain injury (Figure 6).</b> Injury dates tend to have higher ACWR, but injuries are rare and the groups overlap. Even at high observed V-point ACWR, fitted absolute injury probability remains well below 50%.",
        "<b>Failure has momentum (Figure 8).</b> Prior-28-day failure surprise predicts both next-day and next-week failure surprise, although most outcome variance remains unexplained.",
        "<b>Attempted V-grade volume is associated with less failure (Figure 9).</b> Past-month attempted V-grade total has a small negative association with daily failure surprise; average attempted grade does not show the same effect.",
        "<b>Longer sessions are weakly associated with more sending, but sends have little momentum (Figures 10-11).</b> Session duration has a small positive daily association with send surprise, while prior send surprise does not predict next-day or next-week send surprise.",
    ], style="Compact"))

    story.append(PageBreak())
    story.append(para("Evidence 1: Send Probability By Grade And Venue", "Heading1"))
    story.append(para("Both model2.py and model3.py fit separate logistic curves for inside and outside attempts. Send probability declines as grade rises, and the indoor curve is shifted roughly one V-grade to the right. In practical terms, an indoor grade has a higher fitted send probability than the same nominal outdoor grade in this dataset.", "BodyText"))
    story.append(image_block("model3/01_send_probability_by_grade.png", "Figure 1. Fitted send probability by V-grade for inside and outside climbing. Model 2 and Model 3 export the same figure; their PNG outputs are byte-for-byte identical.", max_height=5.2 * inch))
    story.append(para("This venue-specific fit is the prior behind surprise_send, surprise_fail, performance, and information-load calculations. It prevents the later models from treating an indoor and outdoor attempt at the same nominal grade as equally difficult.", "Small"))

    story.append(PageBreak())
    story.append(para("Model 2 Evidence: Session Progression And Pacing", "Heading1"))
    story.append(para("The venue split extends beyond grade difficulty. Model 2's sequential-posterior surprisal generally rises over normalized indoor session time and falls outdoors. Because surprisal is unsigned, this plot describes predictability rather than good-minus-bad performance directly; its venue direction is consistent with the signed-performance session analysis.", "BodyText"))
    story.append(image_block("model2/17_sequentially_updated_surprise_vs_duration_normalized_session_time.png", "Figure M2-1. Sequentially updated posterior surprisal across duration-normalized session time. Indoor surprisal rises while outdoor surprisal generally falls.", max_height=3.1 * inch))
    story.append(para("Attempt pacing also differs strongly by venue. Indoor attempts cluster at shorter intervals, while the main outdoor distribution is shifted toward longer waits. The distant peaks reflect breaks between sessions or climbing days rather than ordinary between-try rest.", "BodyText"))
    story.append(image_block("model2/22_intervals_between_consecutive_attempts_split_by_inside_outside.png", "Figure M2-2. Consecutive-attempt intervals on a log scale. The outdoor distribution is shifted to the right of the indoor distribution.", max_height=3.05 * inch))

    story.append(PageBreak())
    story.append(para("Model 2 Evidence: Rest After A Failure", "Heading1"))
    story.append(para("For attempts immediately following a failure, there is no clear monotonic benefit from waiting longer within the short-rest region. In particular, waits below approximately 10-11 minutes do not show increasing send probability. The wider error bars in sparse bins make this a pattern-level conclusion rather than a precise optimal-rest estimate.", "BodyText"))
    story.append(image_block("model2/26_after_a_fail_does_longer_rest_predict_sends_intervals_400_min.png", "Figure M2-3. Next-attempt send probability after a failure versus rest interval. The dashed lines mark 10 minutes and one hour.", max_height=5.2 * inch))

    story.append(PageBreak())
    story.append(para("Model 2 Evidence: Attempts Until The Next Send", "Heading1"))
    story.append(para("Most completed send-to-send cycles contain very few attempts, and long cycles become progressively rarer. The grade-controlled distribution shows the same basic decline, so the result is not explained only by easier grades being sent more often.", "BodyText"))
    story.append(image_block("model2/29_attempts_until_next_send.png", "Figure M2-4. Raw count distribution of logged attempts until the next send, shown on log-log axes.", max_height=2.8 * inch))
    story.append(image_block("model2/31_attempts_until_next_send_controlling_for_grade_equal_weight_average_over_target_.png", "Figure M2-5. Grade-controlled probability of the next send occurring after a given number of attempts. The probability falls sharply after the first attempt.", max_height=3.25 * inch))

    story.append(PageBreak())
    story.append(para("Attempts By Venue And Grade", "Heading2"))
    story.append(para("Splitting the cycles by venue and target grade shows that the decline is visually clearest for indoor climbing and lower grades. This figure is descriptive: it does not provide a formal interaction-test p-value, and later-attempt points can be based on fewer completed cycles.", "BodyText"))
    story.append(image_block("model2/33_inside_attempts_until_next_send_by_target_grade.png", "Figure M2-6. Attempts until the next send, split by inside/outside venue and target send grade. First-attempt probability is highest across most grade curves.", max_height=4.6 * inch))
    story.append(para("The code labels a cycle as a flash when the next send occurs on the first logged attempt after the previous send (trials_to_send == 1). Under that operational definition, flash probability is high at lower grades and declines substantially at the highest grades.", "BodyText"))
    story.append(image_block("model2/34_flash_probability_by_grade.png", "Figure M2-7. Flash probability by target send grade, using Model 2's send-to-send-cycle definition.", max_height=2.6 * inch))

    story.append(PageBreak())
    story.append(para("Evidence 2: Performance Predicts Performance", "Heading1"))
    story.append(para("The momentum tests are statistically significant but modest: past-28-day performance explains 3.1% of next-day variance and 7.6% of next-week variance. The multivariable model confirms that previous performance is the largest standardized daily coefficient; weekly attempted V-grade volume also contributes.", "BodyText"))
    story.append(image_block("model4/03_performance_momentum_tests.png", "Figure 2. Past-28-day performance versus next-day and next-week performance. Both slopes are positive (p=0.00471 and p=0.00611), but R2 remains low.", max_height=3.25 * inch))
    story.append(image_block("model4/05_multivariable_models_past_month_predictors_of_performance.png", "Figure 3. Combined attempted V-grade total, average session duration, and prior performance. The daily model explains 4.0% of variance; the weekly model explains 11.8%.", max_height=3.45 * inch))

    story.append(PageBreak())
    story.append(para("Evidence 3: Resting Yesterday", "Heading1"))
    story.append(para("The rested-yesterday group performed 0.167 nats lower on average, with significant t-test and Mann-Whitney results. This directly rejects a simple same-day performance boost in this dataset. It does not establish that rest causes worse performance, because rest may be chosen after hard training or when already fatigued.", "BodyText"))
    story.append(image_block("model4/07_does_resting_yesterday_predict_today_s_performance_diff_0_167_t_p_0_000257_mw_p_.png", "Figure 4. Today's mean performance after climbing versus resting yesterday. The observed difference is negative, not positive.", max_height=5.7 * inch))

    story.append(PageBreak())
    story.append(para("Evidence 4: ACWR, Injury, And Performance", "Heading1"))
    story.append(para("The injury-date comparison is strongest for send-surprise ACWR, total and average V-point ACWR, and several information-load ACWR definitions. Session-duration, performance, and failure-surprise ACWR are not significant in this figure, so the conclusion is 'several ACWR measures predict injury,' not 'every ACWR measure does.'", "BodyText"))
    story.append(image_block("model3/35_max_prior_week_acwr_on_injury_dates_vs_non_injury_days.png", "Figure 5. Maximum prior-week ACWR on injury dates versus non-injury days. Red crosses are injury dates; each panel reports Mann-Whitney p, logistic p, and AUC.", max_height=6.1 * inch))

    story.append(PageBreak())
    story.append(para("ACWR Raises Risk But Does Not Guarantee Injury", "Heading2"))
    story.append(para("The V-point models use attempted V-points. Total V-point ACWR is trailing 7-day total divided by trailing 28-day total. Average V-point ACWR compares the analogous rolling daily-average grade measures. With only 14 injuries among 738 modeled days, absolute fitted risk stays low even when relative risk rises.", "BodyText"))
    story.append(image_block("model3/36_estimated_injury_probability_from_v_point_acwr.png", "Figure 6. Estimated injury probability from maximum prior-7-day total and average V-point ACWR. The rising red curves support increased risk; their low absolute height shows why high ACWR also creates many false positives.", max_height=4.25 * inch))
    story.append(para("Across injury dates with enough history, maximum prior-7-day total V-point ACWR had mean 0.5084 and sample variance 0.0603. Average V-point ACWR had mean 1.9742 and sample variance 1.0113.", "Small"))

    story.append(PageBreak())
    story.append(para("ACWR Does Not Predict Better Performance", "Heading2"))
    story.append(para("Across total load, mean load, send surprise, total V-points, and average V-points, no next-day or next-week relationship is statistically significant. Several weekly slopes are slightly negative. This is the direct evidence behind treating ACWR as a risk monitor rather than a performance target.", "BodyText"))
    story.append(image_block("model4/08_past_week_acwr_predicting_future_performance.png", "Figure 7. Past-week ACWR versus next-day and next-week performance. All displayed p-values are non-significant, and explained variance is near zero.", max_height=5.35 * inch))

    story.append(PageBreak())
    story.append(para("Evidence 5: Failure Momentum And Volume", "Heading1"))
    story.append(para("Failure surprise has measurable momentum: prior-28-day failure surprise explains 5.4% of next-day and 10.9% of next-week failure surprise. This may contain mental state, fatigue, tactics, conditions, route selection, or persistent project difficulty.", "BodyText"))
    story.append(image_block("model4_fail/03_surprise_fail_momentum_tests.png", "Figure 8. Failure-surprise momentum. Both next-day and next-week slopes are positive and statistically significant.", max_height=3.45 * inch))
    story.append(para("Past-month attempted V-grade total is negatively associated with daily failure surprise (R2=0.027, p=0.00925). The average attempted grade panel is non-significant, so the evidence points to total attempted volume rather than simply trying harder grades.", "BodyText"))
    story.append(image_block(failure_volume_panel, "Figure 9. Past-month attempted V-grade total versus daily failure surprise (R2=0.027, p=0.00925). The fitted association is negative.", max_height=3.5 * inch))

    story.append(PageBreak())
    story.append(para("Evidence 6: Session Duration And Sending", "Heading1"))
    story.append(para("Past-month average session duration has a small positive association with daily send surprise (R2=0.017, p=0.040). That is a weak association, and it may reflect more opportunities, warmup, project selection, or session intent rather than a causal benefit from extending every session.", "BodyText"))
    story.append(image_block(send_duration_panel, "Figure 10. Past-month average session duration versus daily send surprise (R2=0.017, p=0.040). The fitted association is positive but weak.", max_height=3.75 * inch))
    story.append(para("Recent send surprise itself has no detectable momentum: next-day p=0.879 and next-week p=0.777. This contrasts sharply with failure surprise.", "BodyText"))
    story.append(image_block("model4_send/03_surprise_send_momentum_tests.png", "Figure 11. Send-surprise momentum tests. Both fitted lines are essentially flat and non-significant.", max_height=3.2 * inch))

    story.append(PageBreak())
    story.append(para("Interpretation And Practical Use", "Heading1"))
    story.append(para("The cleanest practical split is between session behavior, performance metrics, and injury-risk metrics. Outdoor attempts naturally use longer intervals, and the data do not support treating sub-11-minute post-failure rests as a send-probability booster. Performance is mostly about ability, task selection, confidence, tactics, and immediate state. ACWR is mostly about load-spike risk.", "BodyText"))
    story.append(table([
        ["Question", "Current answer", "Practical interpretation"],
        ["Does venue affect grade difficulty?", "Yes; indoor send probability is about one V-grade softer.", "Use venue-specific probability fits."],
        ["Does ACWR predict injury?", "Yes for several, but not all, load definitions.", "Track it as a risk marker, not a diagnosis."],
        ["Does ACWR predict better performance?", "No useful positive signal; sometimes slightly negative.", "Do not chase high ACWR."],
        ["Does rest yesterday improve performance?", "No; rested-yesterday days were lower in this sample.", "Do not interpret this observational result as proof rest is harmful."],
        ["Does failure carry forward?", "Yes, more than send momentum.", "Watch confidence, tactics, conditions, and fatigue after bad sessions."],
        ["Does volume help?", "Somewhat; especially reducing failure.", "Volume may stabilize performance rather than create big spikes."],
        ["Does longer session time help?", "Associated with more sends.", "Could reflect more opportunities/warmup, not guaranteed benefit."],
    ], col_widths=[1.7 * inch, 2.2 * inch, 2.4 * inch]))

    story.append(para("Limitations", "Heading1"))
    story.append(bullets([
        "Most tests are observational. They show prediction or association, not clean causality.",
        "All predictor windows precede their outcomes, so next-day and next-week data are not included in their own predictors.",
        "The data mixes indoor and outdoor climbing, different route styles, different intentions, and different conditions.",
        "Model 2's session-phase plot is unsigned surprisal, not signed performance. It supports a venue difference in session progression but does not independently establish whether an outcome is good or bad.",
        "Attempts-until-next-send counts logged attempts between consecutive sends, not attempts on one specific climb. Its 'flash' label means the next send occurred on the first logged attempt after the previous send.",
        "The venue-and-grade attempt curves are descriptive. Later-attempt bins can be sparse, and no formal interaction test establishes that the decline is statistically stronger inside or at lower grades.",
        "Performance and x50 are strongly related by construction, because both are derived from send probability versus grade.",
        "Some p-values can become very small when a variable is definitionally close to the outcome or when many attempts make the sample size large.",
        "Injury dates are sparse (14 injury dates in the displayed V-point model), so high false-positive risk is unavoidable at the observed base rate.",
        "Many hypotheses were tested. P-values should be read with effect size, R2/AUC, direction, and out-of-sample validation rather than used alone.",
    ], style="Compact"))

    story.append(para("Overall Conclusion", "Heading1"))
    story.append(para("Use venue-specific send-probability fits and expect longer rests outdoors. Do not assume a sub-11-minute rest after failure improves the next attempt, and recognize that send likelihood falls sharply as attempts accumulate. Track ACWR to avoid load spikes; do not chase high ACWR. Previous performance remains the clearest performance signal.", "Callout"))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(OUT_PDF)


if __name__ == "__main__":
    build()
