import json
import re
from rdkit import Chem
from IPython.display import display, Markdown
import os
import glob
from PyPDF2 import PdfReader
import csv

pt = Chem.GetPeriodicTable()
symbols = [pt.GetElementSymbol(i) for i in range(1, 119)]

def parse_formula(formula):
    return re.findall(r'[A-Z][a-z]?', re.sub(r'[0-9.()]+', '', formula))

def is_valid_formula(formula):
    if not formula or formula == "":
        return True
    elems = parse_formula(formula)
    invalid = [e for e in elems if e not in symbols]
    return len(invalid) == 0

def score_field(condition):
    return 1 if condition else 0

def check_list(obj):
    return isinstance(obj, list) and len(obj) >= 0

def check_str(obj):
    return isinstance(obj, str)

def check_dict(obj):
    return isinstance(obj, dict)

def check_exists(obj, key):
    return key in obj and obj[key] not in [None, "", []]

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def score_provenance(entry):
    """Check if provenance exists and is reasonable."""
    if "prov" not in entry:
        return 0
    if not isinstance(entry["prov"], list):
        return 0
    if len(entry["prov"]) == 0:
        return 0
    ok = any(any(x in str(p) for x in ["Page", "Figure", "Table", "S"]) for p in entry["prov"])
    return 1 if ok else 0

def check_no_hallucination(text, json_entry):
    """
    Detect suspicious hallucinations by checking if names/descriptions exist in text.
    """
    suspicious = []
    if "chemicals" in json_entry:
        for c in json_entry["chemicals"]:
            name = c.get("name", "").lower()
            if name and name not in text.lower():
                suspicious.append(f"Chemical name '{name}'")

    # Targets names
    if "targets" in json_entry:
        for t in json_entry["targets"]:
            name = t.get("compound_name", "").lower()
            if name and name not in text.lower():
                suspicious.append(f"Target name '{name}'")

    # Step descriptions
    if "synthesis" in json_entry:
        for s in json_entry["synthesis"].get("steps", []):
            desc = s.get("description", "").lower()
            if desc and desc not in text.lower():
                suspicious.append(f"Step description '{desc}'")

    # Characterization methods
    methods = [x.get("method", "").lower() for x in json_entry.get("characterization", [])]
    for m in methods:
        if m and m not in text.lower():
            if m.upper() not in ["SEM", "TGA", "XRD", "XPS", "EDS", "AFM", "TEM", "STEM", "CV"]:
                suspicious.append(f"Method '{m}'")

    # Threshold: >3 suspicious → fail
    if len(suspicious) > 3:
        return 0, suspicious
    else:
        return 1, suspicious

def check_units(data):
    """Check if units match the units_policy from schema."""
    policy = {
        "temperature": "K", "pressure": "bar", "time": "min", "mass": "g",
        "volume": "mL", "amount": "mmol", "concentration": "M",
        "capacity": "mAh g-1"
    }
    ok = True
    suspicious_units = []

    # Check synthesis steps conditions
    if "synthesis" in data:
        for step in data["synthesis"].get("steps", []):
            temp = step.get("temperature", {}) or step.get("conditions", {}).get("temperature", {})
            if isinstance(temp, dict) and temp.get("unit") and temp["unit"] != policy["temperature"]:
                ok = False
                suspicious_units.append(f"Temperature unit '{temp['unit']}' != 'K'")
            # Pressure
            press = step.get("pressure", {}) or step.get("conditions", {}).get("pressure", {})
            if isinstance(press, dict) and press.get("unit") and press["unit"] != policy["pressure"]:
                ok = False
                suspicious_units.append(f"Pressure unit '{press['unit']}' != 'bar'")
            # Time
            dur = step.get("duration", {})
            if isinstance(dur, dict) and dur.get("unit") and dur["unit"] != policy["time"]:
                ok = False
                suspicious_units.append(f"Duration unit '{dur['unit']}' != 'min'")

    # Check chemicals amounts
    if "chemicals" in data:
        for c in data["chemicals"]:
            amt = c.get("amount", {})
            if isinstance(amt, dict) and amt.get("unit"):
                unit = amt["unit"]
                if unit == "g" and unit != policy["mass"]:
                    pass
                elif unit == "mL" and unit != policy["volume"]:
                    ok = False
                    suspicious_units.append(f"Volume unit '{unit}' != 'mL'")

    # Final outcomes
    outcomes = data.get("final_outcomes", {})
    if outcomes.get("yield", {}).get("unit") != "%":
        ok = False
        suspicious_units.append("Yield unit != '%'")
    if outcomes.get("capacity", {}).get("unit") != policy["capacity"]:
        ok = False
        suspicious_units.append(f"Capacity unit != '{policy['capacity']}'")

    return ok, suspicious_units

