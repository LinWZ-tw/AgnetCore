# Research Strategy

## 1. Significance

### 1.1 The Post-GWAS Translational Bottleneck

Genome-wide association studies (GWAS) have catalogued tens of thousands of variant-trait associations across hundreds of human diseases, yet more than 90% of GWAS signals reside in non-coding genomic regions where causal mechanisms require multi-modal functional evidence to resolve (Claussnitzer et al., 2020; Gallagher and Chen-Plotkin, 2018). The consequence is a manifest gap between statistical discovery and biological understanding: druggable targets and prognostic biomarkers underlying most associated loci remain unidentified, and expert-driven integration of regulatory, perturbation, and clinical evidence requires weeks to months per locus.

Bridging this gap requires a **five-stage translational chain**: (1) variant-to-gene resolution through regulatory evidence integration; (2) tissue-specific quantification of variant effects on gene expression; (3) pharmacological tractability assessment; (4) *in-silico* perturbation simulation; and (5) transcriptome-to-proteome biomarker projection (Cano-Gamez and Trynka, 2020; Huang et al., 2025). Currently, there is no tool that covers all five stages within a single automated workflow (Falola et al., 2023; Chen et al., 2025).

### 1.2 Unrealized Potential of NIH Common Fund Data

Twenty NIH Common Fund programs collectively provide the data required to execute this translational chain: chromatin architecture maps (4D Nucleome), single-cell atlases (HuBMAP, SenNet), cis-regulatory variant catalogs (GTEx), controlled-perturbation multi-omic time series (MoTrPAC), perturbation signatures (LINCS), target pharmacology annotations (IDG), longitudinal clinical cohorts (A2CPS, iHMP), and others. These resources remain siloed across separate portals, identifier systems, and access models, precluding their integration as a unified translational resource. However, there is currently no existing computational infrastructure that integrates these resources into a single analysis workflow. 

## 2. Innovation

Existing autonomous research agent frameworks, including The AI Scientist, AutoResearchClaw, Coscientist, and BioAgents, demonstrate that general-purpose agentic AI can coordinate multi-step scientific workflows but fail to address post-GWAS translational analysis at four structural barriers (Tan et al., 2025): 

(1) Silent statistical misconfiguration. Currently commonly used tools such as SuSiE, COLOC, and S-PrediXcan require dataset-specific parameterization (ancestry-matched linkage disequilibrium matrices, calibrated priors, tissue-matched expression models) that a general agentic AI cannot reliably infer; misconfigured parameters produce numerically plausible but statistically invalid outputs indistinguishable from correct results. 

(2) Pre-execution authorization failure. Controlled-access datasets require institutional authorization through dbGaP, EGA, AnVIL, or BioData Catalyst; authorization gaps discovered mid-execution corrupt partially completed session states and require full pipeline restart. 

(3) Probabilistic state collapse. Continuous posteriors propagated as natural-language summaries lose the gradient structure required for downstream Bayesian prioritization, amplifying rather than propagating upstream uncertainty.

(4) Translational chain underdetermination. The five-stage inference chain must be externally specified and scientifically correct; encoding the dependency structure between stages, the designation of primary versus supplementary datasets, and the uncertainty propagation rules at each transition requires domain expertise equivalent in effort to building a domain-specific system, such that a general framework fully adapted to this purpose has in effect become one.

We propose **AgentGWAS**, a computational system that executes a complete five-stage post-GWAS translational pipeline within a single LLM-orchestrated framework integrating twenty NIH Common Fund programs. Stage-specific agents support a configurable LLM backend (e.g. Claude, Gemini, and GPT), selected for structured output reliability and tool-use fidelity under constrained Pydantic schemas; LLM reasoning is architecturally isolated from deterministic statistical computation in all five stages. Three architectural innovations distinguish this system from existing tools:

**(1) Calibrated Uncertainty Diffusion.** A typed PipelineState Pydantic object carries posterior inclusion probabilities (Stage 1), colocalization H4 statistics and TWAS Z-scores (Stage 2), Target Development Level classifications (Stage 3), LINCS connectivity tau statistics (Stage 4), and hazard ratios with confidence intervals (Stage 5) as continuous quantities across all stage transitions. LangGraph conditional edges implement uncertainty-conditional routing, returning the graph to earlier stages when evidence thresholds are not met. No existing post-GWAS system propagates continuous posteriors across a multi-stage translational chain of this form.

