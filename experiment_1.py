# %%
import os
import traceback
import json
import shutil
from statistics import mean
from bs4 import BeautifulSoup
from shapely.geometry import Polygon
from src.utils import (
    pagexml_to_html,
    format_td
)
from src.metrics import (
    compute_mAP,
    TEDS,
    infomration_extraction_precision_recall,
    best_match_similarity
)
from src.person_info_extraction import extract_info_LLM
from src.person_info_extraction_ontogpt import extract_person_info as information_extractor
from statistics import mean

# %%
DATA_DIR = "data/tables/pagexml"
GT_POLYGON_DIR = "data/labels/polygons"
GT_HTML_DIR = "data/labels/tables"
GT_INFO_DIR = "data/labels/info"
OUTPUT_HTML_DIR = "data/tables/html"
OUTPUT_JSON_DIR = "data/json"
TEMP_DIR = "data/temp"
SCHEMA_PATH = "data/schema/personbasicinfo.yaml"
LLM_MODEL = "ollama/llama3"

# storage for metrics
all_scores = {
    "mAP": [],
    "TEDS-Struct": [],
    "TEDS": [],
    "Precision": [],
    "Recall": [],
    "F1-score": []
}


# %% --- Utility Functions ---

def calculate_teds(gt_html, pred_html):
    """Compute TEDS and TEDS-Struct scores between two HTML tables."""
    gt_html = format_td(gt_html)
    teds = TEDS(structure_only=False)
    teds_struct = TEDS(structure_only=True)

    teds_score = teds.evaluate(gt_html, pred_html)
    teds_struct_score = teds_struct.evaluate(gt_html, pred_html)
    return teds_score, teds_struct_score


def parse_html_table(html_content):
    """Parse HTML table into logical rows, respecting rowspan/colspan."""
    soup = BeautifulSoup(html_content, 'html.parser')
    rows = soup.find_all('tr')

    logical_rows = []
    rowspans = {}

    for r_idx, tr in enumerate(rows):
        current_row = []
        to_remove = []

        # carry-down cells
        for col_idx, (remaining, cell) in rowspans.items():
            current_row.append(cell)
            rowspans[col_idx][0] -= 1
            if rowspans[col_idx][0] <= 0:
                to_remove.append(col_idx)
        for col_idx in to_remove:
            del rowspans[col_idx]

        # new cells
        c_idx = 0
        for td in tr.find_all('td'):
            while c_idx in rowspans:
                c_idx += 1
            text = td.get_text(" ", strip=True)
            cell_data = {
                "text": text,
                "id": td.get("id"),
                "row": int(td.get("row", r_idx)),
                "col": int(td.get("col", c_idx)),
                "rowspan": int(td.get("rowspan", 1)),
                "colspan": int(td.get("colspan", 1))
            }
            current_row.append(cell_data)
            if cell_data["rowspan"] > 1:
                rowspans[c_idx] = [cell_data["rowspan"] - 1, cell_data]
            c_idx += cell_data["colspan"]

        logical_rows.append(current_row)
    return logical_rows


def extract_persons_from_table(logical_rows):
    """Extract structured person information from table rows."""
    persons = []
    for row in logical_rows:
        person = json.loads(extract_info_LLM(row))
        if person and not all(v["value"] is None for v in person.values()):
            persons.append(person)
    unique_persons = {json.dumps(p, sort_keys=True) for p in persons}
    return [json.loads(p) for p in unique_persons]


