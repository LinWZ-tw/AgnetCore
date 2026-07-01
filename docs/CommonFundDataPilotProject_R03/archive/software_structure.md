# Software Architecture for the Agentic Post-GWAS Analysis Pipeline

## Purpose

This document specifies the software architecture for an agentic post-GWAS analysis system designed to orchestrate a five-stage translational pipeline traversing variant-to-gene resolution, variant-to-transcriptome propagation, druggability assessment, in-silico perturbation, and transcriptome-to-proteome projection. The architecture is intended to support deployment on Amazon Web Services (AWS) and open-source distribution via GitHub, with the same codebase serving both targets through environment-configurable adapter interfaces. The system includes a graphical user interface through which a researcher may express an analysis intent in natural language; a planner agent that parses this input into a structured, human-reviewable session plan; and a task dispatch layer that assigns each approved plan step to a dedicated stage subagent.

---

## Design Principles

Seven principles govern the structural decisions described in this document.

**Natural-language accessibility.** The system must be operable by researchers who are fluent in biological and clinical domain knowledge but who are not required to specify pipeline parameters programmatically. A planner agent accepts free-text queries, resolves ambiguities through structured dialogue, and produces a complete, reviewable analysis plan without requiring the user to interact directly with configuration files or command-line interfaces.

**Human-in-the-loop plan review.** Before any computational task is dispatched, the system presents the structured session plan to the user as a rendered markdown document. Execution proceeds only upon explicit approval. The user may edit the plan, reject it entirely, or request a revised plan from the planner agent. This checkpoint is not optional and is implemented as a LangGraph interrupt node rather than a courtesy prompt, ensuring it cannot be bypassed programmatically.

**Stateful, graph-structured orchestration.** Each pipeline stage emits calibrated uncertainty scores that downstream stages must consume as continuous posteriors rather than discretized binary calls. The orchestration layer must therefore maintain a typed, persistent state object that is passed between stages and that records evidence-weighted scores at every transition. A linear chain architecture is insufficient for this requirement; the orchestration framework must support conditional routing, back-propagation of corrections, and iterative refinement loops.

**Separation of orchestration from computation.** The agent orchestration layer, which reasons over evidence and selects tool calls, must be decoupled from the bioinformatics compute layer, which executes deterministic statistical analyses such as fine-mapping, colocalization, and TWAS. The former is implemented in Python using LangGraph; the latter is implemented as workflow-managed Nextflow jobs that the agent invokes as subprocess tools. This separation ensures that heavy compute can be dispatched to HPC clusters or AWS Batch without coupling it to the LLM inference runtime.

**Evidence-graph persistence.** All intermediate results are written to a property graph database as typed nodes and edges with uncertainty scores as edge properties. The knowledge graph serves as the shared memory of the pipeline across stages and across invocations, enabling multi-hop traversal queries that span the full variant-to-biomarker evidence chain.

**Access governance as first-class concern.** Multiple constituent datasets (GTEx via dbGaP, MoTrPAC via BioData Catalyst, H3Africa via EGA, UDN and Kids First via their respective gateways) require controlled access authorization. The data access layer maintains an access manifest that records authorized tiers, consent-based use limitations, and credential references. The agent consults this manifest before any data retrieval call and records access events in the audit log. The planner agent also consults this manifest at plan-generation time to flag any dataset required by the proposed plan that has not yet been authorized, surfacing access gaps to the user before execution begins rather than failing mid-run.

**Reproducibility by construction.** All pipeline runs record tool versions, model identifiers, parameter configurations, random seeds, and intermediate artifact hashes. The audit layer is implemented as a structured logging component embedded in the LangGraph state transition hooks rather than as an optional add-on.

---

## System Architecture Overview

The system comprises six horizontal layers, each of which communicates with its immediate neighbors through well-defined interfaces. From the user-facing surface downward, these layers are: the graphical user interface, the planner agent, the session and task management layer, the LangGraph orchestration layer, the bioinformatics compute layer, and the persistence layer (knowledge graph, artifact store, and audit log). The figure below represents this topology schematically.

