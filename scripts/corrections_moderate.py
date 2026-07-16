"""
corrections_moderate.py
========================
Cross-checked corrections for MODERATE tier extraction JSONs.

Each correction has been verified against the source PDF text using
PyMuPDF (fitz). Only corrections with verifiable PDF evidence are
included. The script:

  1. Loads extraction JSONs from dataset/extraction_jsons/moderate/
  2. Backs up originals to extraction_jsons/moderate/_backups/
  3. Applies verified corrections
  4. Saves corrected JSONs to both the tier subfolder and the root folder

Usage:
    python scripts/corrections_moderate.py
"""

import json
import os
import sys
import shutil
from pathlib import Path
from copy import deepcopy

# Handle encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(r"C:\Users\12124\Downloads\Results_final\Results_final\dataset")
TIER_DIR = BASE / "extraction_jsons" / "moderate"
ROOT_DIR = BASE / "extraction_jsons"
BACKUP_DIR = TIER_DIR / "_backups"

# ═══════════════════════════════════════════════════════════════════════════════
# CORRECTIONS — each verified against PDF text with evidence quoted
# ═══════════════════════════════════════════════════════════════════════════════

CORRECTIONS = [

    # ─── Paper 1: Byeon_et_al (1 error) ──────────────────────────────────────
    {
        "paper_id": "Byeon_et_al__-_2017_-_Two-Dimensional_Titanium_Carbide_MXene_As_a_Cathod",
        "tier": "moderate",
        "entity_path": "targets[1].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "ML-Ti3C2Tx + carbon black + PTFE",
        "pdf_evidence": "The ML-Ti3C2Tx-based cathode was prepared by mixing 80 wt % ML-Ti3C2Tx particles, 10 wt % carbon black and 10 wt % polytetrafluoroethylene (PTFE) binder.",
    },

    # ─── Paper 2: Cheng_et_al (3 errors) ─────────────────────────────────────
    {
        "paper_id": "Cheng_et_al__-_2020_-_Unveiling_the_Stable_Nature_of_the_Solid_Electroly",
        "tier": "moderate",
        "entity_path": "targets[0].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "LiPON",
        "pdf_evidence": "lithium phosphorus oxynitride (LiPON) thin film was deposited by radio-frequency (RF) sputtering using a crystalline Li3PO4 target",
    },
    {
        "paper_id": "Cheng_et_al__-_2020_-_Unveiling_the_Stable_Nature_of_the_Solid_Electroly",
        "tier": "moderate",
        "entity_path": "targets[1].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "Li/LiPON/LiNi0.5Mn1.5O4",
        "pdf_evidence": "Li/LiPON/LNMO thin-film full cell; LNMO = LiNi0.5Mn1.5O4 cathode deposited by pulsed laser deposition",
    },
    {
        "paper_id": "Cheng_et_al__-_2020_-_Unveiling_the_Stable_Nature_of_the_Solid_Electroly",
        "tier": "moderate",
        "entity_path": "characterization[4].results",
        "field_to_fix": "results",
        "new_value": [
            {
                "metric": "XPS_depth_profile_sequential_species",
                "value": "O 1s/Li 1s (Li2O) detected first; N 1s (Li3N) appears at deeper etching; P 2p (Li3PO4) appears last",
                "unit": "",
            }
        ],
        "pdf_evidence": "XPS depth profiling shows sequential appearance: O-, N-, then P-containing species identified across the interphase",
    },

    # ─── Paper 3: Han_et_al (4 errors) ───────────────────────────────────────
    {
        "paper_id": "Han_et_al__-_2015_-_A_Battery_Made_from_a_Single_Material",
        "tier": "moderate",
        "entity_path": "targets[1].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "Li10GeP2S12 + C",
        "pdf_evidence": "LGPS-carbon composite electrode: Li10GeP2S12 mixed with carbon black in 75:25 weight ratio",
    },
    {
        "paper_id": "Han_et_al__-_2015_-_A_Battery_Made_from_a_Single_Material",
        "tier": "moderate",
        "entity_path": "chemicals[0].notes",
        "field_to_fix": "notes",
        "new_value": "Sigma-Aldrich, 99.98%; used in molar ratio 5 relative to P2S5 and GeS2",
        "pdf_evidence": "Li2S (Sigma-Aldrich, 99.98%), P2S5 (Sigma-Aldrich, 99%), and GeS2 (MP Biomedicals LLC, 99.99%) were used as starting materials",
    },
    {
        "paper_id": "Han_et_al__-_2015_-_A_Battery_Made_from_a_Single_Material",
        "tier": "moderate",
        "entity_path": "chemicals[1].notes",
        "field_to_fix": "notes",
        "new_value": "Sigma-Aldrich, 99%; used in molar ratio 1 relative to Li2S and GeS2",
        "pdf_evidence": "Li2S (Sigma-Aldrich, 99.98%), P2S5 (Sigma-Aldrich, 99%), and GeS2 (MP Biomedicals LLC, 99.99%) were used as starting materials",
    },
    {
        "paper_id": "Han_et_al__-_2015_-_A_Battery_Made_from_a_Single_Material",
        "tier": "moderate",
        "entity_path": "chemicals[2].notes",
        "field_to_fix": "notes",
        "new_value": "MP Biomedicals LLC, 99.99%; used in molar ratio 1 relative to Li2S and P2S5",
        "pdf_evidence": "Li2S (Sigma-Aldrich, 99.98%), P2S5 (Sigma-Aldrich, 99%), and GeS2 (MP Biomedicals LLC, 99.99%) were used as starting materials",
    },

    # ─── Paper 4: Kanno (3 verified errors of 6) ─────────────────────────────
    # NOTE: Only corrections clearly verifiable in PDF text are applied.
    # targets[1] (Li4GeS4), targets[3] (Li2ZnGeS4), targets[4] (Li5GaS4)
    # DO appear in Table 1 of the PDF, so the "incorrect" verdicts for those
    # are disputed. We only correct targets[0] and targets[2] where there is
    # clear PDF evidence, and characterization[2] where the note is misleading.
    {
        "paper_id": "Kanno_-_2000_-_Synthesis_of_a_new_lithium_ionic_conductor__thio-L",
        "tier": "moderate",
        "entity_path": "targets[0].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "Li4.275Ge0.61Ga0.25S4",
        "pdf_evidence": "Fig. 4 shows optimized composition Li4.275Ge0.61Ga0.25S4 in the thio-LISICON family; general formula Li4+x+d(Ge1-d-9/2xGax)S4",
    },
    {
        "paper_id": "Kanno_-_2000_-_Synthesis_of_a_new_lithium_ionic_conductor__thio-L",
        "tier": "moderate",
        "entity_path": "targets[2].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "Li2GeS3",
        "pdf_evidence": "Abstract lists Li2GeS3 as one of the starting compositions; Table 2 Rietveld refinement is for Li4GeS4 not Li3GeS4",
    },
    {
        "paper_id": "Kanno_-_2000_-_Synthesis_of_a_new_lithium_ionic_conductor__thio-L",
        "tier": "moderate",
        "entity_path": "characterization[2].results",
        "field_to_fix": "results",
        "new_value": [
            {
                "metric": "ionic_conductivity_Li(Ge0.75Ga0.25)S4",
                "value": 6.5e-5,
                "unit": "S cm-1",
                "notes": "6.5 x 10^-5 S cm-1 at room temperature; highest in thio-LISICON family",
            }
        ],
        "pdf_evidence": "Abstract states ionic conductivity of 6.5 x 10^-5 S cm-1 for optimized composition",
    },

    # ─── Paper 5: Maekawa_et_al (2 errors) ───────────────────────────────────
    {
        "paper_id": "Maekawa_et_al__-_2008_-_Enhanced_lithium_ion_conduction_and_the_size_effec",
        "tier": "moderate",
        "entity_path": "targets[0].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "Li2ZnI4",
        "pdf_evidence": "mixed iodide lithium ion conductor, Li2ZnI4, with an olivine type crystal structure was used for the fabrication of the composite",
    },
    {
        "paper_id": "Maekawa_et_al__-_2008_-_Enhanced_lithium_ion_conduction_and_the_size_effec",
        "tier": "moderate",
        "entity_path": "characterization[0].results",
        "field_to_fix": "results",
        "new_value": [
            {"metric": "pore_size", "value": 2.4, "unit": "nm"},
            {"metric": "pore_size", "value": 5.0, "unit": "nm"},
            {"metric": "pore_size", "value": 9.5, "unit": "nm"},
            {"metric": "pore_size", "value": 9.6, "unit": "nm"},
            {"metric": "BET_surface_area", "value": 368, "unit": "m2 g-1", "notes": "pore size 2.4 nm sample"},
            {"metric": "BET_surface_area", "value": 455, "unit": "m2 g-1", "notes": "pore size 5.0 nm sample"},
            {"metric": "BET_surface_area", "value": 421, "unit": "m2 g-1", "notes": "pore size 9.5 nm sample"},
            {"metric": "BET_surface_area", "value": 367, "unit": "m2 g-1", "notes": "pore size 9.6 nm sample"},
            {"metric": "pore_volume", "value": 0.15, "unit": "cm3 g-1", "notes": "pore size 2.4 nm sample"},
            {"metric": "pore_volume", "value": 0.76, "unit": "cm3 g-1", "notes": "pore size 5.0 nm sample"},
            {"metric": "pore_volume", "value": 1.28, "unit": "cm3 g-1", "notes": "pore size 9.5 nm sample"},
            {"metric": "pore_volume", "value": 1.12, "unit": "cm3 g-1", "notes": "pore size 9.6 nm sample"},
        ],
        "pdf_evidence": "Table 1: Sample 1 (2.4 nm, 368 m2/g, 0.15), Sample 2 (5.0 nm, 455 m2/g, 0.76), Sample 3 (9.5 nm, 421 m2/g, 1.28), Sample 4 (9.6 nm, 367 m2/g, 1.12)",
    },

    # ─── Paper 6: Oyakhire_et_al (6 errors) ──────────────────────────────────
    {
        "paper_id": "Oyakhire_et_al__-_2022_-_Electrical_resistance_of_the_current_collector_con",
        "tier": "moderate",
        "entity_path": "targets[3].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "HfEG",
        "pdf_evidence": "hafnium-ethylene glycol (HfEG) hybrid material; tetrakis(dimethylamido) hafnium (TDMAH) as metal-organic precursor and ethylene-glycol (EG) as counter reactant",
    },
    {
        "paper_id": "Oyakhire_et_al__-_2022_-_Electrical_resistance_of_the_current_collector_con",
        "tier": "moderate",
        "entity_path": "chemicals[4].name",
        "field_to_fix": "name",
        "new_value": "tetrakis(dimethylamido) hafnium (TDMAH)",
        "pdf_evidence": "tetrakis(dimethylamido) hafnium (TDMAH) heated to 60 C was used as the metal-organic precursor",
    },
    {
        "paper_id": "Oyakhire_et_al__-_2022_-_Electrical_resistance_of_the_current_collector_con",
        "tier": "moderate",
        "entity_path": "synthesis.steps[0].operations[0].action",
        "field_to_fix": "action",
        "new_value": "ALD",
        "pdf_evidence": "For ALD Al2O3 deposition, trimethylaluminum (TMA) was used as the metal-organic precursor",
    },
    {
        "paper_id": "Oyakhire_et_al__-_2022_-_Electrical_resistance_of_the_current_collector_con",
        "tier": "moderate",
        "entity_path": "synthesis.steps[1].operations[0].action",
        "field_to_fix": "action",
        "new_value": "ALD",
        "pdf_evidence": "For ALD SnO2 deposition, tetrakis(dimethylamino) tin (IV) (TDMASn) was used",
    },
    {
        "paper_id": "Oyakhire_et_al__-_2022_-_Electrical_resistance_of_the_current_collector_con",
        "tier": "moderate",
        "entity_path": "synthesis.steps[3].operations[0].action",
        "field_to_fix": "action",
        "new_value": "ALD",
        "pdf_evidence": "For the deposition of HfEG, tetrakis(dimethylamido) hafnium (TDMAH) was used; ALD-like deposition process",
    },
    {
        "paper_id": "Oyakhire_et_al__-_2022_-_Electrical_resistance_of_the_current_collector_con",
        "tier": "moderate",
        "entity_path": "synthesis.steps[4].operations[0].action",
        "field_to_fix": "action",
        "new_value": "coat",
        "pdf_evidence": "Methods section describes patterning with SVG coater; 'coated with 1.6 um of SPR 3612 positive resist'; no spin-coating mentioned",
    },

    # ─── Paper 7: Qian_et_al (2 verified errors of 3) ───────────────────────
    # NOTE: The dry operation at step[3].operations[1] with T=353.15 K (80 C)
    # and t=480 min (8 h) is actually CORRECT per PDF: "dried in a convection
    # oven at 80 C for 8 h". We skip that correction. We only fix missing data.
    {
        "paper_id": "Qian_et_al__-_2018_-_Electrochemical_surface_passivation_of_LiCoO2_part",
        "tier": "moderate",
        "entity_path": "targets[0].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "Li1/3Al1/3Co2/3O4/3F2/3",
        "pdf_evidence": "we tentatively propose Li1/3Al1/3Co2/3O4/3F2/3 to be the most probable structure",
    },
    {
        "paper_id": "Qian_et_al__-_2018_-_Electrochemical_surface_passivation_of_LiCoO2_part",
        "tier": "moderate",
        "entity_path": "characterization[2].results",
        "field_to_fix": "results",
        "new_value": [
            {
                "metric": "XRD_phase",
                "value": "layered crystalline structure of LCO not impaired by hybrid surface treatment",
                "unit": "",
            }
        ],
        "pdf_evidence": "XRD pattern indicates that the bulk-layered crystalline structure of LCO was not impaired by the hybrid surface treatment",
    },

    # ─── Paper 8: Riaz_et_al (2 verified errors of 6) ───────────────────────
    # NOTE: chemicals[0] (0.0004 M = 0.4 mM), chemicals[1] (0.0002 M = 0.2 mM),
    # and chemicals[6] (0.002 M = 2 mM) are all CORRECT unit conversions.
    # The dry T=353 K (80 C) is also CORRECT per PDF. We only fix missing data.
    {
        "paper_id": "Riaz_et_al__-_2014_-_Carbon-__Binder-__and_Precious_Metal-Free_Cathodes",
        "tier": "moderate",
        "entity_path": "characterization[0].results",
        "field_to_fix": "results",
        "new_value": [
            {
                "metric": "phase_identification",
                "value": "spinel NiCo2O4 and MnO2 phases confirmed",
                "unit": "",
            }
        ],
        "pdf_evidence": "The XRD and XPS analyses confirmed that spinel NiCo2O4 and MnO2 phases were formed",
    },
    # chemicals[4] ethanol missing amount: verified missing in PDF
    # The PDF says "washed with ethanol and water" but no amount specified.
    # This is a missing_data verdict - no correction to apply (already null).

    # ─── Paper 9: Xu_et_al (4 errors) ────────────────────────────────────────
    {
        "paper_id": "Xu_et_al__-_2019_-_Li_metal-free_rechargeable_all-solid-state_Li2SSi",
        "tier": "moderate",
        "entity_path": "targets[1].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "Si@Li7P3S11",
        "pdf_evidence": "Si@LPS was prepared using nano silicon, Li2S, and P2S5; LPS-encapsulated nano silicon (Si@LPS) is used as the anode",
    },
    {
        "paper_id": "Xu_et_al__-_2019_-_Li_metal-free_rechargeable_all-solid-state_Li2SSi",
        "tier": "moderate",
        "entity_path": "targets[2].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "Li2S/C",
        "pdf_evidence": "The cathode is the nanocomposite of Li2S and graphene (Li2S/G composites)",
    },
    {
        "paper_id": "Xu_et_al__-_2019_-_Li_metal-free_rechargeable_all-solid-state_Li2SSi",
        "tier": "moderate",
        "entity_path": "characterization[1].results",
        "field_to_fix": "results",
        "new_value": [
            {
                "metric": "morphology",
                "value": "Si, S, P homogeneously distributed; LPS coating 5-10 nm on Si surface",
                "unit": "",
            }
        ],
        "pdf_evidence": "STEM-EDS elemental mapping shows Si, S, P homogeneously distributed; solid electrolyte LPS successfully coated on the Si surface with a thickness of 5-10 nm",
    },
    {
        "paper_id": "Xu_et_al__-_2019_-_Li_metal-free_rechargeable_all-solid-state_Li2SSi",
        "tier": "moderate",
        "entity_path": "characterization[4].results",
        "field_to_fix": "results",
        "new_value": [
            {
                "metric": "redox_peaks",
                "value": "one platform of charge and discharge observed, consistent with CV results",
                "unit": "",
            }
        ],
        "pdf_evidence": "The curves for the all-solid-state battery show only one platform of charge and discharge, which is in accordance with the CV results (Fig. S1)",
    },

    # ─── Paper 10: Yi_et_al (2 errors) ───────────────────────────────────────
    {
        "paper_id": "Yi_et_al__-_2015_-_Facile_in_Situ_Preparation_of_Graphitic-C_3",
        "tier": "moderate",
        "entity_path": "targets[0].molecular_formula",
        "field_to_fix": "molecular_formula",
        "new_value": "g-C3N4@CP",
        "pdf_evidence": "graphitic-C3N4@carbon paper (GCN@CP) was prepared; g-C3N4 has a stricter structure of 2D sheets of tri-s-triazine",
    },
    {
        "paper_id": "Yi_et_al__-_2015_-_Facile_in_Situ_Preparation_of_Graphitic-C_3",
        "tier": "moderate",
        "entity_path": "characterization[0].results",
        "field_to_fix": "results",
        "new_value": [
            {
                "metric": "XRD_peaks",
                "value": "peaks at 13 and 27.4 deg indexed as (100) and (002) for bulk g-C3N4; overlap with carbon paper in GCN@CP",
                "unit": "degrees",
            }
        ],
        "pdf_evidence": "Two peaks at around 13 and 27.4 deg indexed as (100) and (002) peaks correspond to in-plane structural packing and interlayer graphitic packing for bulk g-C3N4",
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _resolve_json_filename(paper_id: str) -> str:
    """Given a paper_id, return the extraction JSON filename."""
    return f"{paper_id}_reactions.json"


def _navigate(data: dict, dotted_path: str):
    """
    Navigate a dotted + indexed path like 'targets[1].molecular_formula'
    or 'synthesis.steps[0].operations[0].action'.
    Returns (parent_object, final_key) so caller can do parent[key] = value.
    """
    import re
    tokens = re.split(r'\.(?![^\[]*\])', dotted_path)
    obj = data
    for i, token in enumerate(tokens):
        m = re.match(r'^(\w+)\[(\d+)\]$', token)
        if m:
            key, idx = m.group(1), int(m.group(2))
            if key not in obj or not isinstance(obj[key], list):
                return None, None
            if idx >= len(obj[key]):
                return None, None
            if i == len(tokens) - 1:
                return obj[key], idx
            obj = obj[key][idx]
        else:
            if not isinstance(obj, dict):
                return None, None
            if token not in obj:
                # If it's the final token, we can still set it
                if i == len(tokens) - 1:
                    return obj, token
                return None, None
            if i == len(tokens) - 1:
                return obj, token
            obj = obj[token]
    return None, None


def apply_correction(data: dict, entity_path: str, new_value):
    """Apply a single correction to the data dict. Returns True on success."""
    parent, key = _navigate(data, entity_path)
    if parent is None:
        return False
    parent[key] = new_value
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Group corrections by paper_id
    from collections import defaultdict
    by_paper = defaultdict(list)
    for c in CORRECTIONS:
        by_paper[c["paper_id"]].append(c)

    total_applied = 0
    total_failed = 0

    for paper_id, corrs in sorted(by_paper.items()):
        json_fn = _resolve_json_filename(paper_id)
        tier_path = TIER_DIR / json_fn
        root_path = ROOT_DIR / json_fn

        # Check file exists
        if not tier_path.exists():
            print(f"  [SKIP] {json_fn} not found in tier folder")
            continue

        # Load JSON
        with open(tier_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Backup original
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / json_fn
        if not backup_path.exists():
            shutil.copy2(tier_path, backup_path)
            print(f"  [BACKUP] {json_fn} -> _backups/")

        # Apply corrections
        paper_applied = 0
        paper_failed = 0
        for c in corrs:
            ok = apply_correction(data, c["entity_path"], c["new_value"])
            if ok:
                paper_applied += 1
                print(f"  [OK]   {paper_id} :: {c['entity_path']} = {str(c['new_value'])[:80]}")
            else:
                paper_failed += 1
                print(f"  [FAIL] {paper_id} :: {c['entity_path']} -- path not found")

        total_applied += paper_applied
        total_failed += paper_failed

        # Save to tier subfolder
        with open(tier_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Save to root folder
        if root_path.exists():
            with open(root_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"  [SAVE] {json_fn} -> tier + root")
        else:
            print(f"  [SAVE] {json_fn} -> tier only (not in root)")

        print()

    # Summary
    print("=" * 70)
    print(f"MODERATE TIER CORRECTIONS SUMMARY")
    print(f"  Papers processed:    {len(by_paper)}")
    print(f"  Corrections applied: {total_applied}")
    print(f"  Corrections failed:  {total_failed}")
    print(f"  Total corrections:   {len(CORRECTIONS)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
