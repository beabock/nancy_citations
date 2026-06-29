# plot_mycorrhiz_trends.R
#
# Plots the proportion of citing papers mentioning "mycorrhiz*" over time,
# for (1) the Johnson et al. 1997 paper and (2) Nancy Johnson's full corpus.
# Saves two separate PNG files.
#
# Required packages:
#   install.packages(c("tidyverse", "scales"))

library(tidyverse)
library(scales)

# ---------------------------------------------------------------------------
# 0. Paths — set this to wherever your CSVs live
# ---------------------------------------------------------------------------

dir_path <- "C:/Users/beabo/OneDrive - Northern Arizona University/NAU/nancy_citations"

csv_1997   <- file.path(dir_path, "mycorrhiz_citation_results.csv")
csv_full   <- file.path(dir_path, "nancy_johnson_citation_results.csv")
out_1997   <- file.path(dir_path, "plot_citations_1997paper.png")
out_full   <- file.path(dir_path, "plot_citations_fullcorpus.png")

# ---------------------------------------------------------------------------
# 1. Colors & theme
#    Wes Anderson "Darjeeling1"-inspired, colorblind-safe:
#      teal  = classifiable match  (safe for deuteranopia/protanopia)
#      amber = classifiable no-match
#      sand  = no abstract / uncertain
# ---------------------------------------------------------------------------

pal <- c(
  "Mentions mycorrhiz*"             = "#00A08A",  # teal  (Darjeeling1)
  "No mention (abstract available)" = "#F2AD00",  # amber (Darjeeling1)
  "No abstract (uncertain)"         = "#D6C9A8"   # warm sand / parchment
)

# Force legend order
cat_levels <- c(
  "Mentions mycorrhiz*",
  "No mention (abstract available)",
  "No abstract (uncertain)"
)

base_theme <- theme_bw(base_size = 12) +
  theme(
    legend.position   = "bottom",
    legend.title      = element_blank(),
    legend.key.size   = unit(0.8, "lines"),
    panel.grid.minor  = element_blank(),
    plot.title        = element_text(face = "bold", size = 13),
    plot.subtitle     = element_text(size = 10, color = "grey45"),
    plot.caption      = element_text(size = 8, color = "grey55", hjust = 0),
    axis.text         = element_text(size = 10)
  )

# ---------------------------------------------------------------------------
# 2. Helper: build annual summary from a cleaned data frame
# ---------------------------------------------------------------------------

make_annual <- function(df) {
  df |>
    count(year, category) |>
    group_by(year) |>
    mutate(
      pct   = n / sum(n),
      total = sum(n)
    ) |>
    ungroup() |>
    mutate(category = factor(category, levels = cat_levels))
}

make_trend <- function(df) {
  df |>
    filter(category != "No abstract (uncertain)") |>
    group_by(year) |>
    summarise(
      n_classifiable = n(),
      n_match        = sum(mycorrhiz_anywhere == TRUE),
      pct_match      = n_match / n_classifiable,
      .groups        = "drop"
    )
}

# ---------------------------------------------------------------------------
# 3. Load & prep the 1997-paper dataset
# ---------------------------------------------------------------------------

d1997 <- read_csv(csv_1997, show_col_types = FALSE) |>
  filter(!is.na(year), year >= 1998, year <= 2025) |>
  mutate(
    mycorrhiz_anywhere = as.logical(mycorrhiz_anywhere),
    category = case_when(
      mycorrhiz_anywhere              ~ "Mentions mycorrhiz*",
      abstract != "" & !is.na(abstract) ~ "No mention (abstract available)",
      TRUE                            ~ "No abstract (uncertain)"
    )
  )

annual_1997 <- make_annual(d1997)
trend_1997  <- make_trend(d1997)

# ---------------------------------------------------------------------------
# 4. Load & prep the full-corpus dataset (deduplicate by citing paper)
# ---------------------------------------------------------------------------