```
┌─────────────────────────────────────────────────────────────────┐
│                     GUI Layer                                   │
│   Streamlit (open-source) / React + FastAPI (production)        │
│   Chat input ─► Plan viewer ─► Stage monitor ─► Results browser │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / WebSocket
┌──────────────────────────▼──────────────────────────────────────┐
│                  Planner Agent Layer                            │
│   NLU ─► SessionPlan (Pydantic) ─► session_plan.md              │
│   Human review interrupt ─► Approval / Edit / Reject            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Approved SessionPlan
┌──────────────────────────▼──────────────────────────────────────┐
│             Session & Task Management Layer                     │
│   Session store ─► Task dispatcher ─► Task queue                │
│   (SQLite / DynamoDB)    (Celery / SQS)                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Task messages
┌──────────────────────────▼──────────────────────────────────────┐
│           LangGraph Orchestration Layer                         │
│   Stage 1 subgraph ─► Stage 2 ─► Stage 3 ─► Stage 4 ─► Stage 5  │
│   Shared PipelineState ─► conditional edges ─► uncertainty flags│
└───────────┬──────────────────────────────────────┬──────────────┘
            │ subprocess tool calls                │ KG read/write
┌───────────▼──────────────┐          ┌────────────▼──────────────┐
│  Bioinformatics Compute  │          │    Persistence Layer      │
│  Nextflow (Batch / SLURM)│          │  Neo4j / Neptune (KG)     │
│  SuSiE, coloc, PrediXcan │          │  S3 / local (artifacts)   │
│  LINCS connectivity, ABC │          │  PROV-JSON (audit)        │
└──────────────────────────┘          └───────────────────────────┘
```

---

## Repository Structure

The repository is organized as a monorepo. All top-level directories are described below.

