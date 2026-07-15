"""
Retriever Agent - Literature retrieval for the Synthesis Agent.

Environment variables for LLM configuration:
    SYNTH_LLM_PROVIDER: "openai" or "anthropic" (default: "openai")
    SYNTH_LLM_MODEL: Model name (default: "gpt-4o-mini")
    SYNTH_LLM_TEMPERATURE: Temperature (default: 0.7)
    SYNTH_LLM_API_KEY: API key for the selected provider
    SYNTH_LLM_ENABLED: "true" or "false" (default: "true")
    SYNTH_ARXIV_ENABLED: "true" or "false" (default: "true")
    SYNTH_ARXIV_MAX_RESULTS: Max papers to fetch (default: 5)
    SYNTH_ARXIV_TIMEOUT: Timeout in seconds (default: 10)
"""

import os
import re
import logging
import ssl
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

try:
    from state import AgentState
except ModuleNotFoundError:
    from state import AgentState

logger = logging.getLogger(__name__)
_dotenv_loaded = False


def _openai_supports_temperature(model_name: str) -> bool:
    """
    Return False for OpenAI reasoning models that only support default temperature.
    """
    m = (model_name or "").strip().lower()
    unsupported_prefixes = ("o1", "o3", "o4")
    return not any(m.startswith(prefix) for prefix in unsupported_prefixes)


def _parse_dotenv_line(line: str) -> Optional[tuple[str, str]]:
    """Parse a single .env line. Returns None for comments/invalid lines."""
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None
    if raw.startswith("export "):
        raw = raw[len("export "):].strip()
    if "=" not in raw:
        return None

    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"')
        or (value[0] == "'" and value[-1] == "'")
    ):
        value = value[1:-1]

    return key, value


def _load_dotenv_once() -> None:
    """
    Load environment variables from .env once, without overriding existing vars.
    """
    global _dotenv_loaded
    if _dotenv_loaded:
        return

    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        _dotenv_loaded = True
        return

    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_dotenv_line(line)
            if parsed is None:
                continue
            key, value = parsed
            os.environ.setdefault(key, value)
        logger.info(f"Loaded environment from {env_path}")
    except Exception as exc:
        logger.warning(f"Failed to load .env file at {env_path}: {exc}")
    finally:
        _dotenv_loaded = True

class _ArxivConfig:
    """ArXiv configuration from environment variables."""

    @property
    def enabled(self) -> bool:
        return os.environ.get("SYNTH_ARXIV_ENABLED", "true").lower() == "true"

    @property
    def max_results(self) -> int:
        return int(os.environ.get("SYNTH_ARXIV_MAX_RESULTS", "5"))

    @property
    def timeout(self) -> int:
        return int(os.environ.get("SYNTH_ARXIV_TIMEOUT", "10"))

    @property
    def allow_insecure_ssl(self) -> bool:
        return os.environ.get("SYNTH_ARXIV_ALLOW_INSECURE_SSL", "false").lower() == "true"

    @property
    def categories(self) -> List[str]:
        return ["cond-mat.mtrl-sci", "cond-mat.str-el", "physics.comp-ph"]


_arxiv_config = _ArxivConfig()

_llm_instance = None