def evaluate_extraction(text, data):
    score = 0
    total = 0
    details = []

    fields = ["schema", "source", "metadata", "targets",
              "chemicals", "synthesis", "workflow",
              "characterization", "analysis", "final_outcomes",
              "extraction_metadata"]

    for f in fields:
        total += 1
        ok = f in data
        score += score_field(ok)
        details.append((f"Field '{f}' present", ok))

    if "targets" in data:
        for t in data["targets"]:
            total += 4  # formula check
            ok1 = check_exists(t, "compound_name")
            ok2 = score_provenance(t)
            ok3 = check_exists(t, "intended_role")
            ok4 = is_valid_formula(t.get("molecular_formula", ""))

            score += ok1 + ok2 + ok3 + ok4
            details.append((f"targets[{data['targets'].index(t)}].compound_name: `{t.get('compound_name','')}` → Has name", ok1))
            details.append((f"targets[{data['targets'].index(t)}].prov: `{t.get('prov',[])}` → Provenance valid", ok2))
            details.append((f"targets[{data['targets'].index(t)}].intended_role: `{t.get('intended_role','')}` → Has role", ok3))
            details.append((f"targets[{data['targets'].index(t)}].molecular_formula: `{t.get('molecular_formula','')}` → Valid", ok4))


    if "chemicals" in data:
        for c in data["chemicals"]:
            total += 4
            ok1 = check_exists(c, "name")
            ok2 = score_provenance(c)
            ok3 = check_exists(c, "ontology")
            ok4 = is_valid_formula(c.get("molecular_formula", ""))

            score += ok1 + ok2 + ok3 + ok4
            details.append((f"chemicals[{data['chemicals'].index(c)}].name: `{c.get('name','')}` → Has name", ok1))
            details.append((f"chemicals[{data['chemicals'].index(c)}].prov: `{c.get('prov',[])}` → Provenance valid", ok2))
            details.append((f"chemicals[{data['chemicals'].index(c)}].ontology: `{c.get('ontology',{})}` → Has ontology", ok3))
            details.append((f"chemicals[{data['chemicals'].index(c)}].molecular_formula: `{c.get('molecular_formula','')}` → Valid", ok4))


    if "synthesis" in data:
        steps = data["synthesis"].get("steps", [])
        for s in steps:
            total += 4
            ok1 = check_exists(s, "description")
            ok2 = score_provenance(s)
            ok3 = "operations" in s
            ok4 = isinstance(s.get("operations", []), list)

            score += ok1 + ok2 + ok3 + ok4
            details.append((f"synthesis.steps[{steps.index(s)}].description: `{s.get('description','')}` → Has description", ok1))
            details.append((f"synthesis.steps[{steps.index(s)}].prov: `{s.get('prov',[])}` → Provenance valid", ok2))
            details.append((f"synthesis.steps[{steps.index(s)}].operations: Exists", ok3))
            details.append((f"synthesis.steps[{steps.index(s)}].operations: Valid list", ok4))


    if "characterization" in data:
        for ch in data["characterization"]:
            total += 3
            ok1 = check_exists(ch, "method")
            ok2 = score_provenance(ch)
            ok3 = "results" in ch

            score += ok1 + ok2 + ok3
            details.append((f"characterization[{data['characterization'].index(ch)}].method: `{ch.get('method','')}` → Has method", ok1))
            details.append((f"characterization[{data['characterization'].index(ch)}].prov: `{ch.get('prov',[])}` → Provenance valid", ok2))
            details.append((f"characterization[{data['characterization'].index(ch)}].results: Exists", ok3))

    # HALLUCINATION CHECK
    ok_hallu, suspicious = check_no_hallucination(text, data)
    total += 1
    score += ok_hallu
    details.append(("Hallucination check: Passed", ok_hallu))

    # UNITS POLICY CHECK
    ok_units, susp_units = check_units(data)
    total += 1
    score += ok_units
    details.append(("Units policy check: Passed", ok_units))

    return {
        "score_percent": round(score / total * 100, 2) if total > 0 else 0,
        "score_raw": f"{score}/{total}",
        "verdict": (
            "Excellent" if score / total >= 0.9 else
            "Good" if score / total >= 0.75 else
            "Acceptable" if score / total >= 0.6 else
            "Poor"
        ),
        "suspicious_items": suspicious,
        "suspicious_units": susp_units,
        "details": details
    }