**(2) Mandatory Investigator Plan Review.** Before any computation is dispatched, AgentGWAS presents a structured session plan specifying stages, datasets, statistical parameters, access authorizations, and estimated compute hours. Execution proceeds only upon investigator approval through a non-bypassable LangGraph interrupt node. This design implements investigator oversight as an architectural guarantee, distinguishing AgentGWAS from autonomous research agents that operate with minimal oversight by default, and ensuring controlled-access authorization gaps are surfaced before execution rather than discovered mid-run.

**(3) Unified Variant-to-Biomarker Knowledge Graph.** Eleven typed node categories (Variant, CredibleSet, Gene, Tissue, CellType, Drug, Compound, Protein, Phenotype, Pathway, Microbiome) are connected by seven typed edge categories carrying calibrated uncertainty scores as edge properties, enabling multi-hop traversal queries spanning the complete variant-to-biomarker evidence chain. This representation surpasses KGWAS, which is restricted to variant-gene relationships, and GRASP, which spans pharmacology without the full translational chain.

## 3. Approach

### 3.1 Pipeline Architecture

The five-stage pipeline executes as a directed acyclic graph: Stage 1 generates gene-level credible sets; Stages 2 and 3 execute concurrently; Stage 4 integrates joint Stage 2-3 outputs; Stage 5 receives Stage 4 outputs. The central hypothesis is that this framework recovers validated causal genes and approved therapeutic targets at benchmark loci with greater reproducibility than expert-driven single-program analyses. Validation employs benchmark loci for type 2 diabetes (TCF7L2, SLC30A8) and lipid metabolic traits (PCSK9, APOC3), with causal gene recovery and approved-target identification as primary performance metrics.

![Figure 1. AgentGWAS pipeline architecture. Investigator queries are converted to a structured session plan by the Planner Agent; execution proceeds only upon human approval through a non-bypassable review node. The five computational stages execute as a directed acyclic graph with Stages 2 and 3 running concurrently from Stage 1 outputs. Dashed edges denote bidirectional read/write interactions with the Unified Variant-to-Biomarker Knowledge Graph at every stage.](agentgwas_pipeline_v2.4.png)

**Stage 1 (Variant-to-Gene Resolution).** SuSiE and FINEMAP fine-mapping generates credible-set posterior inclusion probabilities. Variants are mapped to chromatin contact domains and enhancer-promoter loops (4DN Hi-C, HiChIP, PLAC-seq), intersected with open chromatin and histone modification profiles from HuBMAP and SenNet (ATAC-seq, ChIP-seq), and scored using Activity-by-Contact modeling. *Primary:* 4DN, HuBMAP; *supporting:* SenNet, GTEx, LINCS.

**Stage 2 (Variant-to-Transcriptome Propagation).** Colocalization applies coloc (H4 posterior probability) and eCAVIAR across GTEx tissues with SMR/HEIDI for pleiotropy assessment. TWAS uses S-PrediXcan and FUSION tissue-specific expression models. Mendelian randomization uses TwoSampleMR with cis-eQTL instruments for directional causal inference. *Primary:* GTEx; *supporting:* MoTrPAC, HuBMAP, SenNet, H3Africa, Kids First, UDN, SMaHT.

**Stage 3 (Druggability Assessment).** Candidate genes are classified by Target Development Level (Tclin, Tchem, Tbio, Tdark) via the IDG TCRD Pharos GraphQL API, supplemented with ChEMBL compound activity data, KOMP2 murine loss-of-function phenotypes, and GlyGen glycoprotein annotations. GTEx expression baselines quantify on-target adverse effect exposure. *Primary:* IDG; *supporting:* LINCS, KOMP2, GTEx, GlyGen.

**Stage 4 (In-Silico Perturbation Simulation).** Disease expression signatures are scored against LINCS L1000 (approximately 1.5 million profiles) using connectivity tau statistics with permutation-based empirical p-values. Cell-context mismatch between the query signature and LINCS reference cell lines is quantified and propagated as uncertainty metadata on output edges. *Primary:* LINCS; *supporting:* IDG, Bridge2AI, MoTrPAC, SenNet.

**Stage 5 (Transcriptome-to-Proteome Biomarker Projection).** Matched transcript-protein pairing uses MoTrPAC multi-omic time series and A2CPS longitudinal cohorts. Survival and treatment-response modeling uses iHMP longitudinal clinical data. Biofluid accessibility is assessed with GlyGen glycoproteomic annotations and ExRNA biofluid catalogs. *Primary:* MoTrPAC, A2CPS, iHMP; *supporting:* ExRNA, GlyGen, Metabolomics Workbench, Bridge2AI.

### 3.2 Software Architecture

