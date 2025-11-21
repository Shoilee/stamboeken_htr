import yaml
import os
import subprocess


def generate_text(logical_rows, temp_path="../data/temp/"):
    import yaml

    cell_spans = []     # list of dicts: {id, start, end}
    row_text = ""       # concatenated text of the entire table
    cursor = 0          # tracks current char offset

    if not os.path.exists(temp_path):
        os.makedirs(temp_path)

    for i, row in enumerate(logical_rows):
        # TODO: update the code, so that it can run for more than one person / row
        if i != 1:
            continue
        for cell in row:
            text = cell["text"]
            cid = cell["id"]

            start = cursor
            end = start + len(text)

            cell_spans.append({
                "id": cid,
                "start": start,
                "end": end,
                "text": text
            })

            row_text += text + '\n'
            cursor = end
        with open(os.path.join(temp_path , "table_cells.yaml"), "w+", encoding="utf-8") as f:
            yaml.dump(cell_spans, f, allow_unicode=True, sort_keys=False)

        with open(os.path.join(temp_path, "row.txt"), "w+") as f:
            f.write(row_text)


def run_ontogpt(input_path="row.txt",
                output="person.yaml",
                template="personbasicinfo.yaml",
                model="ollama/llama3",
                cwd=None,
                env=None):
    
    # input_path = os.path.join(cwd, input_path)
    # output = os.path.join(cwd, output)

    print("Running OntoGPT...")

    cmd = ["ontogpt", "extract", "-i", input_path, "-t", template, "-m", model, "-o", output]
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print("ontogpt failed (rc={}):".format(proc.returncode))
        print(proc.stderr)
        raise RuntimeError("ontogpt command failed")
    print(proc.stdout)
    return proc


def map_text_spans_to_cell(yaml_path, cells_path:yaml):
    def find_cell_for_span(start, spans):
        """
        Return the cell_id whose text covers the character span starting at 'start'.
        Span belongs to the cell where:  cell.start <= start < cell.end
        """
        for item in spans:
            if item["start"] <= start < item["end"]:
                return item["id"]
        return None
    
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    named_entities = data.get("named_entities", [])

    with open(cells_path, "r", encoding="utf-8") as f:
        cell_spans = yaml.safe_load(f)

    for ent in named_entities:
        spans = ent.get("original_spans", [])
        ent_cells = []

        for span_str in spans:
            try:
                start, end = map(int, span_str.split(":"))
            except:
                continue

            cell_id = find_cell_for_span(start, cell_spans)
            ent_cells.append(cell_id)

        # Add new slot "cell"
        if ent_cells:
            # if only one span, store a single value
            ent["cell"] = ent_cells[0] if len(ent_cells) == 1 else ent_cells
        else:
            ent["cell"] = None


    output_path = yaml_path
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)


# %%
def convert_yaml_to_json(yaml_path, json_out):
    import yaml
    import json
    from copy import deepcopy


    def load_yaml(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


    def get_entity_for_value(raw_value, named_entities):
        """
        Given a raw value like 'AUTO:Wageningen',
        return the full named_entity dict (label, cell, original_spans),
        or None if not found.
        """
        if not isinstance(raw_value, str):
            return None

        for ent in named_entities:
            if ent.get("id") == raw_value:
                return ent

        return None


    def process_field(value, named_entities):
        """
        Converts a YAML value into normalized JSON format with:
        - value
        - cell
        - original_spans
        Handles nested dicts.
        """

        # Case 1: nested dict → process each subfield recursively
        if isinstance(value, dict):
            processed = {}
            for k, v in value.items():
                processed[k] = process_field(v, named_entities)
            return processed

        # Case 2: literal field or AUTO reference
        ent = get_entity_for_value(value, named_entities)

        if ent:
            # match found: use curated label + provenance
            return {
                "value": ent.get("label"),
                "cell": ent.get("cell"),
                "original_spans": ent.get("original_spans")
            }

        # No entity match → raw literal value
        return {
            "value": value,
            "cell": None,
            "original_spans": None
        }


    def convert_yaml_to_person_json(data):
        extracted = deepcopy(data["extracted_object"])
        named_entities = data["named_entities"]

        person = {}

        # Process all fields dynamically
        for key, value in extracted.items():
            person[key] = process_field(value, named_entities)

        return {"persons": [person]}


    def write_json(path, obj):
        print("Writing JSON to", path)
        with open(path, "w+", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)


    data = load_yaml(yaml_path)
    result = convert_yaml_to_person_json(data)
    write_json(json_out, result)

    # print(json.dumps(result, indent=2, ensure_ascii=False))


def person_info_extraction_ontogpt(logical_rows, schema,  output_json, temp_dir="temp/"):
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    yaml_path = os.path.join(temp_dir, "person.yaml")

    # 1. Generate text file and cell spans
    generate_text(logical_rows, temp_path=temp_dir)

    # 2. Run OntoGPT
    schema_dest = os.path.join(temp_dir, os.path.basename(schema))
    subprocess.run(["cp", schema, schema_dest])
    schema = os.path.basename(schema)
    run_ontogpt(template=schema ,cwd=temp_dir)

    # 3. Map text spans to cell ids
    map_text_spans_to_cell(os.path.join(temp_dir, "person.yaml"), os.path.join(temp_dir, "table_cells.yaml"))
    
    # 4. Convert final YAML to JSON
    convert_yaml_to_json(yaml_path, output_json)

    # 5. Delete temp files
    subprocess.run(["rm", "-r", temp_dir])