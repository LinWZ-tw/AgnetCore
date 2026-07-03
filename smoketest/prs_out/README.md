# PRS smoke-test artifacts (Stage PRS: clumping + thresholding)

Validated real run of `tools/prs_clump_score.sh` (via the `prs` step / Stage PRS)
in the `finemap` conda env inside WSL, mirroring how `cojo_out/` and `susie_out/`
were produced.

Command:

```bash
conda run -n finemap bash tools/prs_clump_score.sh \
    smoketest/MASLD_chr1_slice.ma \
    data/ref/1000G_phase3/all_hg38_chr1 \
    data/ref/1000G_phase3/all_hg38_chr1 \
    smoketest/prs_out/MASLD_chr1_prs \
    1e-2 0.1 250
```

`p_threshold=1e-2` is used only because this chr1 slice has no genome-wide-
significant SNP (min p = 1.9e-3); a real run keeps the 5e-8 default. The LD
reference is reused as the target bfile, so the per-individual scores are a
runnable demo, not a real risk estimate — supply a genuine target cohort's
bfile for that.

Result: `--clump` formed 5 independent index SNPs (see
`MASLD_chr1_prs_clump.clumped`); `plink --score` produced per-individual PRS for
all 3202 1000G samples. Tool summary line:

```
PRS_SUMMARY n_individuals=3202 score_mean=-0.00217068 score_sd=0.00866591
PRS_SUMMARY n_snps=5
```

Files kept here are the lean evidence (clumped index set, retained SNP list, and
plink logs). The regenerable `.weights.txt`, `.nopred`, and the full 151 KB
`.profile` (FID/IID/CNT/CNT2/SCORE per sample) are not committed.

A pathway-restricted PRS was also validated by passing an 8th argument (a SNP-list
file): the clumped set is intersected with it, scoring only variants that map to
the candidate genes/pathway.
