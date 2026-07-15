# Synthesis Agent Examples

This folder bundles a couple of realistic inputs for `synthesis_agent`.

## Included examples

1. `mote2_candidate3_initial`
   - Formula: `MoTe2`
   - Based on result `result_id = 2`
   - Uses the selected `candidate_3` CIF as a clean starting input state
   - Best for: showing the minimum realistic standalone `AgentState`

2. `mo9wte20_candidate1_followup`
   - Formula: `Mo9WTe20`
   - Based on result `result_id = 5`
   - Uses the 2% compressed `candidate_1` CIF as the current structure
   - Includes one prior `experiments_log` entry so interns can see how a
     follow-up state can carry context from an earlier screening step
   - Best for: showing a more advanced state with history

## Structure files

- `structures/mote2_candidate3_unstrained.cif`
- `structures/mo9wte20_candidate1_unstrained.cif`
- `structures/mo9wte20_candidate1_compressed_2pct.cif`

## Usage

```python
from synthesis_agent.example_data import get_example_structures, load_example_states

structures = get_example_structures()
states = load_example_states()

state = states["mote2_candidate3_initial"]
print(state["current_formula"])
print(state["current_cif_path"])
```

If you want the examples as JSON:

```bash
python synthesis_agent/example_data.py
```

## Notes

- The example states set `current_spacegroup` to the nominal generation space
  group from the original run (`11` for `MoTe2`, `164` for `Mo9WTe20`).
- The copied CIF files themselves declare `P1` / space group `1`. This mirrors
  the current workflow, where the campaign tracks the intended symmetry while
  the saved CIF may still be written in P1.