```
post-gwas-agent/
│
├── gui/                                # Web interface
│   ├── app.py                          # Streamlit app entry point (open-source deployment)
│   ├── pages/
│   │   ├── 01_new_session.py           # Free-text query input and plan review
│   │   ├── 02_session_status.py        # Live stage progress and agent thought stream
│   │   ├── 03_results.py               # Results browser: KG explorer, output tables
│   │   └── 04_session_history.py       # Past sessions with plan and artifact links
│   ├── components/
│   │   ├── plan_viewer.py              # Markdown plan renderer with approve/edit controls
│   │   ├── stage_progress.py           # Per-stage status card (pending/running/done/failed)
│   │   ├── kg_explorer.py              # Interactive knowledge graph visualization (pyvis)
│   │   └── artifact_browser.py         # Download links for output tables and reports
│   └── api/                            # FastAPI backend (production / AWS deployment)
│       ├── main.py                     # FastAPI app, CORS, WebSocket mount
│       ├── routers/
│       │   ├── sessions.py             # POST /sessions, GET /sessions/{id}
│       │   ├── planner.py              # POST /plan, POST /plan/{id}/approve
│       │   └── pipeline.py             # POST /run, GET /run/{id}/status
│       └── ws/
│           └── progress.py             # WebSocket handler: streams agent tokens and events
│
├── planner/                            # Natural language query understanding layer
│   ├── planner_agent.py                # LLM agent: free text -> SessionPlan Pydantic object
│   ├── session_plan_schema.py          # Pydantic schema for the structured session plan
│   │                                   #   Fields: session_id, trait, gwas_source,
│   │                                   #           genome_build, stages_to_run,
│   │                                   #           datasets_per_stage, parameters,
│   │                                   #           access_flags, expected_outputs,
│   │                                   #           estimated_compute_hours
│   ├── plan_writer.py                  # Renders SessionPlan to session_plan.md
│   ├── plan_validator.py               # Checks plan against access manifest;
│   │                                   #   flags unauthorized datasets before execution
│   └── prompts/
│       ├── system_prompt.md            # Planner agent system prompt
│       └── few_shot_examples.md        # Example queries and their structured plans
│
├── session/                            # Session lifecycle management
│   ├── session_manager.py              # Create, load, list, archive sessions
│   ├── session_store.py                # Persistence adapter (SQLite local / DynamoDB AWS)
│   ├── task_dispatcher.py              # Converts approved plan steps into task messages
│   └── task_queue.py                   # Queue adapter (Celery + Redis / AWS SQS)
│
├── workflows/                          # LangGraph graph definitions
│   ├── gwas_to_biomarker.py            # Top-level pipeline entry point
│   └── stages/
│       ├── stage1_v2g.py               # Variant-to-gene resolution subgraph
│       ├── stage2_v2t.py               # Variant-to-transcriptome propagation subgraph
│       ├── stage3_druggability.py      # Druggability assessment subgraph
│       ├── stage4_perturbation.py      # In-silico perturbation subgraph
│       └── stage5_proteomics.py        # Transcriptome-to-proteome subgraph
│
├── agents/                             # Agent configuration per stage
│   ├── base_agent.py                   # Shared model binding, tool registry, retry logic
│   ├── v2g_agent.py                    # Stage 1: system prompt, tool list, model selection
│   ├── v2t_agent.py                    # Stage 2 configuration
│   ├── druggability_agent.py           # Stage 3 configuration
│   ├── perturbation_agent.py           # Stage 4 configuration
│   └── proteomics_agent.py             # Stage 5 configuration
│
├── tools/                              # Python callables exposed as agent tools
│   ├── finemap.py                      # SuSiE and FINEMAP subprocess wrappers
│   ├── liftover.py                     # GRCh37-to-GRCh38 coordinate conversion
│   ├── coloc.py                        # coloc and ecaviar via rpy2 or subprocess
│   ├── twas.py                         # S-PrediXcan and FUSION wrappers
│   ├── mendelian_randomization.py      # MR-Base / TwoSampleMR API calls
│   ├── gtex_api.py                     # GTEx Portal v2 REST client
│   ├── lincs_api.py                    # LINCS clue.io REST / GCTx client
│   ├── pharos_api.py                   # IDG Pharos GraphQL client
│   ├── komp2_api.py                    # IMPC REST API client
│   ├── glygen_api.py                   # GlyGen REST and SPARQL client
│   ├── motrpac_loader.py               # MoTrPAC HDF5 and Parquet data loader
│   ├── connectivity_score.py           # LINCS L1000 connectivity tau computation
│   ├── kg_query.py                     # Knowledge graph read and write (Cypher / Gremlin)
│   └── identifier_resolver.py         # Cross-ontology identifier lookup tool
│
├── knowledge_graph/                    # Graph schema, driver, and harmonization layer
│   ├── schema.py                       # Node and edge type definitions (Pydantic models)
│   │                                   #   Nodes: Variant, CredibleSet, Gene, Tissue,
│   │                                   #          CellType, Drug, Compound, Protein,
│   │                                   #          Phenotype, Pathway
│   │                                   #   Edges: MAPS_TO, COLOCALIZES_WITH, REGULATES,
│   │                                   #          TARGETS, PERTURBS, PREDICTS_BIOMARKER
│   ├── neo4j_client.py                 # Neo4j Python driver wrapper (local / self-hosted)
│   ├── neptune_client.py               # AWS Neptune Gremlin / SPARQL wrapper
│   ├── kg_factory.py                   # Runtime client selection from deployment config
│   └── harmonizer.py                   # Identifier normalization
│                                       #   Variants:  dbSNP rsID, SPDI notation
│                                       #   Genes:     Ensembl gene and transcript IDs
│                                       #   Proteins:  UniProt accession
│                                       #   Compounds: ChEMBL, PubChem CID, InChIKey
│                                       #   Phenotypes: HPO, MONDO, EFO
│                                       #   Tissues:   Uberon, GTEx tissue ontology
│                                       #   Cell types: Cell Ontology (CL)
│
├── data_access/                        # Dataset-specific I/O adapters
│   ├── access_manifest.py              # Authorization registry for controlled-access tiers
│   │                                   #   Records: dataset name, access tier,
│   │                                   #            authorized flag, consent-use codes,
│   │                                   #            credential reference
│   ├── anvil_client.py                 # AnVIL / Terra workspace API (GTEx, MoTrPAC, UDN, KF)
│   ├── cfde_portal.py                  # NIH CFDE Data Portal search and retrieval
│   ├── ega_client.py                   # EGA Htsget and data retrieval API (H3Africa)
│   ├── dbgap_client.py                 # dbGaP authorized-access data retrieval
│   ├── huggingface_loader.py           # HuggingFace Hub dataset retrieval (open datasets)
│   ├── lincs_loader.py                 # GCTx and HDF5 parsing for L1000 signature matrices
│   ├── four_dn_client.py               # 4DN Data Portal REST API (Hi-C, Micro-C, ChIP-seq)
│   ├── hubmap_client.py                # HuBMAP Data Portal REST API (single-cell atlases)
│   ├── sennet_client.py                # SenNet DCC API
│   └── s3_client.py                    # AWS S3 adapter for intermediate artifact storage
│
├── pipelines/                          # Bioinformatics workflow definitions (Nextflow)
│   ├── nextflow.config                 # AWS Batch executor config and local HPC profiles
│   ├── susie_finemap.nf                # Fine-mapping workflow (SuSiE, FINEMAP)
│   ├── coloc_analysis.nf               # Colocalization workflow (coloc, ecaviar)
│   ├── twas_analysis.nf                # TWAS workflow (S-PrediXcan, FUSION, UTMOST)
│   ├── abc_model.nf                    # Activity-by-Contact enhancer-gene scoring
│   ├── connectivity_scoring.nf         # LINCS connectivity analysis workflow
│   └── containers/
│       ├── Dockerfile.bioc             # R / Bioconductor (coloc, susieR, TwoSampleMR)
│       ├── Dockerfile.python_ml        # Python ML (predixcan, pybedtools, cyvcf2)
│       └── Dockerfile.lincs            # LINCS analysis (cmapPy, GCTx, clue.io client)
│
├── state/                              # LangGraph typed state definition
│   └── pipeline_state.py               # Pydantic model for the shared pipeline state
│                                       #   gwas_input: GWASInput
│                                       #   session_id: str
│                                       #   session_plan: SessionPlan
│                                       #   credible_sets: list[CredibleSet]
│                                       #   v2g_scores: dict[str, float]
│                                       #   eqtl_coloc: list[ColocResult]
│                                       #   twas_results: list[TWASResult]
│                                       #   druggability_rankings: list[DrugTarget]
│                                       #   connectivity_scores: list[CompoundScore]
│                                       #   biomarker_candidates: list[BiomarkerCandidate]
│                                       #   iteration_count: int
│                                       #   uncertainty_flags: list[str]
│                                       #   stage_status: dict[str, StageStatus]
│
├── config/                             # Runtime configuration
│   ├── default.yaml                    # Default thresholds, genome build, model IDs
│   ├── aws.yaml                        # AWS overrides (Bedrock ARNs, S3 buckets, SQS URLs)
│   ├── local.yaml                      # Local overrides (Neo4j URI, Ollama model, Redis URL)
│   └── secrets.py                      # Credential loading (Secrets Manager or .env)
│
├── audit/                              # Reproducibility and provenance logging
│   ├── run_logger.py                   # Structured log: tool name, version, params, hash
│   ├── artifact_store.py               # Intermediate artifact deposit to S3 or local path
│   └── provenance_graph.py             # W3C PROV-compatible provenance record generation
│
├── tests/
│   ├── unit/                           # Unit tests for tools, schema, planner parsing
│   ├── integration/                    # End-to-end stage tests with fixture data
│   └── fixtures/                       # Synthetic GWAS summary statistics (TCF7L2 locus)
│
├── docs/
│   ├── architecture.md                 # This document
│   └── demo_notebook.ipynb             # Stage 2 walkthrough using open GTEx data
│
├── pyproject.toml
├── Dockerfile                          # Agent runtime production image
├── docker-compose.yml                  # Local stack: agent + Neo4j + Redis + Streamlit
└── README.md
```

