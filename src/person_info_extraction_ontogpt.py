import os
import yaml
import json
import shutil
import subprocess
from copy import deepcopy


# ============================================================
# File + Path Utilities
# ============================================================

def ensure_dir(path: str):
    """Ensure a directory exists."""
    os.makedirs(path, exist_ok=True)


def load_yaml(path: str):
    """Load YAML from file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_yaml(path: str, data):
    """Write YAML to file."""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


def write_text(path: str, text: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================
# Step 1 — Extract Text & Cell Spans
# ============================================================

def extract_text_and_spans(row, out_dir):
    """
    Convert OCR table rows → flat text + span mapping.
    Only processes row index 1 (as per original behaviour).
    """

    ensure_dir(out_dir)
    row_text = ""
    cursor = 0
    cell_spans = []

    for cell in row:
        text = cell["text"]
        cid = cell["id"]
        start = cursor
        end = start + len(text)

        cell_spans.append({"id": cid, "start": start, "end": end, "text": text})

        row_text += text + "\n"
        cursor = end

    write_yaml(os.path.join(out_dir, "table_cells.yaml"), cell_spans)
    write_text(os.path.join(out_dir, "row.txt"), row_text)


# ============================================================
# Step 2 — Run OntoGPT
# ============================================================

def run_ontogpt(template, cwd, input_file="row.txt", output_file="person.yaml",
                model="ollama/llama3"):
    """
    Executes OntoGPT extraction.
    """
    print("Running OntoGPT...")

    cmd = [
        "ontogpt", "extract",
        "-i", input_file,
        "-t", template,
        "-m", model,
        "-o", output_file
    ]

    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

    if proc.returncode != 0:
        print(proc.stderr)
        raise RuntimeError(f"OntoGPT failed: rc={proc.returncode}")

    print(proc.stdout)
    return os.path.join(cwd, output_file)


# ============================================================
# Step 3 — Map Text Spans → Cell IDs
# ============================================================

def find_cell_for_span(start, spans):
    """Return the cell ID covering a character offset."""
    for item in spans:
        if item["start"] <= start < item["end"]:
            return item["id"]
    return None


def map_text_spans_to_cells(yaml_path, cells_path):
    """
    Merges OntoGPT YAML with provenance mapping to cell IDs.
    """

    data = load_yaml(yaml_path)
    cell_spans = load_yaml(cells_path)

    named_entities = data.get("named_entities", [])

    for ent in named_entities:
        span_list = ent.get("original_spans", [])
        mapped_cells = []

        for span_str in span_list:
            try:
                start, _ = map(int, span_str.split(":"))
            except ValueError:
                continue

            cid = find_cell_for_span(start, cell_spans)
            mapped_cells.append(cid)

        ent["cell"] = mapped_cells[0] if len(mapped_cells) == 1 else mapped_cells or None

    write_yaml(yaml_path, data)


# ============================================================
# Step 4 — Convert YAML → Normalised JSON
# ============================================================

def match_entity(raw_value, named_entities):
    """Return named_entity object if raw_value matches auto-ID."""
    if not isinstance(raw_value, str):
        return None

    return next(
        (ent for ent in named_entities if ent.get("id") == raw_value), None
    )


def process_value(value, named_entities):
    """Recursive converter for values."""

    if isinstance(value, dict):
        return {k: process_value(v, named_entities) for k, v in value.items()}

    ent = match_entity(value, named_entities)

    if ent:
        return {
            "value": ent.get("label"),
            "cell": ent.get("cell"),
            "original_spans": ent.get("original_spans"),
        }

    return {"value": value, "cell": None, "original_spans": None}


def convert_yaml_to_json(yaml_path, json_output):
    """
    Converts OntoGPT YAML output into normalized JSON.
    This version safely handles cases where extracted_object
    or named_entities are missing or malformed.
    """

    data = load_yaml(yaml_path)

    extracted_raw = data.get("extracted_object")
    if not isinstance(extracted_raw, dict):
        print("Warning: YAML has no 'extracted_object'. Returning empty person.")
        extracted = {}
        return
    else:
        extracted = deepcopy(extracted_raw)

    named_entities_raw = data.get("named_entities")
    if not isinstance(named_entities_raw, list):
        print("Warning: YAML has no 'named_entities'. Using empty list.")
        named_entities = []
    else:
        named_entities = named_entities_raw

    person = {
        key: process_value(value, named_entities)
        for key, value in extracted.items()
    }

    write_json(json_output, {"persons": [person]})



# ============================================================
# Step 5 — High-level Orchestration
# ============================================================

def extract_person_info(logical_rows, schema_path, json_output, temp_dir="temp/"):
    """End-to-end person extraction pipeline."""

    ensure_dir(temp_dir)

    # Step 1: Prepare text + spans
    extract_text_and_spans(logical_rows, temp_dir)

    # Step 2: Copy schema locally
    schema_copy = os.path.join(temp_dir, os.path.basename(schema_path))
    shutil.copy(schema_path, schema_copy)
    schema_name = os.path.basename(schema_copy)

    # Step 3: Run OntoGPT
    yaml_path = run_ontogpt(template=schema_name, cwd=temp_dir)

    # Step 4: Add provenance
    map_text_spans_to_cells(
        yaml_path,
        os.path.join(temp_dir, "table_cells.yaml")
    )

    # Step 5: Convert to JSON
    convert_yaml_to_json(yaml_path, json_output)

