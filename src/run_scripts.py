#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
import argparse
import traceback
import shutil
from bs4 import BeautifulSoup

from helpers import copy_file, delete_file, read_html_file, write_html_file, write_json_file, read_json_file
from run_loghi import run_bash_script as run_loghi

def run_LOGHI_pipeline(data_path="data"):
    """Run the LOGHI pipeline from bash inside Python."""
    source_folder = os.path.join(data_path, "images")
    destination_folder = os.path.join(data_path, "htr")

    for filename in os.listdir(source_folder):
        # file_path = os.path.join(source_folder, filename)
        
        if filename.endswith('.jpg'):
            image_name = filename

            # Step 1: Copy the image
            copy_file(image_name, source_folder, destination_folder)

            # Step 2: Run the bash script
            run_loghi()

            # Step 3: Delete the image
            delete_file(image_name, destination_folder)

            # Pause for a moment before moving to the next image
            time.sleep(5)  # Adjust the sleep time as needed


def run_LORE_pipeline():
    """Run the LORE pipeline from bash inside Python."""
    commands = f"""
    cd Image2TableBoundingBoxDetection/src
    source ~/anaconda3/etc/profile.d/conda.sh
    conda deactivate
    conda activate LORE
    bash scripts/infer/demo_wired.sh
    """
    result = subprocess.run(commands, shell=True, text=True, capture_output=True, executable="/bin/bash")
    print(">>> Pipeline STDOUT:\n", result.stdout)
    print(">>> Pipeline STDERR:\n", result.stderr)


def reconstruct_table_pipeline(IMAGE_NAME, cells_bounding_box, cells_structure, page_file, json_file):
    """Run table reconstruction using existing module."""
    from reconstruct_table import main as reconstruct_table
    reconstruct_table(cells_bounding_box, cells_structure, page_file, json_file, IMAGE_NAME, wired=True)