---

## GUI Layer

The graphical user interface serves two purposes: it provides the natural-language entry point through which the user initiates a session, and it presents a live monitoring surface through which the user observes stage execution, inspects intermediate results, and retrieves output artifacts.

For the open-source deployment, the interface is implemented in **Streamlit**. Streamlit is Python-native, requires no JavaScript build tooling, renders markdown natively (which is necessary for displaying the session plan), and supports streaming token output via `st.write_stream`. The interface is organized as a multi-page Streamlit application. The first page (`01_new_session.py`) presents a chat input field alongside an optional file upload widget for GWAS summary statistics. When the user submits a query, a loading indicator is shown while the planner agent processes the input; the resulting session plan is then rendered as a formatted markdown block with an approve button, an edit field, and a reject button. The second page (`02_session_status.py`) displays the execution state of each stage as a status card updated via periodic polling or Streamlit's native `st.rerun` mechanism, along with a scrollable agent thought stream. The third page (`03_results.py`) renders output tables, an interactive knowledge graph visualization built with pyvis, and download links for all output files. The fourth page (`04_session_history.py`) lists prior sessions with links to their plans and artifacts.

For the production AWS deployment, the same user-facing functionality is delivered through a **React** single-page application backed by a **FastAPI** server. The FastAPI backend exposes REST endpoints for session creation, plan submission, plan approval, and run status retrieval, as well as a WebSocket endpoint that streams LangGraph token events and stage status updates to the connected browser client in real time. This architecture supports concurrent multi-user sessions and integrates with AWS Cognito for authentication. The React frontend communicates with the FastAPI server via `axios` for REST calls and the browser's native `WebSocket` API for the event stream.

