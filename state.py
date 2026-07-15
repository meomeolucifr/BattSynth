"""
State definitions for the Synthesis Agent.
"""

import operator
from typing import Annotated, List, Dict, Optional, Literal, TypedDict, Any, Union


class ExperimentRecord(TypedDict):
    """Structured record of a single experiment iteration."""
    formula: str
    cif_data: str
    cif_path: Optional[str]
    properties: Dict[str, Union[float, List[float], Any]]
    valid: bool
    error_message: Optional[str]
    tools_used: Optional[List[str]]


class AgentState(TypedDict):
    """
    Minimal agent state for the synthesis agent.

    Contains only the fields the synthesis agent reads from or writes to.
    Fully compatible with the full AgentState in crystal_agent.models.state —
    extra fields present in the full state are simply ignored by TypedDict.
    """
    # Input
    user_request: str

    # Research Context
    retrieved_papers: Annotated[List[str], operator.add]

    # Current Iteration
    current_formula: str
    current_spacegroup: int
    current_structure_cif: str
    current_cif_path: Optional[str]
    predicted_properties: Dict[str, Union[float, List[float], Any]]

    # History
    experiments_log: Annotated[List[ExperimentRecord], operator.add]
    feedbacks: List[str]
    status: Literal["continue", "success", "human_required", "fail"]
    iteration_count: int

    # Retrieval skill control
    retrieval_skill: Optional[str]

    # Synthesis agent output
    synthesis_suggestion: Optional[Dict[str, Any]]


def create_synthesis_input(
    formula: str,
    cif_data: str = "",
    cif_path: Optional[str] = None,
    spacegroup: int = 1,
    predicted_properties: Optional[Dict[str, Any]] = None,
    user_request: str = "",
    experiments_log: Optional[List[ExperimentRecord]] = None,
) -> AgentState:
    """
    Create an AgentState pre-configured for synthesis agent standalone use.

    Args:
        formula: Chemical formula of the target crystal
        cif_data: CIF format string of the crystal structure
        cif_path: File path to the CIF file (optional)
        spacegroup: Space group number
        predicted_properties: Predicted properties dict
        user_request: Original research goal for context
        experiments_log: History of previous experiments

    Returns:
        AgentState ready for synthesis agent invocation
    """
    return {
        "user_request": user_request,
        "retrieved_papers": [],
        "current_formula": formula,
        "current_spacegroup": spacegroup,
        "current_structure_cif": cif_data,
        "current_cif_path": cif_path,
        "predicted_properties": predicted_properties or {},
        "experiments_log": experiments_log or [],
        "feedbacks": [],
        "status": "continue",
        "iteration_count": 0,
        "retrieval_skill": "synthesis",
        "synthesis_suggestion": None,
    }
