"""
Extraction node for the synthesis agent.

Flow:
synthesis_papers -> _paper_to_text() -> _call_llm_for_extraction()
                                     -> _json_to_synthesis_pathway()
                                     -> _merge_pathways_to_json()
                                     -> extracted_pathways + final_extraction_json
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    try:
        from ..models import SynthesisPathway
    except (ModuleNotFoundError, ImportError):
        from models import SynthesisPathway

logger = logging.getLogger(__name__)

# ── Path resolution ───────────────────────────────────────────────────────────
# Walk upward from this file to locate the prompt / schema assets.
_THIS_DIR = Path(__file__).parent
_ASSETS_DIR = _THIS_DIR.parent
_PROMPT_PATH = _ASSETS_DIR / "extraction_prompt.md"
_SCHEMA_PATH = _ASSETS_DIR / "extraction_format.json"


# ── Asset loaders (cached after first read) ───────────────────────────────────

_extraction_prompt_text: Optional[str] = None
_extraction_schema: Optional[Dict[str, Any]] = None


def _load_extraction_prompt() -> str:
    """Load and cache the extraction prompt from extraction_prompt.md."""
    global _extraction_prompt_text
    if _extraction_prompt_text is None:
        try:
            _extraction_prompt_text = _PROMPT_PATH.read_text(encoding="utf-8").strip()
            logger.info(f"Loaded extraction prompt from {_PROMPT_PATH}")
        except FileNotFoundError:
            logger.error(f"Extraction prompt not found at {_PROMPT_PATH}")
            _extraction_prompt_text = (
                "Extract structured chemistry information from the provided text "
                "and return ONLY valid JSON matching the schema below."
            )
    return _extraction_prompt_text


def _load_extraction_schema() -> Dict[str, Any]:
    """Load and cache the extraction schema from extraction_format.json."""
    global _extraction_schema
    if _extraction_schema is None:
        try:
            _extraction_schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            logger.info(f"Loaded extraction schema from {_SCHEMA_PATH}")
        except FileNotFoundError:
            logger.error(f"Extraction schema not found at {_SCHEMA_PATH}")
            _extraction_schema = {}
    return _extraction_schema


# ── PDF text extraction ───────────────────────────────────────────────────────

def _extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract full text from a PDF using PyMuPDF (fitz).

    Returns an empty string if the file is missing or fitz is not installed.
    Includes page headers so the LLM can cite provenance (e.g., "Page 3").
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF (fitz) not installed — cannot extract PDF text. "
                       "Install with: pip install pymupdf")
        return ""

    path = Path(pdf_path)
    if not path.exists():
        logger.warning(f"PDF not found: {pdf_path}")
        return ""

    pages: List[str] = []
    try:
        with fitz.open(str(path)) as doc:
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append(f"[Page {page_num}]\n{text}")
        logger.info(f"Extracted {len(pages)} pages from {path.name}")
    except Exception as exc:
        logger.error(f"PDF extraction failed for {pdf_path}: {exc}")

    return "\n\n".join(pages)


def _paper_to_text(paper: Dict[str, Any]) -> str:
    """
    Convert a paper dict to the text string sent to the LLM.

    Priority:
      1. pdf_path / pdf_file key  → extract full text via PyMuPDF
      2. full_text key            → use directly
      3. title + abstract         → lightweight fallback
    """
    for key in ("pdf_path", "pdf_file", "file_path"):
        pdf_path = paper.get(key)
        if pdf_path:
            text = _extract_text_from_pdf(str(pdf_path))
            if text:
                return text

    full_text = paper.get("full_text", "")
    if full_text:
        return full_text

    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    return f"Title: {title}\n\nAbstract:\n{abstract}"


# ── LLM call ─────────────────────────────────────────────────────────────────

def _build_extraction_messages(
    paper_text: str,
    schema: Dict[str, Any],
    prompt_text: str,
) -> List[Dict[str, str]]:
    """
    Assemble the messages list for the LLM.

    System message  → extraction prompt + schema
    User message    → paper content
    """
    schema_str = json.dumps(schema, indent=2)
    system_content = (
        f"{prompt_text}\n\n"
        f"OUTPUT SCHEMA (return ONLY valid JSON conforming to this structure):\n"
        f"```json\n{schema_str}\n```"
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"PAPER CONTENT:\n\n{paper_text}"},
    ]


def _call_llm_for_extraction(
    paper_text: str,
    schema: Dict[str, Any],
    prompt_text: str,
    llm,
) -> Dict[str, Any]:
    """
    Call the LLM and parse its JSON response.

    Returns an empty dict on failure so the caller can handle gracefully.
    """
    messages = _build_extraction_messages(paper_text, schema, prompt_text)

    try:
        # LangChain chat models accept a list of dicts or HumanMessage objects.
        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = [
            SystemMessage(content=messages[0]["content"]),
            HumanMessage(content=messages[1]["content"]),
        ]
        response = llm.invoke(lc_messages)

        # Extract string content from AIMessage or plain string
        raw: str = response.content if hasattr(response, "content") else str(response)

        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]  # drop opening fence
            if raw.startswith("json"):
                raw = raw[4:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError as exc:
        logger.error(f"LLM returned non-JSON output: {exc}")
    except Exception as exc:
        logger.error(f"LLM call failed during extraction: {exc}")

    return {}


# ── SynthesisPathway builder ──────────────────────────────────────────────────

def _json_to_synthesis_pathway(
    extracted: Dict[str, Any],
    paper: Dict[str, Any],
    pathway_index: int,
) -> "SynthesisPathway":  # noqa: F821  (imported below to avoid circular import)
    """
    Map a raw extracted JSON dict (matching extraction_format.json) to a
    SynthesisPathway TypedDict.

    Legacy fields (precursors, steps, conditions, characterization) are
    derived from the richer schema fields so that downstream nodes that
    still read the old keys continue to work.
    """
    try:
        from ..models import SynthesisPathway  # local import
    except (ModuleNotFoundError, ImportError):
        from models import SynthesisPathway

    # ── Derive legacy "precursors" from chemicals list ────────────────────
    chemicals: List[Dict[str, Any]] = extracted.get("chemicals", [])
    precursors: List[Dict[str, Any]] = [
        {
            "name": chem.get("name", ""),
            "formula": chem.get("molecular_formula", ""),
            "amount": chem.get("amount", {}).get("value"),
            "unit": chem.get("amount", {}).get("unit", ""),
            "role": chem.get("ontology", {}).get("role", "reactant"),
        }
        for chem in chemicals
    ]

    # ── Derive legacy "steps" from synthesis.steps ────────────────────────
    synthesis_block: Dict[str, Any] = extracted.get("synthesis", {})
    raw_steps: List[Dict[str, Any]] = synthesis_block.get("steps", [])
    steps: List[Dict[str, Any]] = []
    for s in raw_steps:
        ops = s.get("operations", [{}])
        first_op = ops[0] if ops else {}
        temp = first_op.get("temperature", {})
        dur = first_op.get("duration", {})
        steps.append({
            "step_id": s.get("step_id", ""),
            "description": s.get("description", ""),
            "temperature_K": temp.get("value") if isinstance(temp, dict) else temp,
            "duration_min": dur.get("value") if isinstance(dur, dict) else dur,
            "atmosphere": s.get("conditions", {}).get("atmosphere", ""),
        })

    # ── Derive legacy "conditions" from synthesis step conditions ─────────
    conditions: Dict[str, Any] = {}
    if raw_steps:
        first_cond = raw_steps[0].get("conditions", {})
        conditions = {
            "atmosphere": first_cond.get("atmosphere", ""),
            "pressure_bar": (
                first_cond.get("pressure", {}).get("value")
                if isinstance(first_cond.get("pressure"), dict)
                else first_cond.get("pressure")
            ),
        }

    # ── Derive legacy "characterization" list ────────────────────────────
    char_list: List[Dict[str, Any]] = extracted.get("characterization", [])
    characterization_legacy: List[Dict[str, Any]] = [
        {
            "method": c.get("method", ""),
            "purpose": (
                c.get("interpretation", "")
                or c.get("parameters", {}).get("purpose", "")
            ),
        }
        for c in char_list
    ]

    # ── Infer target compound ──────────────────────────────────────────────
    targets: List[Dict[str, Any]] = extracted.get("targets", [])
    target_compound = ""
    if targets:
        t0 = targets[0]
        target_compound = (
            t0.get("molecular_formula")
            or t0.get("compound_name")
            or ""
        )

    # ── Source / confidence ───────────────────────────────────────────────
    source_info: Dict[str, Any] = extracted.get("source", {})
    source_paper = source_info.get("doi") or source_info.get("title") or paper.get("title", "")
    confidence: float = 0.8  # default; can be refined later

    return SynthesisPathway(
        # ── legacy fields ──────────────────────────────────────────────────
        pathway_id=f"extracted_{pathway_index + 1}",
        target_compound=target_compound,
        precursors=precursors,
        steps=steps,
        conditions=conditions,
        characterization=characterization_legacy,
        source_paper=source_paper,
        confidence=confidence,
        # ── new fields (full schema) ───────────────────────────────────────
        source=source_info,
        metadata=extracted.get("metadata", {}),
        targets=targets,
        workflow=extracted.get("workflow", {"timeline": [], "ambiguities": []}),
        analysis=extracted.get("analysis", {"methods": []}),
        final_outcomes=extracted.get(
            "final_outcomes",
            {"yield": {"value": None, "unit": "%"}, "capacity": {"value": None, "unit": "mAh g-1"}, "cycle_life": None},
        ),
        extraction_metadata=extracted.get(
            "extraction_metadata",
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_file": paper.get("pdf_path", paper.get("title", "")),
                "processing_time": None,
            },
        ),
    )


def _empty_pathway(paper: Dict[str, Any], index: int) -> "SynthesisPathway":  # noqa: F821
    """Return a minimal SynthesisPathway when extraction fails."""
    try:
        from ..models import SynthesisPathway
    except (ModuleNotFoundError, ImportError):
        from models import SynthesisPathway

    return SynthesisPathway(
        pathway_id=f"extracted_{index + 1}",
        target_compound="",
        precursors=[],
        steps=[],
        conditions={},
        characterization=[],
        source_paper=paper.get("title", ""),
        confidence=0.0,
        source={},
        metadata={},
        targets=[],
        workflow={"timeline": [], "ambiguities": []},
        analysis={"methods": []},
        final_outcomes={"yield": {"value": None, "unit": "%"}, "capacity": {"value": None, "unit": "mAh g-1"}, "cycle_life": None},
        extraction_metadata={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_file": paper.get("pdf_path", paper.get("title", "")),
            "processing_time": None,
        },
    )


# ── Merge helper ──────────────────────────────────────────────────────────────

def _merge_pathways_to_json(
    pathways: List["SynthesisPathway"],  # noqa: F821
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge all extracted SynthesisPathway dicts into a single consolidated
    JSON that follows the top-level structure of extraction_format.json.

    Fields that can appear once (source, metadata) are taken from the
    first pathway that has a non-empty value.  List-typed fields
    (chemicals, synthesis.steps, characterization, etc.) are concatenated
    and de-duplicated by name / step_id.
    """
    merged: Dict[str, Any] = json.loads(json.dumps(schema))  # deep copy of blank schema

    all_chemicals: List[Dict] = []
    all_steps: List[Dict] = []
    all_char: List[Dict] = []
    all_analysis: List[Dict] = []
    all_targets: List[Dict] = []
    all_timeline: List[Dict] = []
    all_ambiguities: List[Dict] = []

    seen_chem_names: set = set()
    seen_step_ids: set = set()
    seen_char_methods: set = set()

    for pw in pathways:
        # source / metadata: first non-empty wins
        if not merged.get("source", {}).get("title") and pw.get("source", {}).get("title"):
            merged["source"] = pw["source"]
        if not merged.get("metadata", {}).get("type") and pw.get("metadata", {}).get("type"):
            merged["metadata"] = pw["metadata"]

        # targets
        for t in pw.get("targets", []):
            key = t.get("molecular_formula") or t.get("compound_name") or ""
            if key and key not in seen_chem_names:
                all_targets.append(t)
                seen_chem_names.add(key)

        # chemicals (precursors from legacy field, mapped back)
        for chem in pw.get("precursors", []):
            name = chem.get("name", "")
            if name and name not in seen_chem_names:
                all_chemicals.append(chem)
                seen_chem_names.add(name)

        # synthesis steps
        for step in pw.get("steps", []):
            sid = step.get("step_id", "")
            if sid and sid not in seen_step_ids:
                all_steps.append(step)
                seen_step_ids.add(sid)
            elif not sid:
                all_steps.append(step)

        # characterization
        for c in pw.get("characterization", []):
            method = c.get("method", "")
            if method and method not in seen_char_methods:
                all_char.append(c)
                seen_char_methods.add(method)

        # analysis methods
        for m in pw.get("analysis", {}).get("methods", []):
            all_analysis.append(m)

        # workflow
        all_timeline.extend(pw.get("workflow", {}).get("timeline", []))
        all_ambiguities.extend(pw.get("workflow", {}).get("ambiguities", []))

        # final_outcomes: prefer non-null values
        for key in ("yield", "capacity", "cycle_life"):
            fo = pw.get("final_outcomes", {})
            if fo.get(key) is not None and merged["final_outcomes"].get(key) is None:
                merged["final_outcomes"][key] = fo[key]

    merged["targets"] = all_targets
    merged["chemicals"] = all_chemicals
    merged["synthesis"]["steps"] = all_steps
    merged["characterization"] = all_char
    merged["analysis"]["methods"] = all_analysis
    merged["workflow"]["timeline"] = all_timeline
    merged["workflow"]["ambiguities"] = all_ambiguities
    merged["extraction_metadata"]["timestamp"] = datetime.now(timezone.utc).isoformat()

    return merged


