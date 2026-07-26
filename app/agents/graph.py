"""LangGraph agent graph — wires Planner → Retriever/Responder with MemorySaver."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes.planner import planner_node
from app.agents.nodes.retriever import retriever_node
from app.agents.nodes.responder import responder_node
from app.agents.state import AgentState
from app.core.logging import get_logger

logger = get_logger(__name__)


def _route_after_planner(state: AgentState) -> Literal["retriever", "responder"]:
    """Conditional edge: route to retriever for policy queries, else direct to responder."""
    intent = state.get("intent", "BANKING_POLICY_QUERY")
    if intent == "CONVERSATIONAL":
        logger.debug("Graph routing: planner → responder (conversational)")
        return "responder"
    logger.debug("Graph routing: planner → retriever (banking policy query)")
    return "retriever"


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph StateGraph.

    Graph topology:
        START → planner → (retriever → responder | responder) → END

    The MemorySaver checkpoint backend persists state keyed by ``thread_id``
    so multi-turn conversations retain context across API calls.
    """
    graph = StateGraph(AgentState)

    # Register nodes.
    graph.add_node("planner", planner_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("responder", responder_node)

    # Edges.
    graph.add_edge(START, "planner")
    graph.add_conditional_edges(
        "planner",
        _route_after_planner,
        {"retriever": "retriever", "responder": "responder"},
    )
    graph.add_edge("retriever", "responder")
    graph.add_edge("responder", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


@lru_cache(maxsize=1)
def get_graph():
    """Return a cached compiled graph instance (built once at startup)."""
    logger.info("Building LangGraph agent graph")
    return build_graph()