def get_llm(force_new: bool = False):
    """
    Get an LLM instance based on environment configuration.

    Returns None if LLM is disabled or initialization fails.
    """
    global _llm_instance
    _load_dotenv_once()

    if os.environ.get("SYNTH_LLM_ENABLED", "true").lower() != "true":
        logger.info("LLM is disabled")
        return None

    if _llm_instance is not None and not force_new:
        return _llm_instance

    provider = os.environ.get("SYNTH_LLM_PROVIDER", "openai")
    model = os.environ.get("SYNTH_LLM_MODEL", "gpt-5-mini")
    temperature = float(os.environ.get("SYNTH_LLM_TEMPERATURE", "0.7"))
    api_key = os.environ.get("SYNTH_LLM_API_KEY", "")
    if not api_key:
        if provider == "anthropic":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")

    try:
        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            _llm_instance = ChatAnthropic(
                model=model, temperature=temperature, api_key=api_key,
            )
        else:
            from langchain_openai import ChatOpenAI
            kwargs = {"model": model}
            if _openai_supports_temperature(model):
                kwargs["temperature"] = temperature
            if api_key:
                kwargs["api_key"] = api_key
            _llm_instance = ChatOpenAI(**kwargs)

        logger.info(f"Initialized {provider} LLM: {model}")
        return _llm_instance

    except ImportError as e:
        logger.error(f"Failed to import LLM library: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return None


def reset_llm() -> None:
    """Reset the cached LLM instance."""
    global _llm_instance
    _llm_instance = None


def log_agent_start(agent_name: str) -> None:
    print("-" * 60)
    print(f"STEP: {agent_name}")
    print("-" * 60)


def log_agent_result(result: str) -> None:
    logger.info(f"   {result}")


def extract_search_terms_fallback(user_request: str) -> List[str]:
    """Rule-based search term extraction when LLM is unavailable."""
    base_terms = ["crystal structure", "materials science"]
    property_terms = []
    request_lower = user_request.lower()

    if "band gap" in request_lower or "bandgap" in request_lower:
        property_terms.extend(["band gap", "semiconductor"])
    if "formation energy" in request_lower:
        property_terms.extend(["formation energy", "DFT"])
    if "synthesis" in request_lower:
        property_terms.append("synthesis")
    if "stability" in request_lower:
        property_terms.append("thermodynamic stability")
    if "mechanical" in request_lower:
        property_terms.extend(["mechanical properties", "modulus"])
    if "thermoelectric" in request_lower:
        property_terms.append("thermoelectric")
    if "magnetic" in request_lower:
        property_terms.append("magnetic")
    if "perovskite" in request_lower:
        property_terms.append("perovskite")
    if "oxide" in request_lower:
        property_terms.append("oxide")
    if "nitride" in request_lower:
        property_terms.append("nitride")
    if "2d" in request_lower or "monolayer" in request_lower:
        property_terms.append("2D materials")

    # Extract chemical formula patterns (e.g., Al2O3, GaN)
    formulas = re.findall(r'[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*', user_request)
    for f in formulas[:2]:
        if len(f) > 1 and f not in ("OR", "AND", "NOT"):
            property_terms.append(f)

    return list(dict.fromkeys(base_terms + property_terms))


def build_arxiv_query(search_terms: List[str], max_terms: int = 3) -> str:
    """Build an ArXiv search query from search terms."""
    query_parts = [f'all:"{term}"' for term in search_terms[:max_terms]]
    search_query = " OR ".join(query_parts)

    categories = _arxiv_config.categories
    category_filter = " OR ".join([f"cat:{cat}" for cat in categories])

    return f"({search_query}) AND ({category_filter})"


def parse_arxiv_xml(xml_data: str) -> List[Dict]:
    """Parse ArXiv XML response into structured paper data."""
    papers = []
    try:
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(xml_data)

        for entry in root.findall("atom:entry", ns):
            title_elem = entry.find("atom:title", ns)
            summary_elem = entry.find("atom:summary", ns)
            authors_elem = entry.findall("atom:author/atom:name", ns)
            published_elem = entry.find("atom:published", ns)

            if title_elem is None or summary_elem is None:
                continue

            title = title_elem.text.strip().replace("\n", " ")
            abstract = summary_elem.text.strip().replace("\n", " ")

            authors = [a.text for a in authors_elem[:3]]
            if len(authors_elem) > 3:
                authors.append("et al.")

            year = published_elem.text[:4] if published_elem is not None else "Unknown"

            papers.append({
                "title": title,
                "authors": ", ".join(authors),
                "year": year,
                "abstract": abstract,
            })

    except ET.ParseError as e:
        logger.error(f"XML parsing error: {e}")

    return papers


def _arxiv_ssl_context() -> ssl.SSLContext:
    """
    Build SSL context for ArXiv calls using certifi CA bundle when available.
    """
    if _arxiv_config.allow_insecure_ssl:
        logger.warning("ArXiv SSL verification is disabled (SYNTH_ARXIV_ALLOW_INSECURE_SSL=true).")
        return ssl._create_unverified_context()

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception as exc:
        logger.warning(f"Falling back to system CA store for ArXiv SSL: {exc}")
        return ssl.create_default_context()


def _arxiv_urlopen(url: str):
    """
    Open ArXiv URL with configured timeout and SSL context.
    """
    return urllib.request.urlopen(
        url,
        timeout=_arxiv_config.timeout,
        context=_arxiv_ssl_context(),
    )


def fetch_arxiv_papers(
    search_terms: List[str],
    max_results: Optional[int] = None,
) -> List[Dict]:
    """Fetch raw paper data from ArXiv API."""
    if not _arxiv_config.enabled:
        logger.info("ArXiv search disabled")
        return []

    if max_results is None:
        max_results = _arxiv_config.max_results

    base_url = "http://export.arxiv.org/api/query?"
    full_query = build_arxiv_query(search_terms)

    params = {
        "search_query": full_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    }

    url = base_url + urllib.parse.urlencode(params)
    logger.info(f"Querying ArXiv: {full_query}")

    try:
        with _arxiv_urlopen(url) as response:
            data = response.read().decode("utf-8")

        papers = parse_arxiv_xml(data)

        # If no results, retry with broader search
        if not papers:
            logger.info("Retrying with broader search...")
            search_query = " OR ".join([f'all:"{term}"' for term in search_terms[:1]])
            params["search_query"] = search_query
            url = base_url + urllib.parse.urlencode(params)

            with _arxiv_urlopen(url) as response:
                data = response.read().decode("utf-8")
            papers = parse_arxiv_xml(data)

        logger.info(f"Retrieved {len(papers)} papers from ArXiv")
        return papers

    except urllib.error.URLError as e:
        logger.warning(f"ArXiv API network error: {e}")
        return []
    except Exception as e:
        logger.error(f"ArXiv API error: {e}")
        return []


def format_paper_basic(paper: Dict) -> str:
    """Basic paper formatting when LLM is unavailable."""
    abstract = paper.get("abstract", "")
    values = re.findall(r"\d+\.?\d*\s*(?:eV|meV|GPa|K|nm|Å)", abstract)
    values_str = f"Key values: {', '.join(values[:3])}" if values else ""
    sentences = re.split(r"(?<=[.!?])\s+", abstract)
    key_findings = " ".join(sentences[:2])

    return f"""{paper.get('title', 'Unknown')}
Authors: {paper.get('authors', 'Unknown')} ({paper.get('year', 'Unknown')})

Key Findings: {key_findings}
{values_str}
"""


def _tokenize_for_relevance(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9\+\-]+", (text or "").lower())


def _rank_papers_by_relevance(papers: List[Dict], query: str) -> List[Dict]:
    """
    Lightweight relevance ranking based on token overlap with title+abstract.
    """
    q_tokens = set(_tokenize_for_relevance(query))
    if not q_tokens:
        return papers

    scored = []
    for idx, paper in enumerate(papers):
        title = str(paper.get("title", ""))
        abstract = str(paper.get("abstract", ""))
        text_tokens = set(_tokenize_for_relevance(f"{title} {abstract}"))
        overlap = len(q_tokens.intersection(text_tokens))
        title_overlap = len(q_tokens.intersection(set(_tokenize_for_relevance(title))))
        score = (2 * title_overlap) + overlap
        scored.append((score, idx, paper))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [paper for _, _, paper in scored]


def _print_top_titles(papers: List[Dict], query: str, top_n: int) -> None:
    if not papers:
        print("   Top titles: no ArXiv results")
        return

    ranked = _rank_papers_by_relevance(papers, query)
    print(f"   Top {min(top_n, len(ranked))} titles by relevance for: {query}")
    for i, paper in enumerate(ranked[:top_n], start=1):
        print(f"   {i}. {paper.get('title', 'Untitled')}")


# Fallback papers when ArXiv is unavailable
MOCK_PAPERS = [
    "Synthesis of Metal Oxides: A Review\nKey synthesis methods for oxides include sol-gel, hydrothermal, and solid-state routes.",
    "Crystal Growth Techniques for Semiconductors\nCommon techniques: Czochralski, Bridgman, and vapor transport methods for semiconductor crystals.",
]


# ── Research skill prompts (default) ─────────────────────────────────────

SEARCH_TERMS_PROMPT = PromptTemplate(
    input_variables=["user_request"],
    template="""You are a materials science research assistant. Generate optimal search terms for ArXiv to find papers relevant to this research goal.

USER'S RESEARCH GOAL: {user_request}

Generate 2-3 specific search terms that would find relevant materials science papers on ArXiv.
Each search term should be only 1-2 words. Focus on:
- Material properties mentioned
- Material types
- Crystal structure terms

Return ONLY the search terms as a comma-separated list, nothing else. Keep each term to 1-2 words maximum.

Search terms:"""
)

EXTRACTION_PROMPT = PromptTemplate(
    input_variables=["title", "abstract", "user_goal"],
    template="""You are a materials science expert reading research papers to help design new crystal structures.

RESEARCH GOAL: {user_goal}

PAPER TO ANALYZE:
Title: {title}
Abstract: {abstract}

Extract and summarize the following from this paper:
1. **Key Findings**: What are the main scientific findings relevant to the research goal?
2. **Materials Mentioned**: What specific materials, compounds, or crystal structures are discussed?
3. **Property Values**: Any specific numerical values for band gaps, formation energies, or other properties?
4. **Design Rules**: Any guidelines or rules for designing materials with desired properties?
5. **Relevance Score**: Rate 1-5 how relevant this paper is to the research goal.

Format your response as a structured summary that would help a materials scientist propose new crystal structures.

EXTRACTED INSIGHTS:"""
)

# ── Synthesis skill prompts ──────────────────────────────────────────────

SYNTHESIS_SEARCH_PROMPT = PromptTemplate(
    input_variables=["user_request"],
    template="""You are a materials synthesis expert. Generate optimal search terms for ArXiv to find papers describing synthesis methods for a specific material.

SYNTHESIS TARGET: {user_request}

Generate 2-3 specific search terms that would find papers about how to synthesize this material or closely related compounds.
Each search term should be only 1-3 words. Focus on:
- The material name or chemical formula
- Common synthesis methods (sol-gel, hydrothermal, solid-state, etc.)
- Crystal growth techniques

Return ONLY the search terms as a comma-separated list, nothing else. Keep each term to 1-3 words maximum.

Search terms:"""
)

SYNTHESIS_EXTRACTION_PROMPT = PromptTemplate(
    input_variables=["title", "abstract", "user_goal"],
    template="""You are a materials synthesis expert reading research papers to extract synthesis procedures.

SYNTHESIS TARGET: {user_goal}

PAPER TO ANALYZE:
Title: {title}
Abstract: {abstract}

Extract and summarize the following synthesis-relevant information from this paper:
1. **Synthesis Method**: What synthesis technique is used (sol-gel, hydrothermal, solid-state, CVD, etc.)?
2. **Precursors & Reagents**: What starting materials, solvents, and reagents are mentioned with amounts?
3. **Conditions**: Temperature, pressure, atmosphere, duration, pH, and other reaction conditions?
4. **Post-Processing**: Any annealing, calcination, washing, or purification steps?
5. **Characterization**: What techniques confirm successful synthesis (XRD, SEM, TEM, etc.)?
6. **Relevance Score**: Rate 1-5 how relevant this synthesis procedure is to the target material.

Format your response as a structured summary focused on reproducing the synthesis.

EXTRACTED SYNTHESIS INFO:"""
)

# ── Skill registry ───────────────────────────────────────────────────────


def _research_context_builder(state: AgentState) -> str:
    """Build search context for research skill (default)."""
    return state["user_request"]


def _synthesis_context_builder(state: AgentState) -> str:
    """Build search context for synthesis skill."""
    formula = state.get("current_formula", "")
    props = state.get("predicted_properties", {})
    parts = [f"synthesis of {formula}"] if formula else ["crystal synthesis"]
    if props:
        prop_summary = ", ".join(f"{k}={v}" for k, v in list(props.items())[:3])
        parts.append(f"(properties: {prop_summary})")
    return " ".join(parts)


RETRIEVAL_SKILLS: Dict[str, Dict[str, Any]] = {
    "research": {
        "search_prompt": SEARCH_TERMS_PROMPT,
        "extraction_prompt": EXTRACTION_PROMPT,
        "context_builder": _research_context_builder,
    },
    "synthesis": {
        "search_prompt": SYNTHESIS_SEARCH_PROMPT,
        "extraction_prompt": SYNTHESIS_EXTRACTION_PROMPT,
        "context_builder": _synthesis_context_builder,
    },
}


def register_retrieval_skill(
    name: str,
    search_prompt: PromptTemplate,
    extraction_prompt: PromptTemplate,
    context_builder: Callable[[AgentState], str],
) -> None:
    """
    Register a new retrieval skill at runtime.

    Args:
        name: Unique skill name
        search_prompt: PromptTemplate (must accept "user_request")
        extraction_prompt: PromptTemplate (must accept "title", "abstract", "user_goal")
        context_builder: Callable that builds search context from state
    """
    RETRIEVAL_SKILLS[name] = {
        "search_prompt": search_prompt,
        "extraction_prompt": extraction_prompt,
        "context_builder": context_builder,
    }
    logger.info(f"Registered retrieval skill: {name}")


def get_retrieval_skill(name: str) -> Dict[str, Any]:
    """Get a registered retrieval skill by name. Falls back to 'research'."""
    if name not in RETRIEVAL_SKILLS:
        logger.warning(f"Unknown retrieval skill '{name}', falling back to 'research'")
        return RETRIEVAL_SKILLS["research"]
    return RETRIEVAL_SKILLS[name]


# ── Core retrieval functions ─────────────────────────────────────────────

def generate_search_terms_with_llm(
    user_request: str,
    llm,
    search_prompt: Optional[PromptTemplate] = None,
) -> List[str]:
    """Use LLM to generate search terms. Falls back to rule-based extraction."""
    if llm is None:
        return extract_search_terms_fallback(user_request)

    prompt = search_prompt or SEARCH_TERMS_PROMPT

    try:
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"user_request": user_request})

        terms = [t.strip() for t in response.strip().split(",")]
        terms = [t for t in terms if t and len(t) > 2][:5]

        if terms:
            return terms

    except Exception as e:
        logger.warning(f"LLM search term generation failed: {e}")

    return extract_search_terms_fallback(user_request)


