"""
run_verifier_golden.py
======================
Runs the LLM verification pipeline on the 30-paper Golden Dataset v2.

Reuses the core run_llm_verification() logic from the original run_verifier.py
located in the test_app directory. Only the file-finding and path logic is
adapted for the dataset folder structure.

Input:
    dataset/extraction_jsons/{tier}/*_reactions.json
    dataset/pdfs/{tier}/*.pdf

Output:
    dataset/verified_jsons/{tier}/Verified_*_reactions.json

Usage:
    python scripts/run_verifier_golden.py

Skips any paper that already has a Verified_ file (safe to re-run).
"""

import sys
import os
import json
import fitz  # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv

# ── 1. Paths ─────────────────────────────────────────────────────────────────

BASE_DIR      = Path(r"C:\Users\12124\Downloads\Results_final\Results_final")
GOLDEN_DIR    = BASE_DIR / "dataset"
JSON_BASE     = GOLDEN_DIR / "extraction_jsons"
PDF_BASE      = GOLDEN_DIR / "pdfs"
VERIFIED_BASE = GOLDEN_DIR / "verified_jsons"

# Path to the original test_app so we can import run_llm_verification
TEST_APP_DIR = Path(r"C:\Users\12124\Downloads\Research - Materials Science\Chem_Synthesis\test_app")

# ── 2. Bootstrap ──────────────────────────────────────────────────────────────

# Load .env from test_app (contains OPENAI_API_KEY)
load_dotenv(TEST_APP_DIR / ".env")

# Add test_app to sys.path so we can import run_verifier
sys.path.insert(0, str(TEST_APP_DIR))
from run_verifier import run_llm_verification  # noqa: E402

# ── 3. Windows long-path helper ───────────────────────────────────────────────

def _long_path(p: Path) -> str:
    """Add \\\\?\\ prefix to bypass Windows 260-char MAX_PATH limit."""
    s = str(p.resolve())
    if not s.startswith("\\\\?\\"):
        s = "\\\\?\\" + s
    return s


# ── 4. Single-pair processor ──────────────────────────────────────────────────

def process_single_pair(json_path: Path, pdf_path: Path, out_path: Path):
    """Load JSON + PDF, run verification, save Verified_*.json."""
    print(f"\n{'='*62}")
    print(f"  Processing : {json_path.name}")
    print(f"  PDF        : {pdf_path.name}")
    print(f"  Output     : {out_path.name}")
    print(f"{'='*62}")

    # Load extraction JSON
    with open(_long_path(json_path), "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract full PDF text
    print("  Extracting PDF text...")
    doc = fitz.open(_long_path(pdf_path))
    pdf_text_dict = {i: page.get_text("text") for i, page in enumerate(doc)}
    doc.close()
    print(f"  PDF pages  : {len(pdf_text_dict)}")

    # Run LLM verification (adds _llm_flag to each entity in-place)
    print("  Running LLM verification...")
    verified_data = run_llm_verification(data, pdf_text_dict)

    # Save output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(_long_path(out_path), "w", encoding="utf-8") as f:
        json.dump(verified_data, f, indent=2, ensure_ascii=False)

    print(f"  Saved -> {out_path}")
    return out_path


# ── 5. Pair discovery ──────────────────────────────────────────────────────────

def find_unverified_pairs():
    """
    Scan dataset for JSON-PDF pairs that don't yet have a
    Verified_ output file. Returns list of (json_path, pdf_path, out_path).
    """
    pairs = []
    tiers = ["simple", "moderate", "complex"]

    for tier in tiers:
        json_dir     = JSON_BASE / tier
        pdf_dir      = PDF_BASE  / tier
        verified_dir = VERIFIED_BASE / tier

        if not json_dir.exists():
            print(f"[WARN] JSON dir not found: {json_dir}")
            continue

        for json_file in sorted(json_dir.glob("*_reactions.json")):
            # Derive PDF filename: strip _reactions.json -> .pdf
            base_name = json_file.stem.replace("_reactions", "")
            pdf_file  = pdf_dir / f"{base_name}.pdf"

            if not pdf_file.exists():
                print(f"[SKIP] No PDF for {json_file.name}")
                continue

            out_file = verified_dir / f"Verified_{json_file.name}"
            if out_file.exists():
                print(f"[SKIP] Already verified: {json_file.name}")
                continue

            pairs.append((json_file, pdf_file, out_file))

    return pairs


# ── 6. Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 62)
    print("  Golden Dataset v2 — LLM Verification Pipeline")
    print("=" * 62)

    pairs = find_unverified_pairs()

    if not pairs:
        print("\nAll papers already verified (or no pairs found). Exiting.")
        sys.exit(0)

    print(f"\nFound {len(pairs)} unverified papers:")
    for jp, pp, op in pairs:
        tier = jp.parent.name
        print(f"  [{tier:8s}] {jp.name}")

    successful, failed = 0, 0

    for json_path, pdf_path, out_path in pairs:
        try:
            process_single_pair(json_path, pdf_path, out_path)
            successful += 1
        except Exception as e:
            print(f"\n[ERROR] {json_path.name}: {e}")
            failed += 1

    print(f"\n{'='*62}")
    print(f"  DONE: {successful} verified, {failed} failed  (total {len(pairs)})")
    print(f"  Verified files saved to: {VERIFIED_BASE}")
    print(f"{'='*62}")
    print("\nNext step: python scripts/update_review_templates.py")
