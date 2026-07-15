"""
Reasoning node: synthesize a structured SynthesisRecord from crystal context,
predicted properties, extracted pathways, and experiment history.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Literal

from langchain_core.output_parsers import StrOutputParser

try:
    from ..models import SynthesisPathway, SynthesisRecord, SynthesisState
    from ..prompts import SYNTHESIS_REASONING_PROMPT
    from ..retriever import get_llm, log_agent_start, log_agent_result
except (ModuleNotFoundError, ImportError):
    from models import SynthesisPathway, SynthesisRecord, SynthesisState
    from prompts import SYNTHESIS_REASONING_PROMPT
    from retriever import get_llm, log_agent_start, log_agent_result

logger = logging.getLogger(__name__)

_CIF_SUMMARY_MAX_CHARS = 8000


def _cif_summary(cif: str) -> str:
    text = (cif or "").strip()
    if not text:
        return "(no CIF provided)"
    if len(text) <= _CIF_SUMMARY_MAX_CHARS:
        return text
    return text[:_CIF_SUMMARY_MAX_CHARS] + "\n\n... (CIF truncated)"


def _format_block(title: str, payload: Any) -> str:
    try:
        return json.dumps(payload, indent=2, default=str)
    except (TypeError, ValueError):
        return repr(payload)


def _experiments_history_text(log: List[Dict[str, Any]]) -> str:
    if not log:
        return "(no prior experiments in this session)"
    lines: List[str] = []
    for i, rec in enumerate(log, 1):
        lines.append(f"--- Experiment {i} ---")
        lines.append(_format_block("", rec))
    return "\n".join(lines)


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text, count=1)
    return text.strip()


def _coerce_difficulty(value: Any) -> Literal["low", "medium", "high"]:
    if value in ("low", "medium", "high"):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("low", "medium", "high"):
            return v
    return "medium"


def _ensure_pathway(raw: Dict[str, Any], formula: str) -> SynthesisPathway:
    return {
        "pathway_id": str(raw.get("pathway_id") or "recommended_1"),
        "target_compound": str(raw.get("target_compound") or formula),
        "precursors": list(raw.get("precursors") or []),
        "steps": list(raw.get("steps") or []),
        "conditions": dict(raw.get("conditions") or {}),
        "characterization": list(raw.get("characterization") or []),
        "source_paper": raw.get("source_paper"),
        "confidence": raw.get("confidence"),
    }


def _parsed_to_record(data: Dict[str, Any], formula: str) -> SynthesisRecord:
    pathway_raw = data.get("recommended_pathway") or data.get("suggested_pathway")
    if not isinstance(pathway_raw, dict):
        raise ValueError("LLM output missing recommended_pathway")

    alts_in = data.get("alternative_pathways") or []
    alternatives: List[SynthesisPathway] = []
    if isinstance(alts_in, list):
        for item in alts_in:
            if isinstance(item, dict):
                alternatives.append(_ensure_pathway(item, formula))

    return {
        "formula": str(data.get("formula") or formula),
        "suggested_pathway": _ensure_pathway(pathway_raw, formula),
        "success_likelihood": float(data.get("success_likelihood", 0.5)),
        "reasoning": str(data.get("reasoning") or ""),
        "alternative_pathways": alternatives,
        "risk_factors": list(data.get("risk_factors") or []),
        "estimated_difficulty": _coerce_difficulty(data.get("estimated_difficulty")),
    }


def _fallback_record(state: SynthesisState, note: str) -> SynthesisRecord:
    formula = state["current_formula"]
    pathways = list(state.get("extracted_pathways") or [])
    if pathways:
        suggested = dict(pathways[0])
        suggested["pathway_id"] = f"{suggested.get('pathway_id', 'extracted')}_prioritized"
        alternatives = [dict(p) for p in pathways[1:]]
    else:
        suggested = {
            "pathway_id": "heuristic_1",
            "target_compound": formula,
            "precursors": [],
            "steps": [
                {
                    "step_id": "step_1",
                    "description": (
                        "No literature pathways were extracted; design a route from "
                        "standard precursors for this stoichiometry and review safety datasheets."
                    ),
                    "temperature_K": 298,
                    "duration_min": 0,
                    "atmosphere": "inert",
                }
            ],
            "conditions": {},
            "characterization": [
                {"method": "XRD", "purpose": "Phase identification and lattice matching"}
            ],
            "source_paper": None,
            "confidence": 0.25,
        }
        alternatives = []

    return {
        "formula": formula,
        "suggested_pathway": suggested,
        "success_likelihood": 0.35,
        "reasoning": note,
        "alternative_pathways": alternatives,
        "risk_factors": [
            "Automated reasoning unavailable or failed; human review required before lab work."
        ],
        "estimated_difficulty": "high",
    }


def reasoning_node(state: SynthesisState) -> Dict[str, Any]:
    """
    LangGraph node: populate ``synthesis_suggestion`` and mark synthesis as done.

    Uses ``SYNTHESIS_REASONING_PROMPT`` with ``get_llm()``. Falls back to a heuristic
    record if the LLM is disabled or JSON parsing fails.
    """
    log_agent_start("SYNTHESIS REASONING")

    formula = state["current_formula"]
    cif_block = _cif_summary(state["current_structure_cif"])
    cif_summary = (
        f"Space group (international number): {state['current_spacegroup']}\n"
        f"CIF path (if any): {state.get('current_cif_path') or 'inline'}\n\n"
        f"{cif_block}"
    )

    llm = get_llm()
    if llm is None:
        note = "LLM disabled; returning heuristic synthesis record."
        logger.warning(note)
        log_agent_result(note)
        return {
            "synthesis_suggestion": _fallback_record(state, note),
            "synthesis_status": "done",
            "synthesis_error": note,
        }

    chain = SYNTHESIS_REASONING_PROMPT | llm | StrOutputParser()
    try:
        raw = chain.invoke(
            {
                "formula": formula,
                "cif_summary": cif_summary,
                "properties": _format_block("", state.get("predicted_properties") or {}),
                "extracted_pathways": _format_block(
                    "", state.get("extracted_pathways") or []
                ),
                "user_request": state.get("user_request") or "",
                "experiments_history": _experiments_history_text(
                    list(state.get("experiments_log") or [])
                ),
            }
        )
        data = json.loads(_strip_json_fence(raw))
        if not isinstance(data, dict):
            raise ValueError("LLM output is not a JSON object")
        record = _parsed_to_record(data, formula)
    except Exception as e:
        note = f"Reasoning failed ({e}); using heuristic record."
        logger.warning(note)
        log_agent_result(note)
        return {
            "synthesis_suggestion": _fallback_record(state, note),
            "synthesis_status": "done",
            "synthesis_error": str(e),
        }

    log_agent_result("Synthesis recommendation generated.")
    return {
        "synthesis_suggestion": record,
        "synthesis_status": "done",
        "synthesis_error": None,
    }