Both interface variants share the same backend planner, session management, and orchestration layers; the GUI layer is purely presentational.

---

## Planner Agent Layer

The planner agent is a dedicated LLM agent that occupies the topmost position in the orchestration hierarchy. It is invoked immediately when a user submits a natural-language query and is responsible for three sequential tasks: parsing the query into a structured plan, validating that plan against the access manifest, and writing the plan to a markdown file for human review.

**Query parsing.** The planner agent receives the user's free-text query alongside a system prompt (`planner/prompts/system_prompt.md`) that describes the five pipeline stages, the available datasets, the access manifest, and the expected output format. The agent is invoked with structured output mode: the language model is instructed to return a JSON object that conforms to the `SessionPlan` Pydantic schema defined in `planner/session_plan_schema.py`. This schema captures the fields that fully parameterize a pipeline run, including the disease or trait under investigation, the GWAS input source and genome build, the subset of stages to execute, the preferred datasets for each stage, key statistical thresholds, expected output types, and an estimated compute time. If the user's query is underspecified — for example, if no GWAS source is mentioned — the planner agent issues a clarifying question through the GUI chat interface before producing the plan.

The `SessionPlan` schema includes, among other fields, the following:

```
session_id:              str              # UUID assigned at query submission
trait:                   str              # Resolved trait label (e.g., "type 2 diabetes")
trait_efo:               str              # EFO identifier for the trait
gwas_source:             GWASSource       # Consortium name, file path or URL, sample size
genome_build:            Literal["GRCh38", "GRCh37"]
stages_to_run:           list[int]        # Subset of [1, 2, 3, 4, 5]
datasets_per_stage:      dict[int, list[str]]  # Stage index -> dataset names
parameters:              StageParameters  # Thresholds: H4_min, twas_fdr, tau_min, etc.
access_flags:            list[AccessFlag] # Datasets required but not yet authorized
expected_outputs:        list[str]        # Output artifact descriptions
estimated_compute_hours: float
```

**Plan validation.** After generating the `SessionPlan` object, `planner/plan_validator.py` cross-references every dataset listed in `datasets_per_stage` against the access manifest. Any dataset that requires controlled access and is not currently authorized is recorded as an `AccessFlag` in the plan and surfaced prominently in the rendered plan document. The user is informed of these gaps before approving the plan, allowing them to initiate data access requests in parallel with any immediately executable pipeline stages.

**Plan rendering.** `planner/plan_writer.py` converts the validated `SessionPlan` into a human-readable `session_plan.md` file stored in the session's artifact directory. The markdown document presents the proposed analysis in plain language organized by stage, lists the datasets and parameters to be used at each stage, calls out any access flags in a clearly labeled warning section, and concludes with the expected outputs and compute estimate. This file constitutes both the human-review document presented in the GUI and the formal record of the session's analytical intent in the audit trail.

