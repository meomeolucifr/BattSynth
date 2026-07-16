#!/usr/bin/env python3
"""
corrections_simple.py
Applies verified corrections to SIMPLE tier extraction JSONs.
Each correction was cross-checked against the source PDF text.
Only corrections with clear PDF evidence are included.
"""

import json
import os
import copy

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "dataset", "extraction_jsons", "simple")

CORRECTIONS = [
    # -------------------------------------------------------------------------
    # 1. Lee_et_al -- targets[0] missing formula
    #    PDF Evidence: Title reads "Synthesis and characterization of lithium
    #    aluminum-doped spinel (LiAlxMn2-xO4) for lithium secondary battery".
    #    Table 1 header: "Synthetic conditions and properties of LiAlxMn2-xO4 powders"
    #    The formula LiAlxMn2-xO4 appears throughout the paper.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Lee_et_al__-_2001_-_Synthesis_and_characterization_of_lithium_aluminum",
        "tier": "simple",
        "entity_path": "targets[0]",
        "field_to_fix": "molecular_formula",
        "new_value": "LiAlxMn2-xO4",
        "pdf_evidence": "Title: 'Synthesis and characterization of lithium aluminum-doped spinel (LiAlxMn2-xO4)'; Table 1 header: 'LiAlxMn2-xO4 powders'"
    },

    # -------------------------------------------------------------------------
    # 1b. Lee_et_al -- chemicals[1] Al(OH)3 marked incorrect by reviewer
    #     PDF Evidence: ACTUALLY CORRECT. Page 1 abstract lists 'Al(NO3)3, Al(OH)3,
    #     AlF3, and Al2O3' as starting materials. Table 1 rows 2 and 6 use
    #     'Mn3O4 + Al(OH)3' and 'gamma-MnOOH + Al(OH)3'. The human reviewer's
    #     verdict of 'incorrect' appears to be an error -- Al(OH)3 IS in the paper.
    #     SKIPPED: No correction needed as Al(OH)3 is verified correct in the PDF.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # 2. Li_et_al_2023 -- targets[0] missing formula
    #    PDF Evidence: Title reads "One step in-situ synthesis of Na3V2(PO4)3/
    #    Na3V3(PO4)4 biphase coexisted cathode". Abstract and keywords repeat
    #    "Na3V2(PO4)3/Na3V3(PO4)4" multiple times.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Li_et_al__-_2023_-_One_step_in-situ_synthesis_of_Na3V2_PO4_3Na3V3_PO",
        "tier": "simple",
        "entity_path": "targets[0]",
        "field_to_fix": "molecular_formula",
        "new_value": "Na3V2(PO4)3/Na3V3(PO4)4",
        "pdf_evidence": "Title: 'One step in-situ synthesis of Na3V2(PO4)3/Na3V3(PO4)4 biphase coexisted cathode'; Abstract repeats formula throughout"
    },

    # -------------------------------------------------------------------------
    # 3. Liu_et_al_Impedance -- targets[0] missing formula
    #    PDF Evidence: The paper refers to the electrolyte as 'LiPON' (lithium
    #    phosphorus oxynitride) throughout. No explicit stoichiometric formula
    #    like Li3.3PO3.9N0.17 is given. The compound name is 'LiPON'.
    #    Setting formula to 'LiPON' as that is the identifier used in the paper.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Liu_et_al__-_2021_-_Impedance_Modeling_of_Solid-State_Electrolytes_In",
        "tier": "simple",
        "entity_path": "targets[0]",
        "field_to_fix": "molecular_formula",
        "new_value": "LiPON",
        "pdf_evidence": "Abstract: 'The model is verified against the experimental impedance spectra of LiPON'; Section 2: 'the amorphous material LiPON is considered as the solid-state electrolyte'"
    },

    # -------------------------------------------------------------------------
    # 3b. Liu_et_al_Impedance -- operations[0] incorrect (hallucination)
    #     PDF Evidence: This is a modeling/simulation paper. The paper does NOT
    #     describe any synthesis or assembly procedure. The 'assemble' action is
    #     a hallucination. The correct fix is to remove the synthesis step or
    #     mark it as a modeling setup. We change the action to 'model' to reflect
    #     that this is a computational study, not a synthesis.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Liu_et_al__-_2021_-_Impedance_Modeling_of_Solid-State_Electrolytes_In",
        "tier": "simple",
        "entity_path": "synthesis.steps[0].operations[0]",
        "field_to_fix": "action",
        "new_value": "model",
        "pdf_evidence": "The paper is a modeling study ('We propose a new equivalent circuit model'); no synthesis/assembly is described anywhere in the text. 'assemble' is a hallucination."
    },

    # -------------------------------------------------------------------------
    # 4. Lv_et_al -- targets[1] missing formula
    #    PDF Evidence: Title reads "Two-dimensional V2C@Se (MXene) composite
    #    cathode material". Abstract says "The composite two-dimensional layered
    #    structure (V2C@Se) is formed after calcining with selenium."
    # -------------------------------------------------------------------------
    {
        "paper_id": "Lv_et_al__-_2022_-_Two-dimensional_V2C_Se__MXene__composite_cathode_m",
        "tier": "simple",
        "entity_path": "targets[1]",
        "field_to_fix": "molecular_formula",
        "new_value": "V2C@Se",
        "pdf_evidence": "Title: 'Two-dimensional V2C@Se (MXene) composite cathode material'; Abstract: 'composite two-dimensional layered structure (V2C@Se)'"
    },

    # -------------------------------------------------------------------------
    # 5. Hong_et_al -- targets[0] missing formula
    #    PDF Evidence: The composite cathode contains LiNi0.7Co0.1Mn0.2O2 as
    #    active material and Li6PS5Cl as solid electrolyte. The abstract says
    #    "(LiNi0.7Co0.1Mn0.2O2), conducting carbon, and solid electrolyte
    #    (Li6PS5Cl)". For a composite cathode, the primary active material
    #    formula is most appropriate.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Hong_et_al__-_2022_-_All-Solid-State_Lithium_Batteries_Li__",
        "tier": "simple",
        "entity_path": "targets[0]",
        "field_to_fix": "molecular_formula",
        "new_value": "LiNi0.7Co0.1Mn0.2O2/Li6PS5Cl",
        "pdf_evidence": "Abstract: 'active material (LiNi0.7Co0.1Mn0.2O2), conducting carbon, and solid electrolyte (Li6PS5Cl)'"
    },

    # -------------------------------------------------------------------------
    # 5b. Hong_et_al -- targets[1] missing formula
    #     PDF Evidence: Same as above but for the PTFE-based comparison cathode.
    #     Same active material and electrolyte, just different binder.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Hong_et_al__-_2022_-_All-Solid-State_Lithium_Batteries_Li__",
        "tier": "simple",
        "entity_path": "targets[1]",
        "field_to_fix": "molecular_formula",
        "new_value": "LiNi0.7Co0.1Mn0.2O2/Li6PS5Cl",
        "pdf_evidence": "Abstract: 'active material (LiNi0.7Co0.1Mn0.2O2)...solid electrolyte (Li6PS5Cl)'; same components with PTFE binder instead of ionomer"
    },

    # -------------------------------------------------------------------------
    # 6. Lamsayah_et_al -- targets[0-3] missing formula
    #    PDF Evidence: The paper provides IUPAC names and ESI-MS m/z values for
    #    L1-L4, but does NOT provide explicit molecular formulas (CxHyNzOw).
    #    The ESI-MS values are: L1 M=332.02 ([M+Na]+), L2 M=417 ([M]),
    #    L3 M=349.99 ([2M+Na]), L4 not clearly given.
    #    SKIPPED: Cannot verify explicit molecular formulas in the PDF text.
    #    The compound names are already captured in compound_name field.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # 7. Trease_et_al -- characterization[2] incorrect method label
    #    PDF Evidence: The paper uses "joint X-ray and neutron Rietveld
    #    refinement" (page 4 text: "joint X-ray and neutron Rietveld refinement
    #    was performed"). The method was NOT neutron-only.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Trease_et_al__-_2016_-_Identifying_the_Distribution_of_Al_3__i",
        "tier": "simple",
        "entity_path": "characterization[2]",
        "field_to_fix": "method",
        "new_value": "Joint X-ray and Neutron Rietveld Refinement",
        "pdf_evidence": "Page 4: 'joint X-ray and neutron Rietveld refinement was performed'; Figure 3 caption describes joint refinement"
    },

    # -------------------------------------------------------------------------
    # 7b. Trease_et_al -- characterization[3] incorrect
    #     PDF Evidence: characterization[3] is labeled 'Synchrotron X-ray
    #     Powder Diffraction' with result 'matches neutron data', but the paper
    #     describes a JOINT refinement, not a separate synchrotron-only result.
    #     The paper says all peaks indexed to single R-3m phase in joint
    #     refinement. This entry is a duplicate/misrepresentation of the joint
    #     refinement already in characterization[2].
    #     Fix: Change method to match what was actually done and fix the result.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Trease_et_al__-_2016_-_Identifying_the_Distribution_of_Al_3__i",
        "tier": "simple",
        "entity_path": "characterization[3]",
        "field_to_fix": "method",
        "new_value": "Synchrotron X-ray Powder Diffraction (joint refinement with NPD)",
        "pdf_evidence": "Figure 3: 'joint Rietveld refinement' of both synchrotron XRD and NPD patterns; not a standalone XRD result"
    },
    {
        "paper_id": "Trease_et_al__-_2016_-_Identifying_the_Distribution_of_Al_3__i",
        "tier": "simple",
        "entity_path": "characterization[3].results[0]",
        "field_to_fix": "value",
        "new_value": "Single R-3m layered phase confirmed by joint refinement",
        "pdf_evidence": "Text near Figure 3: 'all peaks indexed to single R-3m phase' via joint X-ray and neutron Rietveld refinement"
    },

    # -------------------------------------------------------------------------
    # 8. Li_and_Monroe -- operations[0] incorrect (hallucination)
    #    PDF Evidence: This is a theoretical/modeling paper about dendrite
    #    nucleation mechanisms in LLZO. No synthesis or assembly is described.
    #    The 'assemble' action with T=453 is a hallucination.
    # -------------------------------------------------------------------------
    {
        "paper_id": "Li_and_Monroe_-_2019_-_Dendrite_nucleation_in_lithium-conductive_ceramics",
        "tier": "simple",
        "entity_path": "synthesis.steps[0].operations[0]",
        "field_to_fix": "action",
        "new_value": "model",
        "pdf_evidence": "Paper is a theoretical study ('This paper applies principles of chemomechanics to investigate the critical current'). No synthesis/assembly described. 'assemble' is a hallucination."
    },

    # -------------------------------------------------------------------------
    # 9. Lopez-Aranguren -- characterization[4] TGA/DTA incorrect labels
    #    PDF Evidence: The paper states decomposition occurs "between 450 C
    #    and 650 C" (referring to Figure S2a). The extraction uses 'decomposition
    #    onset' (723 K) and 'decomposition end' (923 K). While the K conversions
    #    are correct (450+273=723, 650+273=923), the paper does not label these
    #    as onset/end. The paper says "exothermic decomposition reaction with
    #    irreversible N loss occurs between 450 and 650 C".
    #    Fix: Change metric labels to match paper description.
    # -------------------------------------------------------------------------
    {
        "paper_id": "L_pez-Aranguren_et_al__-_2021_-_Crystalline_LiPON_as_a_Bulk-Type_Solid_Electrolyte",
        "tier": "simple",
        "entity_path": "characterization[4].results[0]",
        "field_to_fix": "metric",
        "new_value": "decomposition range start",
        "pdf_evidence": "Paper states: 'exothermic decomposition reaction with irreversible N loss occurs between 450 and 650 C' -- not labeled as onset/end"
    },
    {
        "paper_id": "L_pez-Aranguren_et_al__-_2021_-_Crystalline_LiPON_as_a_Bulk-Type_Solid_Electrolyte",
        "tier": "simple",
        "entity_path": "characterization[4].results[1]",
        "field_to_fix": "metric",
        "new_value": "decomposition range end",
        "pdf_evidence": "Paper states: 'between 450 and 650 C' -- a range, not explicit onset/end points"
    },
]


