"""
State and data type definitions for the Synthesis Agent.

These TypedDicts define the internal state of the synthesis sub-graph
and the structured output types for synthesis pathways.
"""

import operator
from typing import Annotated, List, Dict, Optional, Literal, TypedDict, Any


class SynthesisPathway(TypedDict):
    """
    A single extracted or suggested synthesis pathway.

    Attributes:
        pathway_id: Unique identifier (e.g., "extracted_1", "recommended_1")
        target_compound: Chemical formula of the target material
        precursors: List of precursor chemicals with details
        steps: Ordered synthesis steps with conditions
        conditions: Overall reaction conditions (atmosphere, pressure, etc.)
        characterization: Methods to confirm successful synthesis
        source_paper: Paper title/DOI the pathway was extracted from (if any)
        confidence: Extraction confidence score (0-1)
    """
    pathway_id: str
    target_compound: str
    precursors: List[Dict[str, Any]]      # [{name, formula, amount, unit, role}]
    steps: List[Dict[str, Any]]           # [{step_id, description, temperature_K, duration_min, atmosphere}]
    conditions: Dict[str, Any]            # {atmosphere, pressure_bar, ...}
    characterization: List[Dict[str, Any]]  # [{method, purpose}]
    source_paper: Optional[str]
    confidence: Optional[float]
    
    #Add new
    source: Dict[str, Any]                    # {"title": "", "doi": "", "authors": [], "journal": "", "year": null}
    
    metadata: Dict[str, Any]                  # {"discipline": "chemistry", "type": "", "tags": []}
    
    targets: List[Dict[str, Any]]             # [{"formula": "...", "name": "...", ...}]
    
    workflow: Dict[str, Any]                  # {"timeline": [{"step_ref": "", "description": ""}], "ambiguities": []}
    
    analysis: Dict[str, Any]                  # {"methods": []}
    
    final_outcomes: Dict[str, Any]            # {
    #     "yield": {"value": null, "unit": "%"},
    #     "capacity": {"value": null, "unit": "mAh g-1"},
    #     "cycle_life": null
    # }
    
    extraction_metadata: Dict[str, Any]       # {
    #     "timestamp": "",
    #     "source_file": "",
    #     "processing_time": null
    # }

class SynthesisRecord(TypedDict):
    """
    Complete synthesis suggestion produced by the reasoning node.

    Attributes:
        formula: Chemical formula of the target material
        suggested_pathway: The recommended synthesis pathway
        success_likelihood: Estimated probability of synthesis success (0-1)
        reasoning: Detailed reasoning behind the suggestion
        alternative_pathways: Other viable synthesis routes
        risk_factors: Potential failure modes or challenges
        estimated_difficulty: Overall difficulty assessment
    """
    formula: str
    suggested_pathway: SynthesisPathway
    success_likelihood: float
    reasoning: str
    alternative_pathways: List[SynthesisPathway]
    risk_factors: List[str]
    estimated_difficulty: Literal["low", "medium", "high"]
    
    # === new field ===
    final_extraction_json: Dict[str, Any]


class SynthesisState(TypedDict):
    """
    Internal state for the synthesis sub-graph.

    This state is separate from AgentState. Conversion functions in graph.py
    handle the boundary between the main workflow and this sub-graph.

    Attributes:
        current_formula: Chemical formula of the target crystal
        current_spacegroup: Space group number of the target crystal
        current_structure_cif: CIF data of the target crystal
        current_cif_path: File path to the CIF file
        predicted_properties: Properties predicted by experiment agents
        user_request: Original research goal for context
        experiments_log: History of experiments for context
        synthesis_papers: Papers retrieved for synthesis (accumulated)
        extracted_pathways: Structured pathways extracted from papers (accumulated)
        synthesis_suggestion: Final synthesis recommendation
        synthesis_status: Current stage of the synthesis sub-graph
        synthesis_error: Error message if something failed
    """
    # Inputs (copied from AgentState)
    current_formula: str
    current_spacegroup: int
    current_structure_cif: str
    current_cif_path: Optional[str]
    predicted_properties: Dict[str, Any]
    user_request: str
    experiments_log: List[Dict[str, Any]]

    # Synthesis-specific fields
    synthesis_papers: Annotated[List[Dict[str, Any]], operator.add]
    extracted_pathways: Annotated[List[SynthesisPathway], operator.add]
    synthesis_suggestion: Optional[SynthesisRecord]
    synthesis_status: Literal["retrieving", "extracting", "reasoning", "done", "error"]
    synthesis_error: Optional[str]
    
    # === new field===
    final_extraction_json: Optional[Dict[str, Any]]