# ── Main extraction node ──────────────────────────────────────────────────────

def extraction_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: extract structured synthesis pathways from papers.

    Reads:
        state["synthesis_papers"]  — list of paper dicts (may include pdf_path)

    Writes:
        state["extracted_pathways"]    — list of SynthesisPathway
        state["final_extraction_json"] — merged JSON (extraction_format.json schema)
        state["synthesis_status"]      — "extracting" → "reasoning" or "error"
    """
    try:
        from ..retriever import get_llm
    except (ModuleNotFoundError, ImportError):
        from retriever import get_llm

    papers: List[Dict[str, Any]] = state.get("synthesis_papers", [])
    if not papers:
        logger.warning("extraction_node: no synthesis_papers in state — skipping")
        return {
            "extracted_pathways": [],
            "final_extraction_json": {},
            "synthesis_status": "reasoning",
        }

    logger.info(f"extraction_node: processing {len(papers)} paper(s)")

    prompt_text = _load_extraction_prompt()
    schema = _load_extraction_schema()
    llm = get_llm()

    extracted_pathways = []

    for idx, paper in enumerate(papers):
        paper_label = paper.get("title", f"paper_{idx + 1}")
        logger.info(f"  [{idx + 1}/{len(papers)}] Extracting: {paper_label[:80]}")

        t0 = time.perf_counter()
        paper_text = _paper_to_text(paper)

        if not paper_text.strip():
            logger.warning(f"  No text available for paper {idx + 1} — skipping")
            extracted_pathways.append(_empty_pathway(paper, idx))
            continue

        if llm is None:
            logger.warning("  LLM not available — returning empty pathway")
            extracted_pathways.append(_empty_pathway(paper, idx))
            continue

        extracted_json = _call_llm_for_extraction(paper_text, schema, prompt_text, llm)
        elapsed = time.perf_counter() - t0

        if not extracted_json:
            logger.warning(f"  Extraction returned empty result for paper {idx + 1}")
            extracted_pathways.append(_empty_pathway(paper, idx))
            continue

        # Stamp processing time into extraction_metadata
        extracted_json.setdefault("extraction_metadata", {})
        extracted_json["extraction_metadata"]["processing_time"] = round(elapsed, 2)
        extracted_json["extraction_metadata"]["source_file"] = paper.get(
            "pdf_path", paper.get("title", "")
        )

        pathway = _json_to_synthesis_pathway(extracted_json, paper, idx)
        extracted_pathways.append(pathway)
        logger.info(f"  Done in {elapsed:.1f}s — target: {pathway['target_compound']!r}")

    final_json = _merge_pathways_to_json(extracted_pathways, schema)

    return {
        "extracted_pathways": extracted_pathways,
        "final_extraction_json": final_json,
        "synthesis_status": "reasoning",
    }