**Human-in-the-loop checkpoint.** The LangGraph graph for the planner subgraph includes an `interrupt` node between plan generation and task dispatch. When the graph reaches this node, execution suspends and control returns to the GUI. The session transitions to a `PENDING_APPROVAL` status. The user may approve the plan as written, submit an edited version of the markdown document (which the planner agent re-parses into a revised `SessionPlan`), or reject the plan and submit a new query. Only upon explicit approval does the graph advance past the interrupt node and dispatch tasks to the stage subagents.

---

## Session Management and Task Dispatch Layer

**Session management.** Each user query initiates a session identified by a UUID. The session object records the query text, the session plan, the execution status of each stage, and references to all output artifacts. Sessions are persisted in SQLite (open-source deployment) or Amazon DynamoDB (AWS deployment) by `session/session_store.py` via a deployment-agnostic adapter interface exposed by `session/session_manager.py`. Sessions persist across server restarts and can be resumed if execution is interrupted.

**Task dispatch.** When the planner's interrupt node is cleared, `session/task_dispatcher.py` converts the approved `SessionPlan` into a sequence of typed task messages. Each task message specifies a stage index, the relevant subset of the `PipelineState` that the stage requires as input, and the parameters specified in the plan. These messages are enqueued through the adapter in `session/task_queue.py`. In the open-source deployment, the queue is implemented with **Celery** backed by **Redis**; each task message is consumed by a Celery worker that instantiates the corresponding LangGraph stage subgraph. In the AWS deployment, task messages are published to an **SQS** queue and consumed by ECS Fargate task definitions that execute the stage subgraphs. In both cases the stage workers stream progress events back to the WebSocket handler, which forwards them to the connected GUI client.

Stages that have no inter-stage dependency on the output of an earlier stage — specifically, Stage 3 (Druggability) can begin as soon as the gene list from Stage 1 is available, independently of Stage 2 — are dispatched concurrently. The task dispatcher inspects the dependency graph encoded in the `SessionPlan` and submits independent stage tasks in parallel.

---

## Orchestration Layer: LangGraph

The orchestration layer is implemented using LangGraph. The top-level pipeline is defined as a `StateGraph` in `workflows/gwas_to_biomarker.py`. Each of the five analytical stages is compiled as a subgraph that exposes a single entry node and a single exit node; the top-level graph composes these subgraphs as nodes and connects them with typed conditional edges.

The shared state object, defined in `state/pipeline_state.py`, is a Pydantic model whose fields correspond to the principal evidence structures produced and consumed across stages. Every node in every subgraph receives the current state as input and returns a partial state update as output; LangGraph merges these updates according to the declared reducer functions. Uncertainty flags accumulated during execution trigger conditional edges that route the agent back to an earlier stage for supplementary data retrieval rather than proceeding forward with insufficient evidence.

The agent at each stage is configured in the corresponding `agents/` module. Each agent binds a language model (Claude via Anthropic API or Amazon Bedrock), a stage-specific system prompt that describes the analytical objective and the available tools, and a tool registry drawn from the `tools/` directory. The model and tool list are selected per stage to minimize token overhead and to constrain the agent's action space to tools relevant to that stage's scope. LangGraph's native streaming interface emits token events and node transition events that are forwarded to the GUI progress stream.

---

## Knowledge Graph Layer

The knowledge graph is the shared persistent memory of the pipeline. The schema, defined in `knowledge_graph/schema.py`, specifies ten node types and six edge types. Edge properties carry the calibrated uncertainty scores produced at each stage: variant-to-gene edges carry the multi-modal posterior score; colocalization edges carry the H4 posterior probability; TWAS edges carry the Z-score and cross-validation R-squared; perturbation edges carry the connectivity tau and p-value; biomarker edges carry the hazard ratio, confidence interval, and cohort identifier.

