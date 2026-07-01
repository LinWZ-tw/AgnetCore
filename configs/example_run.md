# Example GWASagent run

A worked example task prompt for `agent.py`, covering the full pipeline for a single trait plus
trait-to-trait MR against a second trait. Paths below match the existing liver-disease project
data under `3dGenomeBrowser/EPFinder/data/` - substitute your own trait/data.

```
python agent.py --task "
Run the post-GWAS pipeline for MASLD:

1. The exposure GWAS is already in GCTA .ma format at
   /mnt/Storage5/weizhilin/3dGenomeBrowser/EPFinder/data/full_MASLD_Ghodsian2021.ma
   (sample size 778614) - skip format_gwas_to_ma.
2. Run COJO against the 1000G hg38 reference panel at
   /mnt/Storage5/weizhilin/3dGenomeBrowser/EPFinder/data/1000Genome/1000G_hg38_common.
3. For each COJO-independent locus, run SuSiE fine-mapping in a +/-500kb window.
4. Validate SNP -> gene links via SMR against GTEx v11 liver eQTLs at
   /mnt/Storage5/RefGenome/gtex/GTEx_v11/GTEx_Analysis_v11_eQTL/Liver.v11.eQTLs.signif_pairs.parquet
   (this is a liver-disease trait, so liver eQTLs are the right tissue).
5. I also want to test whether MASLD causally contributes to Cirrhosis - the outcome GWAS is at
   /mnt/Storage5/weizhilin/3dGenomeBrowser/EPFinder/data/full_Cirrhosis_Ghouse2024.ma. Run
   two-sample MR for this.
6. Build the causal network (including the MASLD->Cirrhosis edge from step 5's real MR output,
   not a placeholder) and visualize it.

Put all outputs under results/MASLD_run/. Tell me what you find, including which genes have
both strong fine-mapping support (PIP) and significant SMR evidence.
"
```

## Config schemas referenced by the tools

`run_susie_batch`'s `--config` (write via the agent's `write_json_config` tool):

```json
{
  "locus_master_file": "results/MASLD_run/COJO/COJO_MASLD_locus_master.csv",
  "sumstats_map": {
    "MASLD": {"file": "data/full_MASLD_Ghodsian2021.ma", "N": 778614}
  },
  "window_size": 500000,
  "out_base_dir": "results/MASLD_run/SuSiE",
  "bfile": "data/1000Genome/1000G_hg38_common",
  "conda_env": "finemap",
  "cojo_locus_map_template": "results/MASLD_run/COJO/COJO_{trait}_Locus_Map.xlsx"
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