# =========================
# INFORMATION EXTRACTION
# =========================
def extract_persons_from_html(constructed_html, json_output, temp_dir, schema_path, llm_model):
    from person_info_extraction_ontogpt import extract_person_info as information_extractor

    soup = BeautifulSoup(constructed_html, 'html.parser')
    rows = soup.find_all('tr')

    # --- Step 1: make a grid keeping track of rowspans ---
    logical_rows = []
    rowspans = {}  # {(col_idx): [remaining_rows, cell_content]}

    for r_idx, tr in enumerate(rows):
        current_row = []
        to_remove = []

        for col_idx, (remaining, cell) in rowspans.items():
            current_row.append(cell)
            rowspans[col_idx][0] -= 1
            if rowspans[col_idx][0] <= 0:
                to_remove.append(col_idx)
        for col_idx in to_remove:
            del rowspans[col_idx]

        c_idx = 0
        for td in tr.find_all('td'):
            while any(k == c_idx for k in rowspans): 
                c_idx += 1
            text = td.get_text(" ", strip=True)
            cell_id = td.get('id')
            r_idx = int(td.get('row', r_idx))
            c_idx = int(td.get('col', c_idx))
            rowspan = int(td.get('rowspan', 1))
            colspan = int(td.get('colspan', 1))

            cell_data = {
                'text': text,
                'id': cell_id,
                'row': r_idx,
                'col': c_idx,
                'rowspan': rowspan,
                'colspan': colspan
            }

            # Place cell in current row
            current_row.append(cell_data)

            # Store for future rows if rowspan > 1
            if rowspan > 1:
                rowspans[c_idx] = [rowspan - 1, cell_data]

            c_idx += colspan

        logical_rows.append(current_row)

    
    os.makedirs(temp_dir, exist_ok=True)


    try:
        for i, row in enumerate(logical_rows):
            print(f"Processing row {i+1}/{len(logical_rows)}")
            temp_file = f"person_{i}.json"
            try:
                information_extractor(i, row, schema_path=schema_path, json_output=os.path.join(temp_dir, temp_file), temp_dir=temp_dir, llm_model=llm_model)
            except Exception as e:
                print(f" ❌ Error processing row {i}: {e}")
                traceback.print_exc()
                continue

        persons = []

        for filename in os.listdir(temp_dir):
            if filename.endswith(".json") and filename.startswith("person_"):
                with open(os.path.join(temp_dir, filename), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # each temp file is expected to be {'persons': [...]}
                    person = data.get("persons", [])
                    if isinstance(persons, list):
                        persons.extend(person)
                    elif person:
                        persons.append(persons)

        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump({"persons": persons}, f, indent=2, ensure_ascii=False)   

    finally: 
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

def calculate_TEDS(ground_truth_html, predicted_html):
    """Calculate TEDS and TEDS-Struct similarity."""
    from utils import format_td
    from metrics import TEDS

    predicted_html = format_td(predicted_html)
    ground_truth_html = format_td(ground_truth_html)

    teds = TEDS(structure_only=False)
    teds_struct = TEDS(structure_only=True)

    teds_score = teds.evaluate(ground_truth_html, predicted_html)
    teds_struct_score = teds_struct.evaluate(ground_truth_html, predicted_html)

    print(f"TEDS: {teds_score:.4f}")
    print(f"TEDS-Struct: {teds_struct_score:.4f}")
    return teds_score, teds_struct_score

def ml_construct_table(data_path):    
    # Run LOGHI pipeline
    run_LOGHI_pipeline()

    # Run LORE pipeline
    run_LORE_pipeline()

    # Reconstruct tables
    for filename in os.listdir(os.path.join(data_path, "images")):
        if not filename.endswith('.jpg'):
            continue
        
        IMAGE_NAME = filename
        BASE_NAME = os.path.splitext(IMAGE_NAME)[0]

        cells_bounding_box = f"{data_path}/tables/cells/center/{IMAGE_NAME}.txt"
        cells_structure = f"{data_path}/tables/cells/logi/{IMAGE_NAME}.txt"
        page_file = f"{data_path}/htr/page/{BASE_NAME}.xml"
        json_file = f"{data_path}/tables/json/{IMAGE_NAME}.jsonl"
        reconstruct_table_pipeline(IMAGE_NAME, cells_bounding_box, cells_structure, page_file, json_file)


def transkribus_construct_table(data_path, output_path):
    from utils import pagexml_to_html

    for filename in os.listdir(os.path.join(data_path, "images")):
        if not filename.endswith('.jpg'):
            continue
        
        IMAGE_NAME = filename
        directory = os.path.join(data_path, "tables", "pagexml")

        pagexml_file = os.path.join(directory, IMAGE_NAME+ ".xml")
        output_file = os.path.join(output_path, IMAGE_NAME + ".html")
        # print(f"Converting {pagexml_file} to {output_file}...")
        pagexml_to_html(pagexml_file, output_file)

def llm_construct_table(data_path, output_path):
    from LLM import LLM_table_construct
    from LLM_key import llm_model
    from utils import extract_HTML
    from prompt import tsr_html_prompt, tsr_html_decomposition

    for filename in os.listdir(os.path.join(data_path, "images")):
        if not filename.endswith('.jpg'):
            continue
        
        IMAGE_NAME = filename
        image_path = os.path.join(data_path, "images", IMAGE_NAME)
        output_file = os.path.join(output_path, IMAGE_NAME + ".html")

        llm_html = LLM_table_construct(image_path, prompt=tsr_html_prompt, model_name=llm_model, temperature=0)
        llm_html = extract_HTML(llm_html)
        
        llm_html = llm_html.replace("<table>", "<table border='1'>")
        write_html_file(output_file, llm_html)

def llm_multi_construct_table(data_path, output_path):
    import re, csv
    from LLM import LLM_multi_agent_table_construct
    from LLM_key import llm_model
    from utils import extract_HTML

    for filename in os.listdir(os.path.join(data_path, "images")):
        if not filename.endswith('.jpg'):
            continue
        
        IMAGE_NAME = filename
        image_path = os.path.join(data_path, "images", IMAGE_NAME)

        llm_response = LLM_multi_agent_table_construct(image_path, model_name=llm_model, temperature=0)
        
        # Extract detected cells coordinates 
        detected_block = re.search(r"coordinates.*?```plaintext(.*?)```", llm_response, re.S | re.I)
        detected_lines = detected_block.group(1).strip().splitlines() if detected_block else []

        with open(os.path.join(output_path, "cells", "center", IMAGE_NAME+'.txt'), "w+", newline="") as f:
            writer = csv.writer(f)
            for line in detected_lines:
                if not line.strip():
                    continue
                parts = line.split("#")
                polygon = parts[0].strip()
                cell_id = "#" + parts[1].strip() if len(parts) > 1 else ""
                writer.writerow([polygon, cell_id])

        # Extract logical cell sequence
        logical_block = re.search(r"logical sequence.*?```plaintext(.*?)```", llm_response, re.S | re.I)
        logical_lines = logical_block.group(1).strip().splitlines() if logical_block else []

        with open(os.path.join(output_path, "cells", "logi", IMAGE_NAME+'.txt'), "w+", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["sequence", "cell_id"])  # header
            for line in logical_lines:
                if not line.strip() or line.strip().startswith("</"):
                    continue
                parts = line.split("#")
                sequence = parts[0].strip()
                cell_id = "#" + parts[1].strip() if len(parts) > 1 else ""
                writer.writerow([sequence, cell_id])

        llm_html = extract_HTML(llm_response)
        llm_html = llm_html.replace("<table>", "<table border='1'>")

        output_file = os.path.join(output_path, "html", IMAGE_NAME + ".html")
        write_html_file(output_file, llm_html)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp_name", type=str, required=True, help="Name of the process")
    parser.add_argument("--data_path", type=str, required=True, help="Path to the evaluation dataset")
    parser.add_argument("--output_path", type=str, required=False, help="Path to save outputs")
    args = parser.parse_args()

    exp_name = args.exp_name
    data_path = args.data_path
    output_path = args.output_path if args.output_path else data_path

    print(f"Starting process: {exp_name}")
    time.sleep(1)  # Simulate some processing time

    if not os.path.exists(data_path):
        print(f"Data path {data_path} does not exist.")
        sys.exit(1)

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    if exp_name not in ["ml", "transkribus", "llm", "llm_multi"]:
        print(f"Process {exp_name} is not recognized.")
        sys.exit(1)

    # =========================
    # TABLE CONSTRUCTION
    # =========================
    if exp_name == "ml":
        print("Running ML process...")
        ml_construct_table(data_path)

    elif exp_name == "transkribus":
        print("Running Transkribus process...")  
        output_path = os.path.join(data_path, "tables", "html")
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        transkribus_construct_table(data_path, output_path)
        
    elif exp_name == "llm":
        print("Running LLM process...")
        
        output_path = os.path.join(data_path, "tables")
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        llm_construct_table(data_path, output_path)

    elif exp_name == "llm_multi":
        print("Running LLM Multi process...")
        
        output_path = os.path.join(data_path, "tables")
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        for subfolder in ["cells", "html"]:
            subfolder_path = os.path.join(output_path, subfolder)
            if not os.path.exists(subfolder_path):
                os.makedirs(subfolder_path)
            if subfolder == "cells":
                for cell_type in ["center", "logi"]:
                    cell_type_path = os.path.join(subfolder_path, cell_type)
                    if not os.path.exists(cell_type_path):
                        os.makedirs(cell_type_path)
                        
        llm_multi_construct_table(data_path, output_path) 


    for filename in os.listdir(os.path.join(data_path, "images"))[48:]:  # start from 49th image for testing
        if not filename.endswith('.jpg'):
            continue

        IMAGE_NAME = filename
        print(f"Processing {IMAGE_NAME}...")
        constructed_html = read_html_file(f"{data_path}/tables/html/{IMAGE_NAME}.html")
        # label_html = read_html_file(f"{data_path}/labels/tables/{IMAGE_NAME}.html")
        # calculate_TEDS(label_html, constructed_html)

        # print(f"Completed evaluation for {IMAGE_NAME}\n")

        # =========================
        # INFORMATION EXTRACTION
        # =========================
        TEMP_DIR = f"{data_path}/temp"
        SCHEMA_PATH = f"{data_path}/schema/personbasicinfo.yaml"
        LLM_MODEL = "ollama/llama3"
        JSON_FILE = f"{data_path}/json/{IMAGE_NAME}.json"
        
        persons_json = extract_persons_from_html(constructed_html, json_output=JSON_FILE, temp_dir=TEMP_DIR, schema_path=SCHEMA_PATH, llm_model=LLM_MODEL)

        # from metrics import best_match_similarity
        # pred = read_json_file(f"{data_path}/json/{IMAGE_NAME}.json")
        # true = read_json_file(f"{data_path}/labels/{IMAGE_NAME.replace('.jpg', '.json')}")
        # print(f"Information similarity score: {best_match_similarity(true.get('persons', []), pred.get('persons', [])) : .4f}\n")