The client is selected at runtime by `knowledge_graph/kg_factory.py` based on the active deployment configuration. For open-source local deployment the client is `neo4j_client.py`, which wraps the official `neo4j` Python driver and exposes read and write methods as Cypher transactions. For AWS deployment the client is `neptune_client.py`, which wraps the `gremlinpython` and `sparqlwrapper` libraries against an Amazon Neptune endpoint. The exposed interface is identical in both cases, allowing the agent tools in `tools/kg_query.py` to remain deployment-agnostic.

Identifier normalization is handled by `knowledge_graph/harmonizer.py`. Before any entity is written to the graph, the harmonizer resolves it to its canonical identifier in the appropriate ontology and verifies that no duplicate node exists under an alternative identifier. Cross-ontology mappings are maintained as a local reference table that is updated at pipeline initialization from the relevant ontology REST APIs.

---

## Data Access Layer

Each dataset in the plan has a dedicated adapter module in `data_access/`. Adapters implement a common interface with three methods: `check_authorization`, which consults the access manifest; `list_available_assets`, which queries the dataset's index for available file types and cohorts; and `retrieve`, which downloads or streams the requested data to the artifact store. The access manifest in `access_manifest.py` is a YAML-backed registry loaded at startup that records, for each controlled-access dataset, whether authorization has been obtained, the applicable consent-use codes, and the environment variable or AWS Secrets Manager key from which credentials are retrieved. Any tool call that attempts to retrieve a controlled-access resource is intercepted by the manifest check; if authorization is not recorded, the tool returns a structured error that the agent must route to a human-in-the-loop node for resolution.

---

## Bioinformatics Compute Layer

The bioinformatics compute layer is implemented in Nextflow. Each analytical operation that is computationally intensive, statistically self-contained, and deterministic given fixed inputs is implemented as a Nextflow process rather than as a Python function called inline by the agent. This includes fine-mapping (SuSiE, FINEMAP), colocalization (coloc, ecaviar), TWAS (S-PrediXcan), Activity-by-Contact scoring, and LINCS connectivity analysis. The agent invokes these workflows via subprocess tool calls that pass input file paths and parameter dictionaries, then await completion and parse the structured output files into the appropriate Pydantic types for state update.

Containerized execution environments are defined in `pipelines/containers/`. The Bioconductor container packages R with susieR, coloc, TwoSampleMR, and related packages; the Python ML container packages predixcan, pybedtools, and cyvcf2; the LINCS container packages cmapPy and the CLUE API client. All containers are pinned to specific image digests in `nextflow.config` to ensure computational reproducibility.

---

## Deployment Configurations

### AWS Deployment

The AWS deployment uses Amazon Bedrock for LLM inference, Amazon Neptune for the knowledge graph, Amazon S3 for artifact storage, and AWS Batch for Nextflow job execution. The planner and stage agent runtimes are containerized and deployed on Amazon ECS Fargate. The FastAPI backend is deployed as a separate ECS service behind an Application Load Balancer with WebSocket support enabled. Session state is persisted in DynamoDB. Task messages flow through SQS between the planner service and the stage worker services. Credentials for controlled-access datasets are stored in AWS Secrets Manager. IAM roles govern access between services; no long-lived API keys are embedded in the runtime environment.

### Open-Source GitHub Deployment

The open-source deployment runs on any Linux system with Docker and Java available. The local development stack is defined in `docker-compose.yml` and starts five containers: the Streamlit GUI, the FastAPI backend, a Neo4j community edition instance, a Redis instance for Celery, and the agent runtime. LLM inference is directed to the Anthropic API or to a locally hosted model served by Ollama. Nextflow jobs are submitted to the local execution environment by default and can be redirected to an institutional SLURM cluster by modifying `nextflow.config`. Credentials for controlled-access datasets are loaded from a `.env` file excluded from version control.

---

## Recommended Implementation Sequence

The following sequence minimizes integration risk while delivering testable, demonstrable behavior at each milestone.

**Milestone 1: Core infrastructure.** Implement the knowledge graph schema, Neo4j client, and identifier harmonizer. Define the `PipelineState` and `SessionPlan` Pydantic models. Set up the `docker-compose.yml` stack. This establishes the persistence and configuration foundation on which all other components depend.

