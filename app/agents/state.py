"""AgentState TypedDict — shared state contract for all LangGraph nodes."""

from __future__ import annotations

from typing import Annotated, Any, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Shared state passed between LangGraph nodes.

    Fields
    ------
    messages:
        Full conversation history managed by LangGraph's ``add_messages``
        reducer; new messages are appended automatically.
    query:
        The current user query string (extracted from the last human message).
    documents:
        Retrieved document chunks produced by the Retriever node.  Each entry
        is a dict with keys: ``text``, ``file_name``, ``chunk_index``,
        ``category``, ``doc_id``, ``score``.
    intent:
        Intent label set by the Planner node.
        One of ``"CONVERSATIONAL"`` or ``"BANKING_POLICY_QUERY"``.
    thought_process:
        Ordered list of reasoning step strings logged by each node so the
        Responder and API can surface agent reasoning to the UI.
    thread_id:
        Session identifier forwarded from the API request; used by
        ``MemorySaver`` to partition conversation history across threads.
    filters:
        Optional metadata filters forwarded from the API request.
        Dict with optional keys ``category`` and ``file_name``.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    documents: list[dict[str, Any]]
    intent: str
    thought_process: list[str]
    thread_id: str
    filters: Optional[dict[str, Optional[str]]]