def extract_insights_with_llm(
    papers: List[Dict],
    user_request: str,
    llm,
    extraction_prompt: Optional[PromptTemplate] = None,
) -> List[str]:
    """Use LLM to extract insights from papers. Falls back to basic formatting."""
    if llm is None:
        return [format_paper_basic(p) for p in papers]

    prompt = extraction_prompt or EXTRACTION_PROMPT
    processed_papers = []
    chain = prompt | llm | StrOutputParser()

    for paper in papers:
        try:
            insights = chain.invoke({
                "title": paper["title"],
                "abstract": paper["abstract"],
                "user_goal": user_request,
            })

            formatted_paper = f"""{paper['title']}

{insights.strip()}
"""
            processed_papers.append(formatted_paper)

        except Exception as e:
            logger.warning(f"LLM extraction failed for paper: {e}")
            processed_papers.append(format_paper_basic(paper))

    return processed_papers


# ── Main agent function ─────────────────────────────────────────────────

def retriever_agent(state: AgentState) -> Dict:
    """
    LLM-powered retrieval agent with state-driven skill selection.

    Reads state["retrieval_skill"] to pick prompts and context builder.
    Defaults to "research" skill if not set.

    Args:
        state: Current agent state

    Returns:
        State update with retrieved_papers
    """
    skill_name = state.get("retrieval_skill") or "research"
    skill = get_retrieval_skill(skill_name)

    log_agent_start(f"LITERATURE RETRIEVAL (skill={skill_name})")

    search_context = skill["context_builder"](state)
    llm = get_llm()

    # Step 1: Generate search terms
    # For synthesis, prioritize a formula-only query (e.g., "MoTe2") so ArXiv
    # search stays general instead of over-constrained phrases like "MoTe2 CVD".
    if skill_name == "synthesis" and state.get("current_formula"):
        search_terms = [str(state["current_formula"]).strip()]
        logger.info("   Using formula-only search strategy for synthesis skill.")
    else:
        logger.info("   Generating search strategy with LLM...")
        search_terms = generate_search_terms_with_llm(
            search_context, llm, search_prompt=skill["search_prompt"]
        )
    logger.info(f"   Search terms: {search_terms}")

    # Step 2: Fetch papers from ArXiv
    logger.info("   Fetching papers from ArXiv...")
    raw_papers = fetch_arxiv_papers(search_terms, max_results=_arxiv_config.max_results)
    query_text = " ".join(search_terms)
    top_n = int(os.environ.get("SYNTH_ARXIV_PRINT_TOP_N", "5"))
    _print_top_titles(raw_papers, query_text, top_n)

    if not raw_papers:
        logger.warning("   ArXiv search returned no results, using fallback papers")
        processed_papers = list(MOCK_PAPERS)
    else:
        # Step 3: Extract insights
        logger.info(f"   Using LLM to analyze {len(raw_papers)} papers...")
        processed_papers = extract_insights_with_llm(
            raw_papers, search_context, llm,
            extraction_prompt=skill["extraction_prompt"],
        )

    log_agent_result(f"Processed {len(processed_papers)} papers with extracted insights")

    for i, paper in enumerate(processed_papers, 1):
        logger.info(f"   Paper {i}: {paper}")

    return {"retrieved_papers": processed_papers}
