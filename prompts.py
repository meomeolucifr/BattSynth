"""
Prompt templates for the Synthesis Agent.

Contains the reasoning prompt that combines crystal structure, properties,
and extracted synthesis pathways to suggest a synthesis route.

Note: The extraction prompt is loaded from extraction_prompt.md at runtime
by the extraction node — it is not duplicated here.
"""

from langchain_core.prompts import PromptTemplate


SYNTHESIS_REASONING_PROMPT = PromptTemplate(
    input_variables=[
        "formula",
        "cif_summary",
        "properties",
        "extracted_pathways",
        "user_request",
        "experiments_history",
    ],
    template="""You are a materials synthesis expert. Given a target crystal structure, its predicted properties, and synthesis pathways extracted from literature, suggest the most viable synthesis route and estimate the likelihood of success.

TARGET MATERIAL: {formula}

CRYSTAL STRUCTURE (CIF summary):
{cif_summary}

PREDICTED PROPERTIES:
{properties}

RESEARCH CONTEXT: {user_request}

EXTRACTED SYNTHESIS PATHWAYS FROM LITERATURE:
{extracted_pathways}

PREVIOUS EXPERIMENTS IN THIS SESSION:
{experiments_history}

Based on all the information above, provide your synthesis recommendation. Consider:
- Which synthesis method best suits this crystal structure and space group?
- Are the required precursors commercially available?
- Do the predicted properties align with what is achievable via the suggested route?
- What characterization should confirm successful synthesis?

Your response MUST be valid JSON with this exact structure:
{{
    "recommended_pathway": {{
        "pathway_id": "recommended_1",
        "target_compound": "{formula}",
        "precursors": [
            {{"name": "...", "formula": "...", "amount": "...", "unit": "...", "role": "reactant|solvent|catalyst|precipitant"}}
        ],
        "steps": [
            {{"step_id": "step_1", "description": "...", "temperature_K": 298, "duration_min": 60, "atmosphere": "air|N2|Ar|vacuum"}}
        ],
        "conditions": {{"atmosphere": "...", "pressure_bar": 1.0}},
        "characterization": [
            {{"method": "XRD|SEM|TEM|TGA|DSC|Raman|FTIR", "purpose": "..."}}
        ],
        "source_paper": null,
        "confidence": 0.8
    }},
    "success_likelihood": 0.75,
    "reasoning": "Detailed justification for this synthesis route...",
    "risk_factors": [
        "Risk factor 1...",
        "Risk factor 2..."
    ],
    "alternative_pathways": [
        {{
            "pathway_id": "alt_1",
            "target_compound": "{formula}",
            "precursors": [...],
            "steps": [...],
            "conditions": {{}},
            "characterization": [],
            "source_paper": null,
            "confidence": 0.5
        }}
    ],
    "estimated_difficulty": "low|medium|high"
}}

OUTPUT (valid JSON only):"""
)
