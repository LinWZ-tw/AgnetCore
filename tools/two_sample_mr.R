#!/usr/bin/env Rscript
# Usage: Rscript two_sample_mr.R <cojo_jma_file> <outcome_gwas_csv> <outcome_name> <output_prefix>
#
# Two-sample Mendelian Randomization using COJO-independent SNPs as the
# exposure instrument set and an arbitrary outcome GWAS (e.g. another trait,
# for trait-to-trait MR) as the outcome.

if (!require("TwoSampleMR", quietly = TRUE)) {
  cat("Installing TwoSampleMR...\n")
  if (!require("remotes", quietly = TRUE)) install.packages("remotes", repos="http://cran.us.r-project.org")
  remotes::install_github("MRCIEU/TwoSampleMR")
}
if (!require("data.table", quietly = TRUE)) {
  install.packages("data.table", repos="http://cran.us.r-project.org")
}

library(TwoSampleMR)
library(data.table)

args = commandArgs(trailingOnly=TRUE)
if(length(args) < 4) {
  stop("Usage: Rscript two_sample_mr.R <cojo_jma_file> <outcome_gwas_csv> <outcome_name> <output_prefix>")
}

exposure_file = args[1]
outcome_file = args[2]
outcome_name = args[3]
out_prefix = args[4]

cat("==========================================\n")
cat("Starting Two-Sample Mendelian Randomization\n")
cat("==========================================\n")

# 1. Read and format Exposure Data (from COJO)
cat("Loading Exposure Data from COJO results:", exposure_file, "\n")
cojo_data = fread(exposure_file)
cojo_df = as.data.frame(cojo_data)
print(head(cojo_df))

# COJO .jma columns: Chr, SNP, bp, refA, freq, b, se, p, n, freq_geno, bJ, bJ_se, pJ, LD_r
# We use the joint estimates (bJ, bJ_se, pJ) for MR as they represent independent effects
exp_dat <- format_data(
  cojo_df,
  type = "exposure",
  header = TRUE,
  phenotype_col = "Exposure",
  snp_col = "SNP",
  beta_col = "bJ",
  se_col = "bJ_se",
  eaf_col = "freq",
  effect_allele_col = "refA",
  pval_col = "pJ",
  chr_col = "Chr",
  pos_col = "bp"
)

# NOTE: COJO doesn't output the other allele explicitly in the .jma file.
# For strict MR harmonization, we ideally need the other allele.
# If the outcome data has both alleles, TwoSampleMR will try its best to infer,
# but it's a known limitation when using just the .jma output directly without the original GWAS.
# For this script, we proceed with what COJO provides.

cat("Loaded", nrow(exp_dat), "independent exposure instruments.\n")
print(exp_dat$SNP)

# 2. Read and format Outcome Data
cat("Loading Outcome Data:", outcome_file, "\n")
out_dat_raw = fread(outcome_file)
# TwoSampleMR converts SNP IDs to lowercase during formatting.
# We must match that for the intersection to work.
out_dat_raw$SNP <- tolower(out_dat_raw$SNP)

# Extract only the SNPs present in our exposure dataset
out_dat_subset = as.data.frame(out_dat_raw[out_dat_raw$SNP %in% exp_dat$SNP, ])
cat("Number of SNPs matching in Outcome data:", nrow(out_dat_subset), "\n")

# Formatting Outcome.
out_dat <- format_data(
  out_dat_subset,
  type = "outcome",
  header = TRUE,
  phenotype_col = outcome_name,
  snp_col = "SNP",
  beta_col = "b",
  se_col = "se",
  effect_allele_col = "A1",
  other_allele_col = "A2",
  eaf_col = "freq",
  pval_col = "p"
)

cat("Loaded", nrow(out_dat), "SNPs from outcome data.\n")

if (nrow(out_dat) == 0) {
  stop("No overlapping SNPs found between Exposure instruments and Outcome data. Cannot proceed.")
}

# 3. Harmonize Data
cat("Harmonizing Exposure and Outcome data...\n")
dat <- harmonise_data(
  exposure_dat = exp_dat,
  outcome_dat = out_dat,
  action = 2 # Action 2 tries to infer forward strand alleles
)

# 4. Perform MR
cat("Running Mendelian Randomization analyses...\n")
res <- mr(dat, method_list=c("mr_ivw", "mr_egger_regression", "mr_weighted_median"))

# Generate Odds Ratios
res$OR <- exp(res$b)
res$OR_lower <- exp(res$b - 1.96*res$se)
res$OR_upper <- exp(res$b + 1.96*res$se)

print(res)

# Save Results
out_csv = paste0(out_prefix, "_MR_results.csv")
fwrite(res, out_csv)
cat("Saved MR results to", out_csv, "\n")

# 5. Sensitivity Analyses
cat("Running Sensitivity Analyses (Pleiotropy and Heterogeneity)...\n")
pleio <- mr_pleiotropy_test(dat)
fwrite(pleio, paste0(out_prefix, "_MR_pleiotropy.csv"))

het <- mr_heterogeneity(dat)
fwrite(het, paste0(out_prefix, "_MR_heterogeneity.csv"))

# 6. Generate Plots
cat("Generating plots...\n")
pdf(paste0(out_prefix, "_MR_scatter.pdf"), width=8, height=8)
p1 <- mr_scatter_plot(res, dat)
print(p1[[1]])
dev.off()

res_single <- mr_singlesnp(dat)
pdf(paste0(out_prefix, "_MR_forest.pdf"), width=8, height=10)
p2 <- mr_forest_plot(res_single)
print(p2[[1]])
dev.off()

cat("MR Pipeline Complete. All results and plots saved with prefix:", out_prefix, "\n")