AgentGWAS is implemented as six layers: a Streamlit GUI or React/FastAPI application for query submission and plan review; a planner agent producing Pydantic-validated SessionPlan objects with pre-execution access governance; a session management layer using SQLite/DynamoDB with Celery/SQS task dispatch; a LangGraph orchestration layer with per-stage StateGraph subgraphs sharing the PipelineState object; a bioinformatics compute layer executing statistical tools (SuSiE, FINEMAP, coloc, S-PrediXcan, LINCS connectivity) as containerized Nextflow processes; and a Neo4j/Neptune knowledge graph with W3C PROV-compatible provenance logging.

### 3.3 Validation and Implementation Timeline

**Benchmark metrics.** (1) The expected causal gene must appear in the top-ranked Stage 1 output for all four loci. (2) Tclin classification must be recovered for PCSK9 and APOC3; Tchem or above for SLC30A8. (3) Five-stage pipeline completion without unrecoverable error for all four loci. PCSK9 and APOC3 serve as positive controls with full liver coverage across GTEx, HuBMAP, and LINCS. TCF7L2 and SLC30A8 test access governance flagging under the pancreatic islet eQTL gap condition.

**Milestones.** Months 1-3: knowledge graph schema and PipelineState models. Months 3-6: planner agent, GUI, and access governance module. Months 6-9: Stage 2 end-to-end validation at TCF7L2. Months 9-14: Stage 1 and integrated Stages 1-2 at all benchmark loci. Months 14-20: Stages 3-5 with parallel dispatch validation. Months 20-24: Cloud deployment and public release.

## References

Barbeira, A.N. et al. Exploring phenotypic consequences of tissue specific gene expression variation inferred from GWAS summary statistics. *Nat. Commun.* **9**, 1825 (2018). https://doi.org/10.1038/s41467-018-03621-1

Cano-Gamez, E. & Trynka, G. From GWAS to function: using functional genomics to identify the mechanisms underlying complex diseases. *Front. Genet.* **11**, 424 (2020). https://doi.org/10.3389/fgene.2020.00424

Chen, X. et al. Artificial intelligence agents for biological research: a survey. *Brief. Bioinform.* **27**, bbag075 (2025). https://doi.org/10.1093/bib/bbag075

Claussnitzer, M. et al. A brief history of human disease genetics. *Nature* **577**, 179–189 (2020). https://doi.org/10.1038/s41586-019-1879-7

Falola, O. et al. SysBiolPGWAS: simplifying post-GWAS analysis through the use of computational technologies and integration of diverse omics datasets. *Bioinformatics* **39**, btac791 (2023). https://doi.org/10.1093/bioinformatics/btac791

Fulco, C.P. et al. Activity-by-contact model of enhancer-promoter regulation from thousands of CRISPR perturbations. *Nat. Genet.* **51**, 1664–1669 (2019). https://doi.org/10.1038/s41588-019-0538-0

Gallagher, M.D. & Chen-Plotkin, A.S. The post-GWAS era: from association to function. *Am. J. Hum. Genet.* **102**, 717–730 (2018). https://doi.org/10.1016/j.ajhg.2018.04.002

Giambartolomei, C. et al. Bayesian test for colocalisation between pairs of genetic association studies using summary statistics. *PLoS Genet.* **10**, e1004383 (2014). https://doi.org/10.1371/journal.pgen.1004383

GTEx Consortium. The GTEx Consortium atlas of genetic regulatory effects across human tissues. *Science* **369**, eaaz1776 (2020). https://doi.org/10.1126/science.aaz1776

Hemani, G. et al. The MR-Base platform supports systematic causal inference across the human phenome. *eLife* **7**, e34408 (2018). https://doi.org/10.7554/eLife.34408

Huang, J. et al. Twenty years of genome-wide association studies: health translation challenges and AI opportunities. *Eur. J. Hum. Genet.* (2025). https://doi.org/10.1038/s41431-025-01951-5

Nguyen, D.T. et al. Pharos: Collating protein information to shed light on the druggable genome. *Nucleic Acids Res.* **45**, D995–D1002 (2017). https://doi.org/10.1093/nar/gkw1072

Subramanian, A. et al. A next generation connectivity map: L1000 platform and the first 1,000,000 profiles. *Cell* **171**, 1437–1452 (2017). https://doi.org/10.1016/j.cell.2017.10.049

Tan, X. et al. Streamline automated biomedical discoveries with agentic bioinformatics. *Brief. Bioinform.* **26**, bbaf505 (2025). https://doi.org/10.1093/bib/bbaf505

Wang, G. et al. A simple new approach to variable selection in regression, with application to genetic fine mapping. *J. R. Stat. Soc. Series B* **82**, 1273–1300 (2020). https://doi.org/10.1111/rssb.12388
