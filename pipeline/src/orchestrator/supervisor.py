import structlog
from langgraph.graph import StateGraph, END

from src.orchestrator.state import OrchestratorState
from src.agents.scribe_agent import run_scribe_agent
from src.agents.critic_agent import run_critic_agent
from src.agents.enricher_agent import run_enricher_agent
from src.agents.publisher_agent import run_publisher_agent

logger = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Conditional Routing Functions
# ─────────────────────────────────────────────────────────────────────────────

def router_critic_next(state: OrchestratorState) -> str:
    """
    Decides the next node to execute after the Critic node audits the review.
    """
    status = state.get("status")
    attempts = state.get("attempt_count", 0)
    
    if status == "enriching":
        logger.info("Supervisor Routing: Critic passed. Routing to Enricher.")
        return "enricher"
    elif status == "rejected":
        if attempts >= 2:
            logger.error("Supervisor Routing: Max retry attempts (2) reached or failed job. Terminating job.", job_uuid=str(state.get("job_uuid")))
            return "end"
        logger.warn("Supervisor Routing: Critic rejected. Routing back to Scribe for rewrite.")
        return "scribe"
    else:
        logger.error("Supervisor Routing: Job failed during Critic stage. Terminating.")
        return "end"

def router_publisher_next(state: OrchestratorState) -> str:
    """
    Decides the next node after the Publisher node receives a Human Review update.
    """
    status = state.get("status")
    if status == "approved":
        logger.info("Supervisor Routing: Review approved by human editor. Job complete.")
        return "end"
    elif status == "rejected":
        logger.warn("Supervisor Routing: Review rejected by human editor. Routing back to Scribe.")
        return "scribe"
    else:
        logger.error("Supervisor Routing: Job failed during Publisher stage. Terminating.")
        return "end"

# ─────────────────────────────────────────────────────────────────────────────
# LangGraph Workflow Construction
# ─────────────────────────────────────────────────────────────────────────────

workflow = StateGraph(OrchestratorState)

# 1. Register Agent Nodes
workflow.add_node("scribe", run_scribe_agent)
workflow.add_node("critic", run_critic_agent)
workflow.add_node("enricher", run_enricher_agent)
workflow.add_node("publisher", run_publisher_agent)

# 2. Set Entry Point
workflow.set_entry_point("scribe")

# 3. Add Flat Connections
workflow.add_edge("scribe", "critic")
workflow.add_edge("enricher", "publisher")

# 4. Add Conditional Routing Edges
workflow.add_conditional_edges(
    "critic",
    router_critic_next,
    {
        "enricher": "enricher",
        "scribe": "scribe",
        "end": END
    }
)

workflow.add_conditional_edges(
    "publisher",
    router_publisher_next,
    {
        "end": END,
        "scribe": "scribe"
    }
)

# 5. Compile state machine
pipeline_app = workflow.compile()
logger.info("LangGraph Orchestrator Supervisor compiled successfully.")
