# NIH Common Fund Program Datasets for Post-GWAS Analysis

## Overview

This document provides a reference summary of twenty NIH Common Fund program datasets that are eligible resources for agentic post-genome-wide-association-study (post-GWAS) analysis. For each program, the entry describes (i) an abstract introduction to the scientific mission, (ii) the principal data modalities and content, and (iii) the canonical file formats and data standards in which the resource is distributed. The datasets collectively span genomics, transcriptomics, epigenomics, proteomics, metabolomics, microbiomics, imaging, and deep phenotyping, thereby providing orthogonal evidence streams for fine-mapping, causal inference, mechanistic annotation, and translational contextualization of GWAS loci.

---

## 1. 4D Nucleome (4DN)

### Abstract
The 4D Nucleome program investigates the three-dimensional organization of the human genome within the nucleus and the temporal dynamics of nuclear structure, aiming to elucidate how spatial genome architecture contributes to gene regulation, replication, and disease. The program supports the systematic mapping of chromatin conformation, nuclear bodies, and chromatin dynamics across cell types and conditions.

### Data Content
The repository comprises chromatin conformation capture assays (Hi-C, Micro-C, ChIA-PET, HiChIP, PLAC-seq), high-resolution microscopy (FISH, live-cell imaging, super-resolution), chromatin accessibility assays (ATAC-seq, DNase-seq), histone modification and transcription-factor ChIP-seq, nuclear lamina interaction data (DamID, TSA-seq), and single-cell variants thereof. Reference cell lines and primary tissues are represented.

### Data Formats
Raw sequencing reads are provided as FASTQ; aligned reads as BAM and CRAM; chromatin contact matrices as pairs, .hic, and .mcool (multi-resolution cooler); peak and interval data as BED, bedpe, and narrowPeak; imaging data as OME-TIFF and OME-Zarr; and structured metadata under the 4DN Data Portal schema with JSON-LD descriptors.

---

## 2. Acute to Chronic Pain Signatures (A2CPS)

### Abstract
A2CPS aims to identify biomarkers and biosignatures that predict the transition from acute to chronic pain following surgical insult or acute injury. By integrating longitudinal multi-omic, neuroimaging, psychophysical, and clinical data, the program seeks mechanistic and predictive signatures amenable to clinical translation.

### Data Content
The dataset contains clinical phenotypic assessments, psychophysical testing (quantitative sensory testing), functional and structural neuroimaging, electroencephalography, blood-based multi-omics (genotyping, bulk RNA-seq, proteomics, metabolomics, lipidomics), and longitudinal patient-reported outcomes from thoracic surgery and total knee arthroplasty cohorts.

### Data Formats
Sequencing data are distributed as FASTQ, BAM, and VCF; genotype arrays as PLINK and VCF; mass-spectrometry data as mzML and mzTab; neuroimaging data in DICOM and NIfTI following the Brain Imaging Data Structure (BIDS); clinical and phenotypic data as CSV and REDCap exports conforming to the A2CPS Common Data Element specification.

---

## 3. Bridge to Artificial Intelligence (Bridge2AI)

### Abstract
Bridge2AI generates flagship biomedical datasets explicitly designed to be ethically sourced, trustworthy, diverse, and machine-learning-ready, with the goal of catalyzing the application of artificial intelligence in biomedicine. The program emphasizes standardization, FAIR principles, and dataset documentation suitable for model training and benchmarking.

### Data Content
Current Bridge2AI data-generation projects include voice biomarkers of disease (Voice), cellular responses to stress and resilience (Cell Maps for AI), critical-care multimodal physiological signals (CHoRUS), and precision public-health salt-sensitivity of blood pressure (AI-READI). Modalities encompass digital voice recordings, single-cell omics, continuous waveform telemetry, wearables, retinal imaging, and structured electronic-health-record derivatives.

### Data Formats
Audio signals as WAV and FLAC with accompanying transcripts; physiologic waveforms as WFDB and HDF5; single-cell data as AnnData (.h5ad) and MuData; imaging as DICOM and OME-TIFF; tabular clinical data in the OMOP Common Data Model and FHIR; machine-learning-ready bundles as Parquet with associated datasheets and model cards.

