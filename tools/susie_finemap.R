#!/usr/bin/env Rscript
# Usage: Rscript susie_finemap.R <sumstats_csv> <ld_matrix> <sample_size> <output_prefix>
#
# Runs SuSiE RSS fine-mapping on a single locus given summary statistics
# (beta, se) and an LD matrix in the same SNP order.

if (!require("susieR", quietly = TRUE)) {
  cat("Installing susieR...\n")
  install.packages("susieR", repos="http://cran.us.r-project.org")
}
if (!require("data.table", quietly = TRUE)) {
  cat("Installing data.table...\n")
  install.packages("data.table", repos="http://cran.us.r-project.org")
}

library(susieR)
library(data.table)

args = commandArgs(trailingOnly=TRUE)
if(length(args) < 4) {
  stop("Usage: Rscript susie_finemap.R <sumstats_csv> <ld_matrix_ld> <sample_size> <output_prefix>")
}

sumstats_file = args[1]
ld_file = args[2]
n_samples = as.numeric(args[3])
out_prefix = args[4]

cat("Loading summary statistics from", sumstats_file, "\n")
# Expected columns: SNP, beta, se
sumstats = fread(sumstats_file)

if (!"beta" %in% colnames(sumstats) || !"se" %in% colnames(sumstats)) {
  stop("Error: Input summary stats must contain 'beta' and 'se' columns.")
}

cat("Loading LD matrix from", ld_file, "\n")
# PLINK --r square outputs a space/tab delimited matrix without headers
R = as.matrix(fread(ld_file, header=FALSE))

# Ensure dimensions match
if(nrow(sumstats) != nrow(R)) {
  stop("Dimension mismatch: sumstats has ", nrow(sumstats), " rows, but LD matrix is ", nrow(R), "x", ncol(R))
}

# susie_rss requires shat > 0 for every SNP. A small number of SNPs (commonly
# from imputed-AF datasets) can carry beta=0/se=0 placeholders; drop them and
# the matching LD rows/columns before fitting.
bad_idx = which(sumstats$se <= 0)
if (length(bad_idx) > 0) {
  cat("Dropping", length(bad_idx), "SNP(s) with se <= 0:", paste(sumstats$SNP[bad_idx], collapse=", "), "\n")
  sumstats = sumstats[-bad_idx, ]
  R = R[-bad_idx, -bad_idx]
}

# SuSiE expects R to be symmetric and positive semi-definite. Sometimes PLINK r square has slight precision issues
# Force symmetry just in case
R = (R + t(R))/2
diag(R) = 1.0

cat("Running SuSiE RSS model...\n")
fitted_rss = susie_rss(bhat = sumstats$beta, shat = sumstats$se, R = R, n = n_samples)

cat("Extracting PIPs and Credible Sets...\n")
sumstats$PIP = susie_get_pip(fitted_rss)

# Get Credible Sets
cs = susie_get_cs(fitted_rss, Xcorr = R)
sumstats$CS = 0
if (!is.null(cs$cs)) {
  for (i in seq_along(cs$cs)) {
    # Assign CS identifier (1, 2, 3...) to SNPs in the Credible Set
    sumstats$CS[cs$cs[[i]]] = i
  }
}

out_csv = paste0(out_prefix, "_susie_results.csv")
fwrite(sumstats, out_csv)
cat("Saved results to", out_csv, "\n")

out_rds = paste0(out_prefix, "_susie_model.rds")
saveRDS(fitted_rss, out_rds)
cat("Saved full SuSiE model to", out_rds, "\n")