def extract_text_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        return ""
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            text += page.extract_text() or ""  # Extract text, handle None cases
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
    return text


pdfs_dir = '/content/drive/MyDrive/chemExtract/PDFs'
output_dir = '/content/drive/MyDrive/chemExtract/output_300f'


json_files = glob.glob(f'{output_dir}/*_reactions.json')
print(f"Found {len(json_files)} JSON files to evaluate.")

scores = []
summary_report = []
for json_path in json_files:
    data = load_json(json_path)

    base_filename = os.path.basename(json_path).replace('_reactions.json', '')
    text_path = os.path.join(output_dir, f"{base_filename}_text.txt")
    pdf_path = os.path.join(pdfs_dir, f"{base_filename}.pdf")

    if os.path.exists(text_path):
        text = open(text_path, "r", encoding="utf-8").read()
    elif os.path.exists(pdf_path):
        print(f"Text file not found for {json_path}. Extracting from PDF: {pdf_path}")
        text = extract_text_from_pdf(pdf_path)
    else:
        print(f"Warning: Neither text nor PDF found for {json_path}. Skipping hallucination check.")
        text = ""

    result = evaluate_extraction(text, data)
    scores.append(result['score_percent'])

    display(Markdown(f"## Evaluation for {os.path.basename(json_path)}"))
    print(json.dumps(result, indent=2))

    for detail, ok in result["details"]:
        color = "green" if ok else "red"
        display(Markdown(f"<span style='color:{color};font-family:monospace'>{detail}</span>"))

    if result["suspicious_items"]:
        display(Markdown("**Suspicious Hallucinations:** " + ", ".join(result["suspicious_items"])))

    if result["suspicious_units"]:
        display(Markdown("**Suspicious Units:** " + ", ".join(result["suspicious_units"])))

    display(Markdown(f"**Score:** {result['score_percent']}% - {result['verdict']}"))
    display(Markdown("---"))

    # Add data to the summary list
    summary_report.append({
        "filename": os.path.basename(json_path),
        "score_percent": result['score_percent'],
        "verdict": result['verdict'],
        "raw_score": result['score_raw']
    })

# Overall
if scores:
    avg_score = sum(scores) / len(scores)
    display(Markdown("## BATCH SUMMARY"))
    display(Markdown(f"**Average Score:** {round(avg_score, 2)}%"))
    display(Markdown(f"**Total Files:** {len(json_files)}"))

# Sort the report by percentage (descending)
summary_report.sort(key=lambda x: x['score_percent'], reverse=True)

# Save to CSV
csv_output_path = os.path.join(output_dir, "evaluation_summary.csv")
keys = summary_report[0].keys() if summary_report else []

with open(csv_output_path, 'w', newline='', encoding='utf-8') as f:
    dict_writer = csv.DictWriter(f, fieldnames=keys)
    dict_writer.writeheader()
    dict_writer.writerows(summary_report)

display(Markdown(f"### Report generated: [{csv_output_path}]({csv_output_path})"))

# Display table in Jupyter
import pandas as pd
df = pd.DataFrame(summary_report)
display(df)