---

## 4. Cellular Senescence Network (SenNet)

### Abstract
SenNet constructs comprehensive atlases of senescent cells across human tissues and lifespans to delineate the heterogeneity, origins, and functional consequences of cellular senescence in health and disease. The program develops tools, biomarkers, and computational resources to identify senescent cell states in situ.

### Data Content
The resource contains single-cell and single-nucleus RNA sequencing, spatial transcriptomics (Visium, Slide-seq, MERFISH, Xenium), single-cell ATAC-seq, multiplexed protein imaging (CODEX, IMC, MIBI), bulk omics, and curated senescence gene signatures across diverse human tissues.

### Data Formats
FASTQ for raw reads; AnnData (.h5ad) and Seurat RDS for processed single-cell matrices; OME-TIFF and OME-Zarr for imaging; SpatialData and Vitessce-compatible representations for spatial omics; standardized metadata under the Human Reference Atlas (HRA) and the SenNet Data Coordination Center schemas.

---

## 5. Extracellular RNA Communication (ExRNA)

### Abstract
The Extracellular RNA Communication Consortium characterizes extracellular RNAs and their carriers in biofluids to elucidate mechanisms of intercellular communication and to evaluate exRNAs as biomarkers of disease. The program standardized exRNA profiling across laboratories and platforms.

### Data Content
Small and long RNA-seq from serum, plasma, urine, cerebrospinal fluid, saliva, and cell-culture media; profiles of extracellular vesicles, lipoprotein particles, and ribonucleoprotein complexes; reference standards; and harmonized metadata across hundreds of studies available through the exRNA Atlas.

### Data Formats
Raw reads as FASTQ; alignments as BAM; quantifications as BED, BigWig, and tabular abundance matrices; per-study metadata in the exRNA metadata standard (JSON); harmonized processed data as MatrixMarket and TSV.

---

## 6. Gabriella Miller Kids First (KF)

### Abstract
The Kids First Pediatric Research Program investigates the shared genetic etiology of childhood cancers and structural birth defects through large-scale whole-genome sequencing of affected children and their families. The program provides a cloud-based Data Resource Center that supports cross-cohort discovery.

### Data Content
Germline and somatic whole-genome and whole-exome sequencing, transcriptome sequencing, structural and copy-number variant calls, harmonized clinical phenotypes (using HPO and standardized ontologies), pedigree information, and tumor-normal paired data for pediatric malignancies and congenital anomalies.

### Data Formats
FASTQ, BAM, and CRAM for sequence data; gVCF and VCF for variants; MAF for somatic mutations; TSV and JSON for clinical and phenotype data under the Kids First Data Model; access mediated through the Gen3 platform and Cavatica cloud workspaces.

---

## 7. Genotype-Tissue Expression (GTEx)

### Abstract
GTEx establishes reference catalogs of the effects of human genetic variation on gene expression and regulation across multiple tissues, providing a canonical resource for expression quantitative trait locus (eQTL) and splicing QTL (sQTL) discovery and for colocalization with GWAS signals.

### Data Content
Whole-genome sequencing, deep RNA sequencing across approximately fifty-four tissues in nearly one thousand post-mortem donors, histology whole-slide images, telomere and mitochondrial measures, cis- and trans-eQTL and sQTL summary statistics, allele-specific expression, and fine-mapped regulatory variant sets.

### Data Formats
VCF for genotypes; FASTQ and BAM for reads; GCT and Parquet for expression matrices; QTL summary statistics as TSV and Parquet; histology images as SVS and NDPI; access via the AnVIL platform and the GTEx Portal with controlled-access tiers via dbGaP.

---

## 8. Glycoscience (GL)

### Abstract
The Common Fund Glycoscience program generates accessible tools, reagents, standards, and informatics resources to integrate glycan analysis into mainstream biomedical research. The effort addresses the chemical complexity of glycans and their conjugates on proteins and lipids.

### Data Content
Curated glycan structures, glycoprotein and glycolipid compositions, synthetic oligosaccharide libraries, binding-affinity data, mass-spectrometry reference spectra, and annotations linking glycans to genes, proteins, diseases, and pathways through GlyGen and related resources.