dfull <- read_csv(csv_full, show_col_types = FALSE) |>
  group_by(citing_openalex_id) |>
  slice_head(n = 1) |>
  ungroup() |>
  rename(year = citing_year) |>
  filter(!is.na(year), year >= 1997, year <= 2025) |>
  mutate(
    mycorrhiz_anywhere = as.logical(mycorrhiz_anywhere),
    category = case_when(
      mycorrhiz_anywhere                ~ "Mentions mycorrhiz*",
      abstract != "" & !is.na(abstract) ~ "No mention (abstract available)",
      TRUE                              ~ "No abstract (uncertain)"
    )
  )

annual_full <- make_annual(dfull)
trend_full  <- make_trend(dfull)

# ---------------------------------------------------------------------------
# 5. Plot 1: Johnson et al. 1997 paper
# ---------------------------------------------------------------------------

p1997 <- ggplot(annual_1997, aes(x = year, y = pct, fill = category)) +
  geom_col(width = 0.8, colour = NA) +
  geom_smooth(
    data        = trend_1997,
    aes(x = year, y = pct_match),
    inherit.aes = FALSE,
    method      = "lm",
    span        = 0.6,
    colour      = "#005f56",
    linewidth   = 1.1,
    se          = TRUE,
    fill        = "#00A08A",
    alpha       = 0.15
  ) +
  scale_fill_manual(values = pal, drop = FALSE) +
  scale_y_continuous(
    labels = percent_format(accuracy = 1),
    expand = c(0, 0),
    limits = c(0, 1.02)
  ) +
  scale_x_continuous(breaks = seq(1998, 2025, by = 3)) +
  labs(
    title    = "Citations to Johnson, Graham & Smith (1997)",
    subtitle = "Proportion of citing papers mentioning mycorrhiz* by year\nTrend line (lm) fitted to classifiable papers only (excludes grey bars)",
    x        = "Year of citing paper",
    y        = "Proportion of citing papers",
    caption  = "Source: OpenAlex. Papers without title/abstract/keywords excluded from trend line."
  ) +
  base_theme

ggsave(out_1997, p1997, width = 10, height = 5.5, dpi = 300)
message("Saved: ", out_1997)

# ---------------------------------------------------------------------------
# 6. Plot 2: Full corpus (unique citing papers, deduplicated)
# ---------------------------------------------------------------------------

pfull <- ggplot(annual_full, aes(x = year, y = pct, fill = category)) +
  geom_col(width = 0.8, colour = NA) +
  geom_smooth(
    data        = trend_full,
    aes(x = year, y = pct_match),
    inherit.aes = FALSE,
    method      = "lm",
    span        = 0.4,
    colour      = "#005f56",
    linewidth   = 1.1,
    se          = TRUE,
    fill        = "#00A08A",
    alpha       = 0.15
  ) +
  scale_fill_manual(values = pal, drop = FALSE) +
  scale_y_continuous(
    labels = percent_format(accuracy = 1),
    expand = c(0, 0),
    limits = c(0, 1.02)
  ) +
  scale_x_continuous(breaks = seq(1997, 2025, by = 3)) +
  labs(
    title    = "Citations to Nancy Collins Johnson's full body of work",
    subtitle = "Papers citing multiple of her works counted only once per year\nTrend line (lm) fitted to classifiable papers only (excludes grey bars)",
    x        = "Year of citing paper",
    y        = "Proportion of citing papers",
    caption  = "Source: OpenAlex. Papers without title/abstract/keywords excluded from trend line."
  ) +
  base_theme

ggsave(out_full, pfull, width = 10, height = 5.5, dpi = 300)
message("Saved: ", out_full)

# ---------------------------------------------------------------------------
# 7. Significance testing
#
#    PRIMARY: logistic regression on individual papers (binary outcome).
#      Each paper is a data point; year is the predictor.
#      This is more rigorous than regressing annual proportions because it
#      uses all observations, properly models the 0/1 outcome, and doesn't
#      assume proportions are normally distributed.
#      Only classifiable papers (those with abstracts or title/keyword matches)
#      are included, same as the trend line.
#
#    SECONDARY: weighted linear regression on annual proportions.
#      Weighted by n_classifiable per year. Matches what geom_smooth(method="lm")
#      shows in the plots, so coefficients can be read directly off the figure.
# ---------------------------------------------------------------------------

