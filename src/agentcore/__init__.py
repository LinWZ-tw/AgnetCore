"""Shared core for the merged translational-agent framework.

Domain-specific pipelines (bioinformatics WES/scRNA, post-GWAS V2G/MR/Drug)
live under `agentcore.domains.*` and are routed to by a single Planner. This
package holds only infrastructure common to every domain: LLM provider
abstraction, background job queue, checkpoint persistence, and the web chat
session wrapper.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = REPO_ROOT / "results"
TOOLS_DIR = REPO_ROOT / "tools"

# Conda environments used by domain "real mode" steps that shell out to
# external bioinformatics tools. Not needed for mock-mode runs.
WES_CONDA_ENV = "wes"
FINEMAP_CONDA_ENV = "finemap"
GWASAGENT_CONDA_ENV = "gwasagent"
