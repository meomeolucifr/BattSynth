"""
LangGraph workflow for synthesis planning:
retrieval -> extraction -> reasoning -> END.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langgraph.graph import END, StateGraph

try:
    from .models import SynthesisState
    from .nodes.extraction import extraction_node
    from .nodes.reasoning import reasoning_node
    from .retriever import retriever_agent
except (ModuleNotFoundError, ImportError):
    from models import SynthesisState
    from nodes.extraction import extraction_node
    from nodes.reasoning import reasoning_node
    from retriever import retriever_agent


def _normalize_retrieved_papers(papers: List[Any]) -> List[Dict[str, Any]]:
    """
    Normalize retrieval output into the dict schema expected by extraction_node.

    retriever_agent currently returns List[str] for many paths; extraction_node
    expects List[Dict[str, Any]] with optional keys like title/abstract/full_text.
    """
    normalized: List[Dict[str, Any]] = []
    for i, paper in enumerate(papers, start=1):
        if isinstance(paper, dict):
            normalized.append(paper)
            continue
        if isinstance(paper, str):
            normalized.append(
                {
                    "title": f"retrieved_paper_{i}",
                    "full_text": paper,
                }
            )
            continue
        normalized.append(
            {
                "title": f"retrieved_paper_{i}",
                "full_text": str(paper),
            }
        )
    return normalized


def retrieval_node(state: SynthesisState) -> Dict[str, Any]:
    """
    LangGraph node: retrieve synthesis-relevant papers and map into synthesis_papers.
    """
    retrieval_state = dict(state)
    retrieval_state["retrieval_skill"] = "synthesis"
    result = retriever_agent(retrieval_state)
    papers = _normalize_retrieved_papers(list(result.get("retrieved_papers") or []))
    return {
        "synthesis_papers": papers,
        "synthesis_status": "extracting",
    }


def build_synthesis_graph():
    """Create and compile the synthesis sub-graph."""
    workflow = StateGraph(SynthesisState)
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("extraction", extraction_node)
    workflow.add_node("reasoning", reasoning_node)

    workflow.set_entry_point("retrieval")
    workflow.add_edge("retrieval", "extraction")
    workflow.add_edge("extraction", "reasoning")
    workflow.add_edge("reasoning", END)
    return workflow.compile()


def run_synthesis_graph(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience runner for one-shot invocation."""
    graph = build_synthesis_graph()
    return graph.invoke(initial_state)