### Data Formats
Glycan structures as GlycoCT, WURCS, and IUPAC-condensed strings with GlyTouCan identifiers; mass-spectrometry data as mzML, mzIdentML, and mzTab; protein annotations in UniProt-compatible formats; integrated queryable endpoints via RESTful APIs and SPARQL over GlyGen.

---

## 9. H3Africa

### Abstract
The Human Heredity and Health in Africa (H3Africa) initiative advances genomic and epidemiologic research on the African continent, generating reference genomic data from diverse African populations and supporting studies on communicable and non-communicable diseases. The resource is essential for improving diversity in GWAS and fine-mapping in populations with short linkage-disequilibrium blocks.

### Data Content
Whole-genome sequences, dense genotyping arrays (including the H3Africa array), transcriptomic and epigenetic data, microbiome profiles, and harmonized clinical and phenotypic data across cardiovascular, metabolic, infectious, and neurological disease cohorts from numerous African countries.

### Data Formats
FASTQ, BAM, and CRAM for sequence data; VCF for variants; PLINK binary (BED/BIM/FAM) for genotype arrays; summary statistics as TSV and VCF; controlled-access distribution via the European Genome-phenome Archive (EGA) and the H3Africa Data and Biospecimen Archive.

---

## 10. Human BioMolecular Atlas Program (HuBMAP)

### Abstract
HuBMAP builds an open, global framework for mapping the human body at single-cell resolution, integrating multi-modal molecular and imaging data across organs to construct reference atlases of healthy human tissues. The program provides common ontologies, assays, and pipelines for cross-laboratory interoperability.

### Data Content
Single-cell and single-nucleus RNA-seq, single-cell ATAC-seq, spatial transcriptomics, multiplexed immunofluorescence (CODEX, Cell DIVE, MxIF), imaging mass cytometry, MALDI imaging, light-sheet microscopy, and autofluorescence images, with comprehensive donor and sample metadata.

### Data Formats
FASTQ, BAM, AnnData (.h5ad), and MuData for sequencing; OME-TIFF, OME-Zarr, and IMZML for imaging; ATLAS JSON for the Human Reference Atlas; HIVE metadata objects; distribution via the HuBMAP Data Portal and Globus endpoints.

---

## 11. Human Microbiome Project (HMP)

### Abstract
The original Human Microbiome Project characterized microbial communities at multiple body sites in a reference cohort of healthy adults, producing a foundational catalog of the human microbiota and associated analytic tools and methods.

### Data Content
16S rRNA gene amplicon sequencing, whole-metagenome shotgun sequencing, reference microbial genomes, taxonomic and functional community profiles, and associated participant metadata collected from oral, skin, nasal, gastrointestinal, and urogenital sites.

### Data Formats
FASTQ for sequencing reads; SFF for legacy 454 data; BIOM and TSV for OTU/ASV tables; FASTA and GFF for reference genomes and annotations; standardized metadata under the MIxS (Minimum Information about any Sequence) specification.

---

## 12. Illuminating the Druggable Genome (IDG)

### Abstract
The IDG program characterizes understudied proteins in three druggable target families (G-protein-coupled receptors, ion channels, and protein kinases) to reduce the knowledge gap on potential therapeutic targets. The program curates evidence on target biology, disease association, and chemical tractability.

### Data Content
Harmonized target-level information including expression across tissues and cells, disease associations, pathway participation, chemical probes and ligands, structural information, and literature evidence quantified via the Target Development Level classification. These are delivered through the Pharos portal and the Target Central Resource Database (TCRD).

### Data Formats
Relational database dumps (MySQL), REST and GraphQL API endpoints, TSV and CSV tabular exports, JSON for programmatic access, and chemical structures as SMILES, InChI, and SDF.

---

## 13. Integrated Human Microbiome Project (iHMP)

### Abstract
The integrated phase of the Human Microbiome Project examines longitudinal host-microbiome interactions in three disease-relevant contexts: inflammatory bowel disease, type 2 diabetes prediabetes, and pregnancy with preterm birth. The program couples microbial profiling with host multi-omics and clinical outcomes.

