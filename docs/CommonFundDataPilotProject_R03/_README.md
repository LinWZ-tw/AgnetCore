# AgentGWAS: NIH Common Fund Data Pilot Project (R03)

## Project Overview

AgentGWAS is an AI agent system for end-to-end post-GWAS translational analysis that integrates twenty NIH Common Fund program datasets within a single automated pipeline. The system orchestrates a five-stage workflow spanning variant-to-gene resolution, variant-to-transcriptome propagation, druggability assessment, in-silico perturbation simulation, and transcriptome-to-proteome biomarker projection.

## Core Documentation

### Project Aims and Strategy

**[aim_page_v2.4.md](aim_page_v2.4.md)**
Concise summary of the project significance, goals, objectives, and specific aims. Includes the core hypothesis that an LLM-orchestrated multi-agent framework can integrate heterogeneous NIH Common Fund datasets to recover validated causal genes and approved therapeutic targets at benchmark GWAS loci. This document provides the high-level overview of the AgentGWAS system and its three key innovations: calibrated uncertainty propagation, mandatory human-in-the-loop review, and unified knowledge graph integration.

**[research_strategy_v1.md](research_strategy_v1.md)**
Comprehensive research strategy document detailing the significance, innovation, and approach for the AgentGWAS project. Organized into three major sections covering the post-GWAS translational bottleneck, underutilization of NIH Common Fund program data, and the absence of automated end-to-end infrastructure. Describes all five analytical stages in detail with methods, applicable datasets, and expected outputs for each stage.

### Implementation and Architecture

**[plan.md](plan.md)**
Detailed computational implementation plan for the agentic post-GWAS analysis pipeline. Consists of four major parts: (I) Pipeline overview and design with stage-by-stage methodological components; (II) System architecture and design decisions including OpenClaw ecosystem integration analysis; (III) Disease applicability and validation strategy with detailed assessments for type 2 diabetes, liver diseases, osteoporosis, sarcopenia, lipid metabolic diseases, and obesity; (IV) Conclusions. This document serves as the primary technical planning reference for the project.

**[software_structure_v2.md](software_structure_v2.md)**
Software architecture specification for AgentGWAS detailing the six-layer system design: GUI layer, planner agent layer, session and task management layer, LangGraph orchestration layer, bioinformatics compute layer, and persistence layer. Describes design principles, component interfaces, and deployment considerations for both AWS and open-source distribution. Includes architectural diagrams showing pipeline topology and data flow.

**[agentgwas_pipeline_v2.4.mmd](agentgwas_pipeline_v2.4.mmd)** | **[agentgwas_pipeline_v2.4.png](agentgwas_pipeline_v2.4.png)**
Visual representation of the AgentGWAS pipeline architecture showing the flow from investigator query through planner agent, human review, and five analytical stages with knowledge graph integration. Available as both Mermaid source file and rendered PNG image.

### Benchmarking and Analysis

**[benchmark_v1.md](benchmark_v1.md)**
Comprehensive benchmark analysis comparing AgentGWAS with existing AI systems in four categories: GWAS and genomics-specific AI systems (KGWAS, MRAgent, Genomic Agent Discovery), multi-agent systems for bioinformatics (BioAgents), general autonomous research agents, and specialized scientific domain agents. Identifies key innovations, architectural similarities, and distinguishing features relative to AgentGWAS. Includes analysis of the OpenClaw ecosystem and its relevance to the project.

### Reference Data

**[dataset_readme.md](dataset_readme.md)**
Reference summary of twenty NIH Common Fund program datasets eligible for post-GWAS analysis. For each program, provides: (i) abstract introduction to the scientific mission, (ii) principal data modalities and content, and (iii) canonical file formats and data standards. Programs covered include 4DN, A2CPS, Bridge2AI, SenNet, ExRNA, GTEx, HuBMAP, IDG, LINCS, MoTrPAC, and others. Includes cross-cutting considerations for post-GWAS integration addressing identifier harmonization, genome build consistency, and access tier management.

**[reference_readme.md](reference_readme.md)**
Citation reference mapping for aim_page_v2.4.md. Maps each numbered citation to the specific claim it supports and the corresponding supporting statement in the source article. Includes eight key references covering GWAS history, benefits and limitations, post-GWAS functional interpretation, and systematic variant-to-gene prioritization approaches.

