from state import create_synthesis_input
from graph import run_synthesis_graph
import json

state = create_synthesis_input(
    formula="MoTe2",
    cif_data="",  # optional; can paste CIF text here
    user_request="Suggest a practical synthesis pathway for MoTe2",
)

result = run_synthesis_graph(state)

print("status:", result.get("synthesis_status"))
print("error:", result.get("synthesis_error"))
suggestion = result.get("synthesis_suggestion") or {}
print("suggestion keys:", list(suggestion.keys()))
print("\n=== Full synthesis suggestion ===")
print(json.dumps(suggestion, indent=2, ensure_ascii=True, default=str))