### Data Content
Longitudinal 16S, metagenomic, and metatranscriptomic sequencing; host transcriptomics, proteomics, metabolomics, lipidomics, cytokine panels, and serology; clinical phenotypes and medications; and viromics and culturomics from matched specimens.

### Data Formats
FASTQ for sequencing; BIOM for community tables; mzML and mzTab for mass-spectrometry outputs; harmonized tabular data in TSV; metadata in MIxS-compatible JSON; access through the HMP Data Portal and the NCBI Sequence Read Archive.

---

## 14. Knockout Mouse Phenotyping Program (KOMP2)

### Abstract
KOMP2, the United States contribution to the International Mouse Phenotyping Consortium (IMPC), generates and broadly phenotypes knockout mouse lines for every protein-coding gene in the mouse genome, producing a reference resource for gene function and disease modeling.

### Data Content
Standardized pipelines of morphological, physiological, behavioral, metabolic, hematological, ophthalmologic, and histopathological phenotyping; embryonic lethality screens; X-ray and micro-CT imaging; viability and fertility outcomes; and linked genotyping quality-control data for each knockout line.

### Data Formats
Phenotype data encoded in the IMPReSS (International Mouse Phenotyping Resource of Standardised Screens) ontology and delivered as CSV, JSON, and via the IMPC REST API; images as TIFF, DICOM, and JPEG; whole-slide histology as SVS; controlled-vocabulary terms from the Mammalian Phenotype Ontology.

---

## 15. Library of Integrated Network-based Cellular Signatures (LINCS)

### Abstract
LINCS catalogs molecular and cellular signatures induced by chemical, genetic, and environmental perturbations across a wide range of cell lines and primary cells to support hypothesis generation on mechanism of action, drug repurposing, and disease network inference.

### Data Content
L1000 reduced-representation transcriptomic profiles of tens of thousands of perturbations; P100 and GCP proteomic and epiproteomic assays; high-content cell-imaging (Cell Painting); kinomics (KINOMEscan); RNA-seq and ATAC-seq subsets; and curated metadata for cell lines, compounds, and genetic perturbations.

### Data Formats
GCTx and GCT for gene-expression matrices; HDF5 for multi-level signature archives; CEL for raw array data; TSV and CSV for metadata; OME-TIFF for imaging; programmatic access via the clue.io platform and the BD2K LINCS Data Portal.

---

## 16. Metabolomics Workbench

### Abstract
The Metabolomics Workbench serves as the national repository and analysis platform for metabolomics data, standards, protocols, and tools, facilitating deposition, dissemination, and reuse of untargeted and targeted metabolomic datasets.

### Data Content
Mass-spectrometry and nuclear-magnetic-resonance spectra, metabolite identifications and quantifications, associated clinical and experimental metadata, reference spectral libraries, and curated pathway and compound information linked to external ontologies.

### Data Formats
Raw instrument data as mzML, mzXML, and vendor-native files; processed data in mwTab (the Workbench native tabular format) and mzTab-M; compound identifiers linked to RefMet, HMDB, KEGG, and PubChem; metadata under the Metabolomics Standards Initiative schema.

---

## 17. Molecular Transducers of Physical Activity in Humans (MoTrPAC)

### Abstract
MoTrPAC maps the molecular responses to acute and chronic exercise across multiple tissues in humans and in rats, producing a compendium of exercise-induced molecular changes to support discovery of the mechanisms linking physical activity to health.

### Data Content
Multi-tissue (skeletal muscle, adipose, liver, heart, lung, kidney, blood, and others) bulk and single-cell transcriptomics, epigenomics (ATAC-seq, methylation), proteomics, phosphoproteomics, acetyl-proteomics, ubiquitylomics, metabolomics, and lipidomics collected at defined post-exercise time points, together with physiological and phenotypic measurements.

### Data Formats
FASTQ, BAM, and count matrices (TSV, Parquet) for sequencing; mzML, RAW, and mzTab for mass spectrometry; processed data in standardized R-compatible RDS/H5 objects; access through the MoTrPAC Data Hub and BioData Catalyst with controlled-access tiers.

