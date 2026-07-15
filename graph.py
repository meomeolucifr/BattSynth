"""
Workflow for Langgraph: retrieval -> extraction -> reasoning -> END
- retrieval node: retriever_agent, sets retrieval_skill="synthesis" in state, calls retriever_agent(), maps results to synthesis_papers
- extraction node: extract synthesis pathway from paper pdfs 
- reasoning node: generate synthesis suggestions based on predicted properties, extracted pathways, and other relevant information
"""