def process_single_image(image_name, IE_method="ontogpt"):
    """Run the full evaluation pipeline for one image and return metrics."""
    print("\n===================================")
    print(f"Processing {image_name}...")

    pagexml_file = os.path.join(DATA_DIR, f"{image_name}.xml")
    output_html_file = os.path.join(OUTPUT_HTML_DIR, f"{image_name}.html")
    pagexml_to_html(pagexml_file, output_html_file)

    # --- Compute mAP ---
    gt_file = os.path.join(GT_POLYGON_DIR, f"{image_name}.polygons.json")
    pred_file = pagexml_file
    mAP = compute_mAP(gt_file, pred_file)

    # --- Compute TEDS ---
    with open(os.path.join(GT_HTML_DIR, f"{image_name}.html"), encoding="utf-8") as f:
        gt_html = f.read()
    with open(output_html_file, encoding="utf-8") as f:
        pred_html = f.read()
    teds_score, teds_struct_score = calculate_teds(gt_html, pred_html)

    # --- Information Extraction ---
    logical_rows = parse_html_table(pred_html)

    if IE_method == "llm":
        persons = extract_persons_from_table(logical_rows)
        json_obj = {"persons": persons}
        json_out_path = os.path.join(OUTPUT_JSON_DIR, f"{image_name}.json")
        with open(json_out_path, "w", encoding="utf-8") as jf:
            json.dump(json_obj, jf, ensure_ascii=False, indent=2)
    
    if IE_method == "ontogpt":
        json_out_path = os.path.join(OUTPUT_JSON_DIR, f"{image_name}.json")
        os.makedirs(TEMP_DIR, exist_ok=True)

        try:
            for i, row in enumerate(logical_rows):
                print(f"Processing row {i+1}/{len(logical_rows)}")
                temp_file = f"person_{i}.json"
                try:
                    information_extractor(row, schema_path=SCHEMA_PATH, json_output=os.path.join(TEMP_DIR, temp_file), temp_dir=TEMP_DIR, llm_model=LLM_MODEL)
                except Exception as e:
                    print(f" ❌ Error processing row {i}: {e}")
                    continue

            persons = []

            for filename in os.listdir(TEMP_DIR):
                if filename.endswith(".json") and filename.startswith("person_"):
                    with open(os.path.join(TEMP_DIR, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # each temp file is expected to be {'persons': [...]}
                        person = data.get("persons", [])
                        if isinstance(persons, list):
                            persons.extend(person)
                        elif person:
                            persons.append(persons)

            with open(json_out_path, 'w', encoding='utf-8') as f:
                json.dump({"persons": persons}, f, indent=2, ensure_ascii=False)   
        finally: 
            shutil.rmtree(TEMP_DIR, ignore_errors=True)

    # --- Compare with Ground Truth JSON ---
    with open(os.path.join(GT_INFO_DIR, f"{image_name.replace('.jpg', '.json')}"), encoding="utf-8") as f:
        gt_info = json.load(f)
    with open(json_out_path, encoding="utf-8") as f:
        pred_info = json.load(f)

    # info_sim = best_match_similarity(gt_info.get("persons", []), pred_info.get("persons", []))
    precision, recall, f1_score = infomration_extraction_precision_recall(
        pred_info.get("persons", []), gt_info.get("persons", []), threshold=0.4
    )

    print(f"Mean Average Precision (mAP): {mAP:.4f}")
    print(f"TEDS-Struct: {teds_struct_score:.4f}")
    print(f"TEDS: {teds_score:.4f}")
    
    print(f"Information Extraction - \nPrecision: {precision:.4f}, \nRecall: {recall:.4f}, \nF1-score: {f1_score:.4f}")

    return mAP, teds_score, teds_struct_score, precision, recall, f1_score


# %% --- Main Execution Loop ---

def main():
    for file in os.listdir(DATA_DIR): 
        if not file.endswith(".xml"): 
            continue 

        image_name = file.replace(".xml", "") 

        try: 
            mAP, teds, teds_struct, p, r , f= process_single_image(image_name) 
            all_scores["mAP"].append(mAP) 
            all_scores["TEDS-Struct"].append(teds_struct) 
            all_scores["TEDS"].append(teds) 
            all_scores["Precision"].append(p) 
            all_scores["Recall"].append(r) 
            all_scores["F1-score"].append(f) 
            print(f"✅ Finished processing {image_name}")
        except Exception as e: 
            # Print detailed error info
            print("❌ [ERROR] An exception occurred!")
            traceback.print_exc()


    # --- Print summary averages ---
    print("\n===================================") 
    print("=== Average Metrics Across All Images ===") 
    for key, vals in all_scores.items(): 
        avg = mean(vals) if vals else 0.0 
        print(f"{key}: {avg:.4f}")

if __name__ == "__main__":
    main()