---

## 18. Somatic Mosaicism Across Human Tissues (SMaHT)

### Abstract
SMaHT investigates the landscape, mechanisms, and consequences of somatic mosaicism across human tissues throughout life, generating reference maps of post-zygotic genetic variation in non-cancerous tissues from carefully curated donors.

### Data Content
Deep and ultra-deep bulk whole-genome sequencing, duplex sequencing, single-cell and single-nucleus DNA and RNA sequencing, long-read sequencing (PacBio HiFi, Oxford Nanopore), mitochondrial variation, and matched multi-tissue sampling from benchmarking donors.

### Data Formats
FASTQ, BAM, and CRAM for sequence data; VCF and gVCF for variants; duplex consensus formats; tabular single-cell matrices as AnnData (.h5ad); metadata and phenotypic data through the SMaHT Data Portal with dbGaP-controlled access.

---

## 19. Stimulating Peripheral Activity to Relieve Conditions (SPARC)

### Abstract
SPARC generates high-resolution anatomical and functional maps of the peripheral nervous system innervating internal organs and develops neuromodulation strategies and computational models to guide bioelectronic medicine. The program emphasizes rigorous data curation and FAIR dissemination.

### Data Content
Neuroanatomical tracing, electrophysiological recordings, functional responses to peripheral nerve stimulation, histology and microscopy across autonomic organ systems, anatomically grounded computational models, and device and stimulation parameters linked to physiological outcomes in multiple species.

### Data Formats
Datasets are packaged under the SPARC Dataset Structure (SDS); electrophysiology in Neurodata Without Borders (NWB); imaging in DICOM, OME-TIFF, and SBEM; computational models in SBML, CellML, and Python/MATLAB source; distributed via the SPARC Portal with persistent DOIs.

---

## 20. Undiagnosed Diseases Network (UDN)

### Abstract
The UDN brings together clinical and research expertise to diagnose patients with rare and previously undiagnosed conditions and to catalyze discovery of new disease entities and mechanisms. The network couples deep clinical phenotyping with comprehensive multi-omic investigation.

### Data Content
Whole-exome and whole-genome sequencing (trio-based when feasible), RNA sequencing, targeted long-read sequencing for structural and repeat variants, metabolomics, deep clinical phenotyping encoded in the Human Phenotype Ontology, family pedigrees, and functional validation data from model organisms.

### Data Formats
FASTQ, BAM, and CRAM for reads; VCF and gVCF for variants; phenotypic data as HPO-encoded JSON and as Phenopackets; clinical metadata in the UDN Gateway schema; controlled-access distribution via dbGaP and the AnVIL platform.

---

## Cross-Cutting Considerations for Post-GWAS Integration

Post-GWAS workflows that draw on these resources must harmonize identifiers and coordinates across genome builds (typically GRCh37 and GRCh38, with emerging T2T-CHM13 mappings), reconcile ontology usage (HPO, MONDO, Uberon, Cell Ontology, ChEBI), respect the differing access tiers (open, registered, controlled via dbGaP, EGA, or program-specific committees), and acknowledge heterogeneous consent structures. Common integrative operations include colocalization of GWAS signals with eQTL and sQTL maps (GTEx, MoTrPAC, SMaHT), mechanistic annotation through chromatin contact and regulatory data (4DN, HuBMAP, SenNet), cell-type deconvolution and context specification through single-cell atlases (HuBMAP, SenNet, Bridge2AI), drug-target prioritization (IDG, LINCS), microbiome- and metabolome-informed endophenotype analysis (HMP, iHMP, Metabolomics Workbench, A2CPS, MoTrPAC), population-specific fine-mapping (H3Africa, Kids First), and translational validation against clinical cohorts (UDN, Kids First, A2CPS). Data delivery platforms that recur across programs include the NHGRI AnVIL, the NIH Common Fund Data Ecosystem (CFDE) portal, Gen3-based data commons, Globus, and dbGaP, which together provide interoperable computational environments suitable for agentic orchestration.
