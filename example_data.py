"""
Reusable example inputs for the synthesis agent.

These fixtures are derived from the March 14, 2026 campaign stored in:
    crystal_results/results_history_compress_2D_symmetry_with_compress_tool_VASP_multiple_sampling.json

The goal is to give interns a couple of realistic AgentState inputs that
already match the current synthesis-agent schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    from synthesis_agent.state import AgentState, ExperimentRecord, create_synthesis_input
except ModuleNotFoundError:
    # Allows `python synthesis_agent/example_data.py` from the repo root.
    from state import AgentState, ExperimentRecord, create_synthesis_input


EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"
STRUCTURES_DIR = EXAMPLES_DIR / "structures"


def _structure_path(filename: str) -> str:
    return str((STRUCTURES_DIR / filename).resolve())


def _read_cif(filename: str) -> str:
    return (STRUCTURES_DIR / filename).read_text()


def get_example_structures() -> Dict[str, Dict[str, Any]]:
    """
    Return lightweight structure metadata for the bundled CIF examples.

    Note:
        The stored CIFs declare P1 symmetry, while current_spacegroup in the
        example states preserves the nominal generation space group from the
        source campaign.
    """
    return {
        "mote2_candidate3_unstrained": {
            "formula": "MoTe2",
            "selected_candidate": "candidate_3",
            "nominal_spacegroup": 11,
            "cif_declared_spacegroup": 1,
            "atom_count": 6,
            "cif_path": _structure_path("mote2_candidate3_unstrained.cif"),
            "source_result_id": 2,
            "summary": (
                "MoTe2 candidate_3 selected from the 3% compression sweep because "
                "it had the lowest formation energy in that run and adsorption "
                "became favorable after compression."
            ),
        },
        "mo9wte20_candidate1_compressed_2pct": {
            "formula": "Mo9WTe20",
            "selected_candidate": "candidate_1_compressed_2pct",
            "nominal_spacegroup": 164,
            "cif_declared_spacegroup": 1,
            "atom_count": 30,
            "cif_path": _structure_path("mo9wte20_candidate1_compressed_2pct.cif"),
            "source_result_id": 5,
            "summary": (
                "Compressed Mo9WTe20 candidate_1 chosen for follow-up because the "
                "2% strained structure had the most favorable OCP adsorption energy "
                "among the screened candidates."
            ),
        },
    }


def load_example_states() -> Dict[str, AgentState]:
    """
    Build a couple of realistic synthesis-agent input states.

    Returns:
        Dict keyed by example name.
    """
    mote2_cif = _read_cif("mote2_candidate3_unstrained.cif")
    mo9wte20_unstrained_cif = _read_cif("mo9wte20_candidate1_unstrained.cif")
    mo9wte20_compressed_cif = _read_cif("mo9wte20_candidate1_compressed_2pct.cif")

    mote2_state = create_synthesis_input(
        formula="MoTe2",
        cif_data=mote2_cif,
        cif_path=_structure_path("mote2_candidate3_unstrained.cif"),
        spacegroup=11,
        predicted_properties={
            "source_result_id": 2,
            "screening_campaign": (
                "compress_2D_symmetry_with_compress_tool_VASP_multiple_sampling"
            ),
            "selected_candidate": "candidate_3",
            "candidate_metrics": {
                "formation_energy_eV_per_atom_unstrained": 0.036471955478191376,
                "bandgap_mbj_eV_unstrained": 0.24626076221466064,
                "formation_energy_eV_per_atom_3pct_compressed": 0.004885464906692505,
                "bandgap_mbj_eV_3pct_compressed": 0.07444657385349274,
                "ocp_adsorption_eV_unstrained": 0.1750066727399826,
                "ocp_adsorption_eV_3pct_compressed": -0.15861459076404572,
                "work_function_eV_3pct_compressed": 4.412285327911377,
            },
            "all_candidate_summaries": [
                {
                    "label": "candidate_1",
                    "formation_energy_eV_per_atom_unstrained": 0.702854335308075,
                    "bandgap_mbj_eV_unstrained": 0.4138108789920807,
                    "formation_energy_eV_per_atom_3pct_compressed": 0.7185009121894836,
                    "bandgap_mbj_eV_3pct_compressed": 0.370039165019989,
                },
                {
                    "label": "candidate_2",
                    "formation_energy_eV_per_atom_unstrained": 0.6548939347267151,
                    "bandgap_mbj_eV_unstrained": 0.1011715829372406,
                    "formation_energy_eV_per_atom_3pct_compressed": 0.6674183011054993,
                    "bandgap_mbj_eV_3pct_compressed": 0.21976280212402344,
                },
                {
                    "label": "candidate_3",
                    "formation_energy_eV_per_atom_unstrained": 0.036471955478191376,
                    "bandgap_mbj_eV_unstrained": 0.24626076221466064,
                    "formation_energy_eV_per_atom_3pct_compressed": 0.004885464906692505,
                    "bandgap_mbj_eV_3pct_compressed": 0.07444657385349274,
                    "ocp_adsorption_eV_unstrained": 0.1750066727399826,
                    "ocp_adsorption_eV_3pct_compressed": -0.15861459076404572,
                    "work_function_eV_3pct_compressed": 4.412285327911377,
                },
                {
                    "label": "candidate_4",
                    "formation_energy_eV_per_atom_unstrained": 0.18026065826416016,
                    "bandgap_mbj_eV_unstrained": 0.0900634229183197,
                    "formation_energy_eV_per_atom_3pct_compressed": 0.19638806581497192,
                    "bandgap_mbj_eV_3pct_compressed": 0.11795181035995483,
                },
                {
                    "label": "candidate_5",
                    "formation_energy_eV_per_atom_unstrained": 0.16583546996116638,
                    "bandgap_mbj_eV_unstrained": 0.19535858929157257,
                    "formation_energy_eV_per_atom_3pct_compressed": 0.12237723916769028,
                    "bandgap_mbj_eV_3pct_compressed": 0.14498405158519745,
                },
            ],
            "selection_notes": (
                "Candidate_3 is the most promising MoTe2 example from the sweep: "
                "lowest formation energy, smaller band gap under compression, and "
                "adsorption changing from positive to negative at 3% compression."
            ),
        },
        user_request=(
            "Discover a distorted 2D TMD where <3% compressive strain induces a "
            "phase transition to a high-symmetry metallic phase with superior HER "
            "activity."
        ),
        experiments_log=[],
    )

    mo9wte20_history: ExperimentRecord = {
        "formula": "Mo9WTe20",
        "cif_data": mo9wte20_unstrained_cif,
        "cif_path": _structure_path("mo9wte20_candidate1_unstrained.cif"),
        "properties": {
            "source_result_id": 5,
            "candidate_label": "candidate_1",
            "formation_energy_eV_per_atom": 0.1417084038257599,
            "mbj_bandgap_unstrained_eV": 0.12408186495304108,
            "exfoliation_energy_mev_per_atom": 93.936767578125,
            "selection_stage": "pre-compression screening",
        },
        "valid": True,
        "error_message": None,
        "tools_used": [
            "batch_structure_generator",
            "predict_formation_energy",
            "predict_bandgap_mbj",
            "predict_exfoliation_energy",
        ],
    }

    mo9wte20_state = create_synthesis_input(
        formula="Mo9WTe20",
        cif_data=mo9wte20_compressed_cif,
        cif_path=_structure_path("mo9wte20_candidate1_compressed_2pct.cif"),
        spacegroup=164,
        predicted_properties={
            "source_result_id": 5,
            "screening_campaign": (
                "compress_2D_symmetry_with_compress_tool_VASP_multiple_sampling"
            ),
            "selected_candidate": "candidate_1_compressed_2pct",
            "candidate_metrics": {
                "formation_energy_eV_per_atom_unstrained": 0.1417084038257599,
                "mbj_bandgap_unstrained_eV": 0.12408186495304108,
                "exfoliation_energy_mev_per_atom": 93.936767578125,
                "mbj_bandgap_compressed_2pct_eV": 0.09745396673679352,
                "ocp_adsorption_compressed_2pct_eV": -0.3286680579185486,
            },
            "other_promising_candidates": {
                "candidate_2": {
                    "formation_energy_eV_per_atom": 0.12309887260198593,
                    "mbj_bandgap_compressed_2pct_eV": 0.1699834167957306,
                    "ocp_adsorption_compressed_2pct_eV": 0.235213503241539,
                },
                "candidate_4": {
                    "formation_energy_eV_per_atom": 0.15270453691482544,
                    "mbj_bandgap_compressed_2pct_eV": 0.08446463942527771,
                    "ocp_adsorption_compressed_2pct_eV": 0.18202327191829681,
                },
            },
            "selection_notes": (
                "Candidate_1 compressed by 2% was forwarded to VASP because it had "
                "the most favorable OCP adsorption energy, a small predicted band "
                "gap, and finite DOS near the Fermi level in the screening run."
            ),
        },
        user_request=(
            "Discover a distorted 2D TMD/MXene where <3% compressive strain induces "
            "a phase transition to a high-symmetry metallic phase with superior HER "
            "activity."
        ),
        experiments_log=[mo9wte20_history],
    )
    mo9wte20_state["feedbacks"] = [
        "Continue from the 2% compressed candidate_1 structure for synthesis planning."
    ]
    mo9wte20_state["iteration_count"] = 1

    return {
        "mote2_candidate3_initial": mote2_state,
        "mo9wte20_candidate1_followup": mo9wte20_state,
    }


def dump_example_states(indent: int = 2) -> str:
    """Return the bundled example states as JSON."""
    return json.dumps(load_example_states(), indent=indent)


if __name__ == "__main__":
    print(dump_example_states())
