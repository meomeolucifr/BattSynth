"""
This node will handle the reasoning and synthesis suggestion generation based on the extracted pathways and other relevant information. 
Tasks:
- Input: 
    current_formula: str
    current_spacegroup: int
    current_structure_cif: str
    current_cif_path: Optional[str]
    predicted_properties: Dict[str, Union[float, List[float], Any]]
    extract relevant synthesis pathways from state["extracted_pathways"]
- Build prompt with SYNTHESIS_REASONING_PROMPT, including the target material, CIF summary, predicted properties, user request, extracted pathways, and experiments history (you can adjust the prompt as you see fit).
- Return with structured output matching SynthesisRecord.
"""