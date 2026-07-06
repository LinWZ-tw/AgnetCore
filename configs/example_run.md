# Example GWASagent run

A worked example task prompt for `run_pipeline.py`, covering the full pipeline for a single
trait plus trait-to-trait MR against a second trait. Paths below use the WSL-side data layout
(`~/agent0/data/...`) that the GWAS steps require under the Windows->WSL execution backend
(see README "GWAS conda environments") - substitute your own trait/data.

```
python run_pipeline.py --input /home/<user>/agent0/data/gwas/<trait>.ma --trait MASLD \
  --run-id MASLD_run --goal "
Run the post-GWAS pipeline for MASLD:

1. The exposure GWAS is already in GCTA .ma format at
   /home/<user>/agent0/data/gwas/<trait>.ma (sample size 778614) - skip format_gwas_to_ma.
   (If starting from raw summary stats instead, run format_gwas first.)
2. Run COJO against the 1000G hg38 reference panel at
   /home/<user>/agent0/data/ref/1000G_phase3/all_hg38. This is the full ALL-VARIANTS panel
   (~75M SNPs), which gcta64 cannot load whole on a <=15GB machine, so run COJO with
   per_chromosome=true (chromosomes "1-22"): it runs one chromosome at a time against
   auto-created per-chr bfiles and concatenates - identical result to a genome-wide run.
3. For each COJO-independent locus, run SuSiE fine-mapping in a +/-500kb window.
4. Validate SNP -> gene links via SMR against GTEx liver eQTLs at
   /home/<user>/agent0/data/ref/gtex_v8/Liver.v8.signif_variant_gene_pairs.txt.gz
   (this is a liver-disease trait, so liver eQTLs are the right tissue).
5. I also want to test whether MASLD causally contributes to Cirrhosis - supply the outcome
   GWAS .ma and run two-sample MR for this.
6. Build the causal network (including the MASLD->Cirrhosis edge from step 5's real MR output,
   not a placeholder) and visualize it.

Put all outputs under /home/<user>/agent0/results/MASLD_run/. Tell me what you find, including
which genes have both strong fine-mapping support (PIP) and significant SMR evidence.
"
```

## Config schemas referenced by the tools

`run_susie_batch`'s `--config` (write via the agent's `write_json_config` tool):

```json
{
  "locus_master_file": "/home/<user>/agent0/results/MASLD_run/COJO/COJO_MASLD_locus_master.csv",
  "sumstats_map": {
    "MASLD": {"file": "/home/<user>/agent0/data/gwas/<trait>.ma", "N": 778614}
  },
  "window_size": 500000,
  "out_base_dir": "/home/<user>/agent0/results/MASLD_run/SuSiE",
  "bfile": "/home/<user>/agent0/data/ref/1000G_phase3/all_hg38",
  "conda_env": "finemap",
  "cojo_locus_map_template": "/home/<user>/agent0/results/MASLD_run/COJO/COJO_{trait}_Locus_Map.xlsx"
}
```

`extract_graph_table`'s `--trait_trait_mr_config`:

```json
[
  {
    "source": "MASLD",
    "target": "Cirrhosis",
    "mr_results_csv": "results/MASLD_run/MR_results/Cirrhosis_MR_results.csv",
    "method": "Inverse variance weighted"
  }
]
```
