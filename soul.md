# soul.md — Methodology and Design Rationale

*Last reviewed: 2026-07-08. This document is a portable statement of the reasoning behind this framework. It is written to be read by a person, or handed to an LLM client, as the seed for building a comparable pipeline elsewhere. Read the ["What this document does not give you"](#9-what-this-document-does-not-give-you) section before treating any statement here as a recipe.*

---

## 0. What this document is, and is not

This is a *design-rationale and methods* document, not an operating manual and not a runnable specification. It records **why** the pipeline is shaped the way it is: the study-design philosophy, the tool-selection reasoning, the methodological defaults, and the architectural invariants. It deliberately omits exact tool flags, file-format schemas, and installation steps, because those belong with the code and drift from prose the moment either changes.

The correct expectation: reading this lets you reconstruct the *thinking* and build *your own* pipeline informed by it. It does not let you skip the engineering — the tooling, reference data, and validation are yours to supply.

Operating instructions for the reference implementation live in `README.md`; this document is repository-independent by design.

---

## 1. Problem class and intended reader

The problem class is **translational post-analysis**: taking a primary genomic or statistical result and driving it toward mechanistic and therapeutic interpretation. Two concrete instances are implemented:

- **Post-GWAS interpretation** — from summary statistics to fine-mapped causal
  variants, to genes, to causal validation, to druggability.
- **Sequencing analysis** — whole-exome (WES) germline variant calling, and
  single-cell RNA-seq (scRNA) cell-level characterisation.

The distinguishing design commitment is that an **LLM agent orchestrates** the pipeline rather than a static workflow graph. The intended reader is someone building an LLM-orchestrated scientific pipeline who wants the reasoning, not the button-presses.

---

## 2. Foundational philosophy

These are the load-bearing convictions. Each is stated as a decision, its rationale, the alternative rejected, and the assumption under which it holds (its failure mode).

### 2.1 Orchestrate with an agent, compute with tools

- **Decision.** An LLM plans and dispatches; it never performs computation itself. Every action is a typed tool call whose implementation is ordinary code.
- **Rationale.** Inputs are heterogeneous and the decisions are judgment-laden — which eQTL tissue matches the trait, whether a study is case-control or a group comparison, whether a second trait warrants a two-sample MR. A negotiable natural-language plan suits this better than a fixed graph.
- **Rejected alternative.** A pure workflow manager (Snakemake, Nextflow, WDL). These are excellent for fixed DAGs but cannot present a plan, absorb a mid-run correction, or classify an unknown input by inspection.
- **Assumption / failure mode.** Requires a model competent at tool-use and instruction-following. It degrades ungracefully with a weak model: malformed tool arguments, skipped steps, or plausible-sounding but wrong scientific choices. The separation in §2.2 is what keeps that degradation observable.

### 2.2 Separate orchestration from computation, absolutely

- **Decision.** The agent's only interface to the world is the tool schema. No agent writes to disk except through a small number of explicit, audited tools.
- **Rationale.** This buys three things at once: **testability** (the compute layer can be driven by deterministic code with no model in the loop), **auditability** (every decision is a logged tool call), and **substitutability** (the model can be swapped without touching the science).
- **Rejected alternative.** Letting the model emit and execute code directly. Faster to prototype, but unauditable, non-deterministic, and unsafe.

### 2.3 Checkpoint first, and automatically

- **Decision.** Every heavy step persists its result to a run checkpoint the instant it completes, via a completion callback — not at the end of the run, and not because the model remembered to save.
- **Rationale.** Real runs are long and interruptible. A checkpoint written per-step makes a run resumable from any point and lets a different entrypoint (a browser session, a fresh CLI invocation) pick up where another left off.
- **Assumption / failure mode.** The checkpoint is the source of truth for "what is done." If a step's outputs are mutated out-of-band, the checkpoint lies. Steps must therefore be effectively idempotent with respect to their recorded outputs.

### 2.4 Classify by content, never by name

- **Decision.** Input type is determined by inspecting file *content*, never by filename or extension.
- **Rationale.** Filenames are supplied by users and are routinely wrong or absent. A `.txt` may be summary statistics; a directory may be a multimodal cohort.
- **Failure mode.** Content inspection has its own blind spots (see §5 on bulk vs single-cell RNA); the classifier must fail *loudly and specifically* when it cannot decide, rather than guessing.

### 2.5 Honest failure over fabricated success

- **Decision.** When a real analysis cannot run — a missing binary, an absent reference panel, an unreadable input — the step raises an error that names exactly what is missing. It never silently substitutes a weaker method or synthetic output.
- **Rationale.** In a scientific pipeline a silent fallback is worse than a crash: it produces a result that looks valid and is not.

### 2.6 A mock path that is contract-identical to the real path

- **Decision.** For the domains where it is affordable (sequencing analysis), each step has a *mock* mode that returns synthetic-but-plausible metrics, deterministically seeded from a hash of the input, alongside a *real* mode that shells out to the genuine tool. Both have identical signatures and output shapes.
- **Rationale.** This makes the orchestration demonstrable and testable end-to-end without a heavy toolchain, while guaranteeing that enabling real mode later changes nothing about the tool-calling contract. Determinism means repeated mock runs on the same input agree, so the mock path is a stable test fixture.
- **Caveat that must travel with this idea.** Mock output is for wiring and demonstration only. It is not data. Any document or UI that surfaces it must say so (see §9).

---

## 3. Architectural invariants

A faithful re-implementation may differ in language, framework, and file layout, but should preserve these invariants. They are the structural expression of §2.

1. **A three-layer agent hierarchy.**
   - *Planner* — inspects the input, detects the domain, presents a plan, dispatches the work, then triggers reporting.
   - *Workers / Stages* — one short-lived agent per branch or stage, each running its ordered steps and returning a findings summary.
   - *Reporter* — a single shared agent that reads the checkpoint and synthesises the final report, branching on the recorded domain for domain-specific content.
2. **Every heavy step runs through an asynchronous job queue** (`start → poll → result`), even in mock mode, so the model's contract is identical regardless of how long the underlying work takes and regardless of mode.
3. **Checkpointing is automatic, not agent-driven** — wired as a completion callback, so the on-disk state is always current without the model issuing a save.
4. **Domains are self-contained.** Domain packages do not import from one another; the shared core imports from the domains in one direction only. This is what allows a domain to be read, tested, and extended in isolation, and a new domain to be added without touching the core.
5. **The provider is an abstraction with a minimal surface** (send user text, send tool results, take one step). Tool schemas are always passed in explicitly; the provider layer never knows the domain. Transient overloads retry down a per-vendor fallback model list.
6. **One checkpoint schema with a domain discriminator.** A single persisted record format serves both domains; a `domain` field written at classification time is what lets a resumed run or a downstream reporter know which logic applies, even if the run was interrupted immediately after classification.

---

## 4. Domain methodology I — Post-GWAS interpretation

This is the richer of the two domains and the clearest illustration of the "evidence-escalation" design. The chain proceeds in three mandatory stages plus one optional stage, and each stage reads the previous stage's outputs back out of the checkpoint rather than receiving them as direct arguments.

### 4.1 Why the stage ordering is V2G → MR → Drug

The ordering is a deliberate escalation of evidential burden. Each stage is only worth running on what survived the last:

1. **V2G (variant-to-gene)** — *localise the signal.* Establish which variants carry the association and which genes they plausibly act through.
2. **MR (causal validation)** — *test the causal claim.* A gene near a signal is not a causal gene; colocalization and Mendelian randomization are what separate causation from mere proximity and linkage.
3. **Drug (druggability)** — *assess tractability.* Only for genes that survived causal validation is it meaningful to ask whether they can be drugged.

Running these in the reverse order, or in parallel, would waste the expensive causal analysis on candidates that localisation alone would have discarded.

### 4.2 V2G internals: format → COJO → SuSiE

- **format first.** Summary statistics arrive in inconsistent shapes; everything downstream assumes one normalised representation. Normalise once, at the boundary.
- **COJO before SuSiE.** A single locus frequently harbours *multiple independent* association signals masked by linkage disequilibrium. Conditional analysis (COJO) resolves these into conditionally-independent signals *before* fine-mapping, so that fine-mapping is applied to a genuinely single-signal region rather than smearing a credible set across two merged peaks.
- **SuSiE for fine-mapping.** It yields credible sets and per-variant posterior inclusion probabilities, which is the currency the later stages consume (a ranked, probabilistic shortlist rather than a single lead SNP).
- **Per-chromosome COJO as a memory-bounded equivalence.** A genome-wide reference panel of tens of millions of variants will not load whole on a modest machine. Running COJO one chromosome at a time against per-chromosome reference files, then concatenating, is provably equivalent to a genome-wide run (conditional analysis does not cross chromosomes) while staying within memory. This is an engineering accommodation with zero methodological cost — the kind worth documenting precisely so a re-implementer does not mistake it for an approximation.
- **±500 kb fine-mapping window.** A locus is defined as a window around each conditionally-independent signal, wide enough to capture the local LD block without bleeding into neighbouring signals.

### 4.3 MR internals: SMR/HEIDI → optional two-sample MR → network

- **SMR with the HEIDI test** is used to ask whether a variant's effect on the trait is mediated by its effect on a gene's expression (colocalization), and critically to *distinguish causal pleiotropy from linkage* — two nearby but distinct variants, one affecting expression and one affecting the trait, would otherwise masquerade as a causal gene.
- **Tissue-matching the eQTL panel to the trait is non-negotiable.** Colocalization against the wrong tissue is uninterpretable. A liver-disease trait is validated against liver eQTLs. This is the single most common place where a mechanically-correct run produces a scientifically-meaningless answer, so it is stated as a hard rule.
- **Two-sample MR is optional and trait-directed.** When a second, downstream trait is of interest (does trait A causally contribute to disease B?), a two-sample MR tests that specific edge. It is not run speculatively.
- **The causal network is assembled from real stage outputs**, not placeholders — an edge asserted in the network must trace to an actual SMR or MR result.

### 4.4 Drug internals

Druggability is a lookup against a curated target-tractability resource for each gene that reached the causal network. The design point is that this stage is cheap and deterministic relative to the analysis above it, and is deliberately last so it is only ever run on validated candidates.

### 4.5 The optional PRS stage, and why it is decoupled

- A polygenic risk score depends only on the normalised summary statistics and a genotyped target cohort — not on any output of the MR or Drug stages. It is therefore dispatchable any time after V2G, independently of the rest of the chain.
- The method is clumping-and-thresholding (select LD-independent index variants at a p-value threshold, weight them, score a cohort). This is chosen as a *transparent baseline*, not a state-of-the-art predictor.
- **Honest limitation.** Clumping-and-thresholding is not a jointly-fit predictive panel (it is not penalised regression over correlated variants), and the framework does not, at present, produce a validated accuracy metric for it. A reader wanting a predictive panel should treat this stage as a starting point, not a finished product.

---

## 5. Domain methodology II — Sequencing analysis

### 5.1 WES (germline)

The branch is QC → alignment → variant calling, one sample at a time, checkpointed after each step. **A disclosed approximation:** somatic (paired tumour/normal) calling is not implemented; the germline pipeline is used as a stand-in. Any report over tumour data must state this, because presenting germline calls as somatic findings would be a scientific error, not merely a missing feature.

### 5.2 scRNA

The branch is cell-annotation → clustering → differential-expression → GSEA. The ordering reflects that **batch-corrected clustering precedes differential expression**: comparisons drawn across un-corrected batches confound technical and biological variation. GSEA runs on the differential-expression result to move from a gene list to an interpretable pathway-level statement.

### 5.3 The classifier's known blind spot

Content-based detection (§2.4) recognises single-cell RNA and WES inputs; **bulk RNA-seq is not recognised.** This is a deliberate scope boundary, not a bug, and is called out so a re-implementer does not assume coverage that is absent.

---

## 6. Methodological defaults

Defaults encode judgment and should be *changed deliberately*, not treated as fixed law. The table records the default and the condition under which to revisit it. Exact numeric thresholds that live in the step code (p-value cut-offs, MAF filters) are intentionally not restated here, because they are the first thing to drift — consult the step implementation and set them per run.

| Parameter | Default | Justification | Change when |
|---|---|---|---|
| Stage ordering (GWAS) | V2G → MR → Drug (+ optional PRS after V2G) | Evidence escalation; expensive stages run only on survivors | Never, without re-reading §4.1 |
| COJO execution | Per-chromosome, concatenated | Memory-bounded exact equivalence to genome-wide | Panel + RAM comfortably fit a genome-wide run |
| Fine-mapping window | ±500 kb around each independent signal | Captures the LD block without merging signals | Unusually long- or short-range LD |
| eQTL tissue | Matched to the trait's biology | Colocalization is otherwise uninterpretable | The causal tissue is genuinely unknown — then justify explicitly |
| Two-sample MR | Off unless a downstream trait is named | Not run speculatively | A specific trait-to-trait hypothesis exists |
| Sequencing execution mode | Mock | Demonstrable and testable without a toolchain | Real analysis is intended and tools are installed |
| Confirmation gating | Auto-approve (which keeps sequencing in mock) | Safe default for a demo | Real, resource-consuming actions are intended |

---

## 7. Tooling choices

The instrument for each task, and the reason. A re-implementation may substitute equivalents, but should understand what each choice is *for*.

| Task | Instrument | Why this one |
|---|---|---|
| Conditional GWAS analysis | GCTA-COJO | Standard, resolves multiple independent signals per locus |
| Fine-mapping | SuSiE | Credible sets + posterior inclusion probabilities, not a single lead SNP |
| eQTL colocalization | SMR + HEIDI | Separates causal pleiotropy from linkage |
| Causal trait-trait test | Two-sample MR | Directed causal estimate between traits |
| Druggability | Curated target-tractability resource | Known-drug and tractability evidence per gene |
| Polygenic score | Clumping + thresholding | Transparent, interpretable baseline |
| WES calling | Established germline caller | Well-validated germline workflow |
| scRNA processing | Standard single-cell stack (clustering, batch correction, enrichment) | Community-standard, reproducible |

---

## 8. Execution-environment philosophy

Three environment decisions are load-bearing and easy to omit from a naïve port:

- **Environment isolation by capability.** Heavy statistical-genetics binaries (the conditional-analysis, fine-mapping, and MR toolchain) live in a separate environment from the orchestration Python. The agent shells into that environment per command. This keeps the orchestration layer lightweight and lets the heavy stack be installed, versioned, and reasoned about independently.
- **Explicit UTF-8 everywhere.** Model output contains Greek letters, inequality signs, and arrows. On a non-Latin default locale this crashes naïve I/O. Encoding is forced explicitly at every entrypoint and file operation. Omitting this produces failures that are baffling until traced to the locale.
- **A cross-boundary execution backend where the host cannot run the tools.** On the primary development machine the tools cannot run natively, so commands are shelled out to a POSIX subsystem, which imposes a path-translation discipline (tool arguments must be expressed in the subsystem's path space, not the host's). A re-implementer on a uniform platform can drop this, but should recognise that *where a tool runs* and *whose paths it sees* is a real design axis, not an afterthought.

---

## 9. What this document does not give you

Stated plainly, so the document cannot be mistaken for more than it is:

1. **It is not runnable.** There is no substitute here for the tool flags, file schemas, and glue code. Philosophy does not execute.
2. **It does not close the reproducibility gap.** Reconstructing behaviour requires the actual tools, pinned versions, and reference data (LD panels, eQTL catalogues, annotation resources), none of which prose can supply.
3. **The default execution is mock, for sequencing.** Out of the box, sequencing metrics are synthetic and deterministic — for wiring and demonstration, not for interpretation.
4. **Several capabilities are approximations or absent.** Somatic calling is approximated by the germline path; trajectory, cell-cell communication, mutational signatures, and copy-number analysis are not implemented; bulk RNA-seq is not recognised; the PRS stage is a baseline without a validated accuracy metric. A report built on this framework must disclose these where they bear on the claim.
5. **It carries no validation.** Nothing here asserts that the pipeline's outputs are correct for your data. That is established by you, on your data, against ground truth.

---

## 10. Adapting this to a new domain

The extensibility contract follows directly from §3.4 (self-contained domains). Adding a third domain means:

1. A new self-contained domain package: its worker/stage agents, its prompts, its step library, and its own tool schemas and dispatch — importing nothing from the other domains.
2. A new inspection tool the Planner can call, and a new dispatch tool it routes to.
3. Touching the shared core *only* if the new domain genuinely needs a new checkpoint field. If it does not, the core does not change.

If adding a domain forces edits across the core, that is a signal the domain boundary is wrong, not that the core needs loosening.

---

## 11. Staleness policy

Prose and code diverge unless something binds them. This document is bound by the following rule, and a reader should trust it only to the extent the rule has been kept:

> **`soul.md` is a specification the code is expected to satisfy, at the altitude of philosophy and methodology — not at the altitude of parameters.** When a *design decision or methodological stance* changes, this document is updated in the same change. Parameter-level facts are deliberately delegated to the code and are not mirrored here, precisely so that this document does not rot every time a threshold is tuned.

If you are reading this long after the review date at the top, verify the invariants in §3 against the current code before relying on them, and treat §4–§8 as the intended methodology rather than a guaranteed description of the present implementation.
