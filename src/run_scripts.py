#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
import argparse
from bs4 import BeautifulSoup

from helpers import copy_file, delete_file, read_html_file, write_json_file, read_json_file
from rdflib import Graph, ConjunctiveGraph, Namespace, URIRef, Literal, RDF
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
def extract_persons_from_html(constructed_html):
    """Extract persons from reconstructed HTML using LLM/regex."""
    from person_info_extraction import extract_info_LLM

    soup = BeautifulSoup(constructed_html, 'html.parser')
    rows = soup.find_all('tr')

    persons = []
    logical_rows, rowspans = [], {}

    for r_idx, tr in enumerate(rows):
        current_row = []
        to_remove = []

        # Fill carried-over rowspans
        for col_idx, (remaining, cell) in rowspans.items():
            current_row.append(cell)
            rowspans[col_idx][0] -= 1
            if rowspans[col_idx][0] <= 0:
                to_remove.append(col_idx)
        for col_idx in to_remove:
            del rowspans[col_idx]

        # New cells
        c_idx = 0
        for td in tr.find_all('td'):
            while c_idx in rowspans:
                c_idx += 1
            cell_data = {
                'text': td.get_text(" ", strip=True),
                'id': td.get('id'),
                'row': int(td.get('row', r_idx)),
                'col': int(td.get('col', c_idx)),
                'rowspan': int(td.get('rowspan', 1)),
                'colspan': int(td.get('colspan', 1))
            }
            current_row.append(cell_data)
            if cell_data['rowspan'] > 1:
                rowspans[c_idx] = [cell_data['rowspan'] - 1, cell_data]
            c_idx += cell_data['colspan']
        logical_rows.append(current_row)

    # Person extraction
    for row in logical_rows:
        person = json.loads(extract_info_LLM(row))
        if person and not all(v['value'] is None for v in person.values()):
            persons.append(person)

    unique_persons = {json.dumps(p, sort_keys=True) for p in persons}
    return {"persons": [json.loads(p) for p in unique_persons]}

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
        pagexml_to_html(pagexml_file, output_file)

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
        # Placeholder for LLM process logic
    elif exp_name == "llm_multi":
        print("Running LLM Multi process...")
        # Placeholder for LLM Multi process logic


    for filename in os.listdir(os.path.join(data_path, "images")):
        if not filename.endswith('.jpg'):
            continue

        IMAGE_NAME = filename
        constructed_html = read_html_file(f"data/tables/html/{IMAGE_NAME}.html")
        label_html = read_html_file(f"data/labels/{IMAGE_NAME.replace('.jpg', '.html')}")
        calculate_TEDS(label_html, constructed_html)

        print(f"Completed evaluation for {IMAGE_NAME}\n")

        # =========================
        # INFORMATION EXTRACTION
        # =========================
        persons_json = extract_persons_from_html(constructed_html)
        write_json_file(f"{data_path}/json/{IMAGE_NAME}.json", persons_json)

        from metrics import best_match_similarity
        pred = read_json_file(f"data/json/{IMAGE_NAME}.json")
        true = read_json_file(f"data/labels/{IMAGE_NAME.replace('.jpg', '.json')}")
        print(f"Information similarity score: {best_match_similarity(true.get('persons', []), pred.get('persons', [])) : .4f}\n")