**Milestone 2: Planner agent and GUI scaffold.** Implement the planner agent with structured output mode against a small set of example queries. Implement `plan_writer.py` and verify that a `session_plan.md` is generated correctly. Build the Streamlit pages for query input and plan review. Test the human-in-the-loop interrupt node in LangGraph in isolation. This milestone delivers the user-facing entry point and validates the NLU parsing before any pipeline compute is involved.

**Milestone 3: Stage 2 end-to-end.** Implement the GTEx API tool, the coloc tool via rpy2, and the Stage 2 LangGraph subgraph. Connect the task dispatcher to the Stage 2 worker. Run a complete Stage 2 session from the GUI — submitting a query about TCF7L2 and type 2 diabetes, approving the plan, and observing colocalization results written to Neo4j and displayed on the results page. This milestone validates the full stack from GUI to knowledge graph for a single stage.

**Milestone 4: Stage 1.** Implement the fine-mapping Nextflow workflow, the 4DN and HuBMAP API clients, and the Stage 1 subgraph. Stage 1 produces the credible set input that Stage 2 consumes, closing the upstream dependency and enabling end-to-end runs from raw GWAS summary statistics.

**Milestone 5: Stages 3, 4, and 5.** Implement the remaining three stages in order. Stage 3 (Druggability) has no Nextflow dependency and can be completed quickly using the Pharos GraphQL client. Stage 4 requires the LINCS GCTx loader and the connectivity scoring workflow. Stage 5 draws on the MoTrPAC and A2CPS data adapters.

**Milestone 6: AWS deployment.** Migrate from the local docker-compose stack to AWS by activating the `aws.yaml` configuration profile, deploying the ECS services, provisioning the Neptune cluster and SQS queues, and validating that the full pipeline executes on AWS Batch.

---

## Technology Summary

| Layer | Open-Source Deployment | AWS Deployment |
|---|---|---|
| GUI Frontend | Streamlit | React (served via S3 + CloudFront) |
| GUI Backend | FastAPI + Uvicorn | FastAPI on ECS Fargate + ALB |
| Real-time Progress | Streamlit `st.rerun` / SSE | WebSocket via ALB |
| Planner Agent | LangGraph + Claude API / Ollama | LangGraph + Amazon Bedrock |
| Session Store | SQLite | Amazon DynamoDB |
| Task Queue | Celery + Redis | Amazon SQS |
| Stage Orchestration | LangGraph (Python) | LangGraph on ECS Fargate |
| LLM Inference | Anthropic API / Ollama | Amazon Bedrock (Claude) |
| Knowledge Graph | Neo4j Community (Docker) | Amazon Neptune |
| Artifact Storage | Local filesystem | Amazon S3 |
| Bioinformatics Compute | Nextflow (local / SLURM) | Nextflow on AWS Batch |
| Containerization | Docker / Docker Compose | Docker on ECR / ECS |
| Credential Management | .env file | AWS Secrets Manager |
| Provenance Logging | Local PROV-JSON files | S3 PROV-JSON + CloudWatch |
| Identifier Harmonization | Local reference tables (SQLite) | Same, cached in ElastiCache |
| Dependency Management | pyproject.toml (uv or pip) | Same, pinned in container image |

---

## Key External Dependencies

The orchestration and agent layer depends on `langgraph` (>=0.2), `langchain-anthropic` or `langchain-aws` for Bedrock, and `pydantic` (v2). The GUI layer depends on `streamlit` (>=1.35) for open-source deployment and `fastapi`, `uvicorn`, and `websockets` for the production backend. The knowledge graph layer depends on `neo4j` (>=5.0) or `gremlinpython` for Neptune. The session management layer depends on `celery` and `redis` for open-source deployment and `boto3` (SQS and DynamoDB) for AWS. The bioinformatics tool layer depends on `rpy2`, `cyvcf2`, `pybedtools`, `cmapPy`, `pandas`, and `pyarrow`. The data access layer depends on `firecloud` or `terra-notebook-utils` for AnVIL and `boto3` for S3 and Secrets Manager. Reproducibility tooling depends on `mlflow` for experiment tracking and `dvc` for large-file versioning. The knowledge graph visualization component in the GUI depends on `pyvis`.