report_significance <- function(paper_df, trend_df, label) {

  cat(sprintf("\n======================================================\n"))
  cat(sprintf("  %s\n", label))
  cat(sprintf("======================================================\n"))

  # --- PRIMARY: logistic regression on individual papers ---
  classifiable <- paper_df |>
    filter(category != "No abstract (uncertain)") |>
    mutate(match = as.integer(mycorrhiz_anywhere == TRUE))

  glm_fit <- glm(match ~ year, data = classifiable, family = binomial)
  glm_s   <- summary(glm_fit)
  glm_cf  <- coef(glm_s)

  log_or      <- glm_cf["year", "Estimate"]   # log-odds ratio per year
  or_per_year <- exp(log_or)                   # odds ratio per year
  or_per_dec  <- exp(log_or * 10)              # odds ratio per decade
  glm_p       <- glm_cf["year", "Pr(>|z|)"]
  n_papers    <- nrow(classifiable)

  sig_label <- function(p) {
    ifelse(p < 0.001, "***", ifelse(p < 0.01, "**", ifelse(p < 0.05, "*", "(not significant)")))
  }

  cat(sprintf("\nLogistic regression (individual papers, n = %d)\n", n_papers))
  cat(sprintf("  Log-odds per year:      %+.4f\n", log_or))
  cat(sprintf("  Odds ratio per year:     %.4f  (%.1f%% change per year)\n",
              or_per_year, (or_per_year - 1) * 100))
  cat(sprintf("  Odds ratio per decade:   %.4f  (%.1f%% change per decade)\n",
              or_per_dec, (or_per_dec - 1) * 100))
  cat(sprintf("  p-value:                 %.2e  %s\n", glm_p, sig_label(glm_p)))
  cat(sprintf("  Interpretation:          A paper published one year later has\n"))
  cat(sprintf("                           %.1f%% %s odds of mentioning mycorrhiz*\n",
              abs((or_per_year - 1) * 100),
              ifelse(log_or < 0, "lower", "higher")))

  # --- SECONDARY: weighted lm on annual proportions (matches the plot) ---
  lm_fit <- lm(pct_match ~ year, data = trend_df, weights = n_classifiable)
  lm_s   <- summary(lm_fit)
  lm_cf  <- coef(lm_s)

  slope_yr  <- lm_cf["year", "Estimate"]
  lm_p      <- lm_cf["year", "Pr(>|t|)"]
  r2        <- lm_s$r.squared

  cat(sprintf("\nWeighted linear regression on annual proportions (matches plot)\n"))
  cat(sprintf("  Slope:                   %+.4f per year  (%+.1f%% per decade)\n",
              slope_yr, slope_yr * 10 * 100))
  cat(sprintf("  R²:                      %.3f\n", r2))
  cat(sprintf("  p-value:                 %.2e  %s\n", lm_p, sig_label(lm_p)))

  invisible(list(glm = glm_fit, lm = lm_fit))
}

fits_1997 <- report_significance(d1997,  trend_1997, "Johnson et al. 1997 paper")
fits_full <- report_significance(dfull, trend_full,  "Nancy Collins Johnson full corpus")

# ---------------------------------------------------------------------------
# 8. Console summary (early vs. recent means)
# ---------------------------------------------------------------------------

cat("\n--- Mean mycorrhiz* rate by era (full corpus, classifiable papers only) ---\n")
early  <- trend_full |> filter(year %in% 1997:2005) |> summarise(pct = mean(pct_match))
recent <- trend_full |> filter(year %in% 2020:2025) |> summarise(pct = mean(pct_match))
cat(sprintf("Mean mycorrhiz* rate 1997-2005:  %.1f%%\n", early$pct  * 100))
cat(sprintf("Mean mycorrhiz* rate 2020-2025:  %.1f%%\n", recent$pct * 100))