### Funding Information

**[Funding Opportunity Common Fund Data Pilot Projects (R03, Clinical Trial Not Allowed).txt](Funding%20Opportunity%20Common%20Fund%20Data%20Pilot%20Projects%20(R03,%20Clinical%20Trial%20Not%20Allowed).txt)**
NIH Common Fund funding opportunity announcement (RFA-RM-26-017) for pilot projects enhancing utility and usage of Common Fund data sets. Includes eligibility requirements (must use two or more CF datasets), application deadline (June 23, 2026), and complete list of eligible Common Fund program datasets. Notes that Early Stage Investigators are encouraged to apply.

## Supporting Files

**[CLAUDE.md](CLAUDE.md)**
Project instructions and style guidelines for Claude Code assistant work on this project. Specifies writing style (academic, avoid emojis), reference search protocols (UpToDate, PubMed, Google Scholar priority), and formatting preferences.

**[mermaid_config.json](mermaid_config.json)**
Configuration file for Mermaid diagram rendering used in pipeline visualizations.

**[aim_page_v2.4.docx](aim_page_v2.4.docx)**
Microsoft Word version of the aims page document.

## Project Structure

This project documentation is organized to support grant submission and implementation planning for the AgentGWAS system:

1. Start with **aim_page_v2.4.md** for a high-level overview
2. Review **research_strategy_v1.md** for comprehensive background and methods
3. Consult **plan.md** for detailed implementation planning and disease applicability assessments
4. Reference **software_structure_v2.md** for technical architecture details
5. Use **dataset_readme.md** as a reference for NIH Common Fund program capabilities
6. Review **benchmark_v1.md** to understand AgentGWAS positioning relative to existing systems

## Key Innovations

AgentGWAS introduces three principal innovations in post-GWAS translational analysis:

1. **Calibrated Uncertainty Propagation**: Multi-stage pipeline architecture that propagates continuous posterior probability estimates across all five analytical stages, enabling uncertainty-conditional routing and iterative refinement.

2. **Mandatory Human-in-the-Loop Review**: Architectural guarantee requiring explicit investigator approval of structured session plans before execution, implemented as a non-bypassable LangGraph interrupt node.

3. **Unified Knowledge Graph**: Property graph database spanning the complete variant-to-biomarker evidence chain with eleven typed node categories and seven typed edge categories carrying calibrated uncertainty scores.

## Validation Strategy

The system will be validated using benchmark loci with established causal resolution:

- **Type 2 Diabetes**: TCF7L2, SLC30A8
- **Lipid Metabolic Traits**: PCSK9, APOC3

Primary performance metrics include recovery of known causal genes and identification of approved therapeutic targets (Tclin classification).

## Dataset Integration

AgentGWAS integrates twenty NIH Common Fund programs across the five-stage analytical pipeline:

**Stage 1 (Variant-to-Gene)**: 4DN (primary), HuBMAP (primary), SenNet, GTEx, LINCS

**Stage 2 (Variant-to-Transcriptome)**: GTEx (primary), MoTrPAC, HuBMAP, SenNet, H3Africa, Kids First, UDN, SMaHT

**Stage 3 (Druggability)**: IDG (primary), LINCS, KOMP2, GTEx, GlyGen

**Stage 4 (In-Silico Perturbation)**: LINCS (primary), IDG, Bridge2AI, MoTrPAC, SenNet

**Stage 5 (Transcriptome-to-Proteome)**: MoTrPAC (primary), A2CPS (primary), iHMP (primary), ExRNA, Metabolomics Workbench, GlyGen, Bridge2AI, Kids First, UDN

## Contact and Collaboration

This project responds to NIH Common Fund RFA-RM-26-017 encouraging the use of Common Fund data. For questions about the funding opportunity, contact the CFDE Program Team at CFDE@od.nih.gov or George Papanicolaou at george.papanicolaou@nih.gov.

## Project Timeline

Application Due Date: June 23, 2026, by 5:00 PM local time of applicant organization

## Excluded Content

The archive/ folder contains deprecated files and is not indexed in this documentation.