def parse_entity_path(path):
    """Parse entity path like 'targets[0]' or 'characterization[3].results[0]' into list of keys."""
    import re
    parts = []
    for segment in path.split('.'):
        m = re.match(r'(\w+)\[(\d+)\]', segment)
        if m:
            parts.append(m.group(1))
            parts.append(int(m.group(2)))
        else:
            parts.append(segment)
    return parts


def get_nested(data, path_parts):
    """Navigate nested dict/list using path parts."""
    current = data
    for part in path_parts:
        current = current[part]
    return current


def set_nested(data, path_parts, field, value):
    """Set a field in a nested dict/list using path parts."""
    current = data
    for part in path_parts:
        current = current[part]
    current[field] = value


def find_json_file(paper_id):
    """Find the extraction JSON file for a given paper_id."""
    filename = paper_id + "_reactions.json"
    filepath = os.path.join(BASE_DIR, filename)
    if os.path.exists(filepath):
        return filepath
    # Also check root extraction_jsons directory
    root_dir = os.path.dirname(BASE_DIR)
    filepath2 = os.path.join(root_dir, filename)
    if os.path.exists(filepath2):
        return filepath2
    return None


def apply_corrections():
    """Apply all corrections to extraction JSONs."""
    # Group corrections by paper_id
    corrections_by_paper = {}
    for corr in CORRECTIONS:
        pid = corr["paper_id"]
        if pid not in corrections_by_paper:
            corrections_by_paper[pid] = []
        corrections_by_paper[pid].append(corr)

    results = []
    for paper_id, corrs in corrections_by_paper.items():
        json_path = find_json_file(paper_id)
        if json_path is None:
            print(f"WARNING: Could not find JSON for {paper_id}")
            continue

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        original = copy.deepcopy(data)
        changes_made = 0

        for corr in corrs:
            entity_path = corr["entity_path"]
            field = corr["field_to_fix"]
            new_value = corr["new_value"]
            evidence = corr["pdf_evidence"]

            try:
                path_parts = parse_entity_path(entity_path)
                target = get_nested(data, path_parts)
                old_value = target.get(field, "")

                if old_value == new_value:
                    print(f"  SKIP {paper_id} -> {entity_path}.{field}: already correct")
                    continue

                target[field] = new_value
                changes_made += 1
                print(f"  FIX  {paper_id} -> {entity_path}.{field}")
                print(f"       OLD: {repr(old_value)}")
                print(f"       NEW: {repr(new_value)}")
                print(f"       Evidence: {evidence[:100]}...")

                results.append({
                    "paper_id": paper_id,
                    "tier": corr["tier"],
                    "entity_path": entity_path,
                    "field_to_fix": field,
                    "old_value": old_value,
                    "new_value": new_value,
                    "pdf_evidence": evidence
                })

            except (KeyError, IndexError, TypeError) as e:
                print(f"  ERROR {paper_id} -> {entity_path}.{field}: {e}")
                continue

        if changes_made > 0:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  SAVED {json_path} ({changes_made} changes)")
        else:
            print(f"  NO CHANGES for {paper_id}")
        print()

    # Print summary
    print("=" * 70)
    print(f"CORRECTIONS SUMMARY: {len(results)} corrections applied")
    print("=" * 70)
    for r in results:
        print(f"  {r['paper_id']}")
        print(f"    Path:  {r['entity_path']}.{r['field_to_fix']}")
        print(f"    Old:   {repr(r['old_value'])}")
        print(f"    New:   {repr(r['new_value'])}")
        print()

    return results


if __name__ == "__main__":
    print("Applying SIMPLE tier corrections...")
    print("=" * 70)
    results = apply_corrections()
    print(f"\nDone. {len(results)} corrections applied successfully.")
