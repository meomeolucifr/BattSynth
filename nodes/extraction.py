"""
Tasks:
- Use the extraction_prompt.md and extraction_format.json as LLM prompt and output format (or work on SynthesisPathway and modify it according to the schema in extraction_format.json) for the retrieval agent.
- Redesign SynthesisPathway TypedDict to match the schema in extraction_format.json, which includes fields like pathway_id, target_compound, precursors, steps, conditions, characterization, source_paper, and confidence.
- For each paper in the state["synthesis_papers"]: 
    - Build prompt with extraction_prompt.md, paper pdf (pymupdf or any OCR technology) and output the extracted synthesis pathway using with_structured_output along with defined SynthesisPathway TypedDict.
- Return the extracted synthesis pathways and store it in the state.


"""