from rdflib import Dataset, Graph, Namespace
import os
import time
import json

###############################################################################
# 1. CREATE SUBGRAPH FOR A GIVEN FOLIO
###############################################################################

def create_sub_graph_for_folio(folio_no: int) -> str:
    """
    Create a constructed graph for one folio and save it to Turtle.
    Returns the output file path.
    """
    ds = Dataset()
    ds.parse("Bronbeek_Data/Stamboeken.trig", format="trig")

    out_graph = Graph()
    batch_size = 100
    offset = 0
    timeout_minutes = 5
    timeout_seconds = timeout_minutes * 60
    last_success_time = time.time()

    def construct_query(offset):
        return f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rico: <https://www.ica.org/standards/RiC/ontology#>
        PREFIX sdo:  <https://schema.org/>
        PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

        CONSTRUCT {{
            ?person a sdo:Person .
            ?person rico:isOrWasSubjectOf ?archive .
            ?archive rico:identifier ?archiveID .
            ?archive rico:hasDerivedArchiveNumber ?archiveN .
            ?archive rico:hasInventoryNumber ?inv .
            ?archive sdo:identifier ?invNum .
            ?archive sdo:url ?archiveLink .
            ?person ?p ?o .
            ?o ?p1 ?o1 .
        }}
        WHERE {{
            ?person a sdo:Person .
            ?person rico:isOrWasSubjectOf ?archive .
            ?archive rico:identifier ?archiveID .

            BIND(REPLACE(?archiveID, "NL-HaNA_(.*?)_.*?_.*$", "$1") AS ?archiveN)
            BIND(REPLACE(?archiveID, "NL-HaNA_.*?_(.*?)_.*$", "$1") AS ?inv)
            BIND(xsd:integer(?inv) AS ?invNum)
            FILTER (?invNum = {folio_no})

            ?person ?p ?o .
            OPTIONAL {{ ?o  ?p1 ?o1 . }}
        }}
        LIMIT {batch_size}
        OFFSET {offset}
        """
    try:
        while True:
            print(f"\nRunning batch with OFFSET = {offset} ...")

            query = construct_query(offset)
            total_results = 0

            for g in ds.graphs():
                try:
                    results = g.query(query)
                except Exception:
                    continue

                rows = list(results)
                total_results += len(rows)
                for s, p, o in rows:
                    out_graph.add((s, p, o))

            # Stop condition
            if total_results > 0:
                last_success_time = time.time()
                offset += batch_size
            else:
                if time.time() - last_success_time > timeout_seconds:
                    break
                time.sleep(5)
                offset += batch_size
    finally:
        print(f"✔ Created subgraph with {len(out_graph)} triples")
        out_path = f"folio_{folio_no}_graph.ttl"
        out_graph.serialize(out_path, format="turtle")
        return out_path


###############################################################################
# 2. COUNT STATISTICS
###############################################################################

def count_new_graph_stats(folio_no: int):
    g = Graph()
    g.parse(f"folio_{folio_no}_graph.ttl", format="turtle")

    query = f"""
    PREFIX rico: <https://www.ica.org/standards/RiC/ontology#>
    PREFIX sdo:  <https://schema.org/>
    PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

    SELECT (COUNT(DISTINCT ?person) AS ?persons)
           (COUNT(DISTINCT ?archiveID) AS ?images)
    WHERE {{
        ?person a sdo:Person .
        ?person rico:isOrWasSubjectOf ?archive .
        ?archive rico:identifier ?archiveID .

        BIND(REPLACE(?archiveID, "NL-HaNA_.*?_(.*?)_.*$", "$1") as ?inv)
        BIND(xsd:integer(?inv) AS ?invNum)
        FILTER (?invNum = {folio_no})
    }}
    """

    for row in g.query(query):
        print(f"Total persons: {row.persons}")
        print(f"Total unique images: {row.images}")


###############################################################################
# 3. DOWNLOAD IMAGES FROM ARCHIVAL LINKS
###############################################################################

def download_images_for_folio(folio_no: int, output_dir="data/images"):
    from src.image_downlaod.download_stamboeken import process_archive_link
    from src.image_downlaod.download_control_book import download_image

    os.makedirs(output_dir, exist_ok=True)

    g = Graph()
    g.parse(f"folio_{folio_no}_graph.ttl", format="turtle")

    query = f"""
    PREFIX rico: <https://www.ica.org/standards/RiC/ontology#>
    PREFIX sdo:  <https://schema.org/>
    PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

    SELECT ?archiveID ?archiveLink WHERE {{
        ?person a sdo:Person .
        ?person rico:isOrWasSubjectOf ?archive .
        ?archive rico:identifier ?archiveID .

        BIND(REPLACE(?archiveID, "NL-HaNA_(.*?)_.*?_.*$", "$1") AS ?archiveN)
        BIND(REPLACE(?archiveID, "NL-HaNA_.*?_(.*?)_.*$", "$1") AS ?inv)
        BIND(xsd:integer(?inv) AS ?invNum)
        FILTER (?invNum = {folio_no})

        BIND(uri(CONCAT(
            "https://www.nationaalarchief.nl/onderzoeken/archief/",
            ?archiveN, "/invnr/", ?inv, "/file/", ?archiveID
        )) AS ?archiveLink)
    }}
    """

    for row in g.query(query):
        image_name = f"{row.archiveID}.jpg"
        download_url = process_archive_link(row.archiveLink, image_name)

        if download_url:
            download_image(download_url, image_name, output_dir)
        else:
            print(f"⚠ Could not download {image_name}")


###############################################################################
# 4. BUILD JSON INFORMATION EXTRACTION FILES
###############################################################################

class RDFToJSONConverter:
    def __init__(self, graph_path: str):
        self.graph = Graph()
        self.graph.parse(graph_path, format="turtle")

        self.ns_schema = Namespace("https://schema.org/")
        self.ns_pnv = Namespace("https://w3id.org/pnv#")
        self.ns_rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
        self.ns_dbpedia = Namespace("http://dbpedia.org/ontology/")

    def convert(self):
        persons = []
        for person in self.graph.subjects(predicate=None, object=self.ns_schema.Person):
            # Extract name details
            name_uri = self.graph.value(person, self.ns_pnv.hasName)
            name_data = {
                "label": self._lit(name_uri, self.ns_rdfs.label),
                "basesurname": self._lit(name_uri, self.ns_pnv.baseSurname),
                "firstnames": self._lit(name_uri, self.ns_pnv.firstName),
                "infix": self._lit(name_uri, self.ns_pnv.infix),
            }

            # Extract other details
            date_of_birth = self._lit(person, self.ns_schema.birthDate)
            birth_place_uri = self.graph.value(person, self.ns_schema.birthPlace)
            birth_place = self._lit(birth_place_uri, self.ns_schema.name)
            death_place_uri = self.graph.value(person, self.ns_schema.deathPlace)
            death_place = self._lit(death_place_uri, self.ns_schema.name)
            nationality_uri = self.graph.value(person, self.ns_schema.nationality)
            nationality = self._lit(nationality_uri, self.ns_schema.name)
            military_rank_uri = self.graph.value(person, self.ns_dbpedia.militaryRank)
            military_rank = self._lit(military_rank_uri, self.ns_schema.roleName)

            # Build structured person object
            person_obj = {
                "name": self._wrap_dict(name_data),
                "date_of_birth": self._wrap(date_of_birth),
                "birth_place": self._wrap(birth_place),
                "last_residence": self._wrap(death_place),
                "country_of_nationality": self._wrap(nationality),
                "military_rank": self._wrap(military_rank)
            }
            persons.append(person_obj)

        return {"persons": persons}

    def _lit(self, s, p):
        if not s:
            return None
        v = self.graph.value(s, p)
        return str(v) if v else None

    def _place(self, s, p):
        uri = self.graph.value(s, p)
        if not uri:
            return "Not mentioned"
        name = self.graph.value(uri, self.ns_schema.name)
        return str(name) if name else "Not mentioned"

    def _wrap(self, val):
        return {"value": val, "row": None, "cell": None, "original_spans": None}

    def _wrap_dict(self, d):
        wrapped = {}
        for k, v in d.items():
            wrapped[k] = self._wrap(v)
        return wrapped


def build_json_for_images(folio_no: int):
    image_dir = "data/images"
    graph = Graph()
    graph.parse(f"folio_{folio_no}_graph.ttl", format="turtle")

    out_graph_dir = "data/graph"
    out_json_dir = "data/labels/info"
    os.makedirs(out_graph_dir, exist_ok=True)
    os.makedirs(out_json_dir, exist_ok=True)

    for file in os.listdir(image_dir):
        if not file.endswith(".jpg"):
            continue

        archiveID = file.replace(".jpg", "")
        print(f"➡ Building JSON for {archiveID}")

        image_graph = construct_graph_for_single_image(archiveID, graph)
        ttl_path = f"{out_graph_dir}/{archiveID}.ttl"
        image_graph.serialize(ttl_path, format="turtle")
        print(f"The main graph has length: {len(graph)},\n"
              f"The sub-graph has length: {len(image_graph)}")

        json_path = f"{out_json_dir}/{archiveID}.json"
        conv = RDFToJSONConverter(ttl_path)
        data = conv.convert()

        with open(json_path, "w", encoding="utf8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def construct_graph_for_single_image(archiveID: str, graph: Graph):
    """
    Creates a subgraph for one image only.
    """
    new_g = Graph()

    query = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        prefix rico: <https://www.ica.org/standards/RiC/ontology#>
        prefix sdo:  <https://schema.org/> 
        prefix dbo:  <http://dbpedia.org/ontology/>
        prefix xsd:  <http://www.w3.org/2001/XMLSchema#>
        prefix pvn:  <https://w3id.org/pnv#>
        prefix ricrst: <https://www.ica.org/standards/RiC/vocabularies/recordSetTypes#>
        CONSTRUCT 
        {{
            # --- original triples ---
            ?person a sdo:Person .
            ?person rico:isOrWasSubjectOf ?archive .
            ?archive rico:identifier ?archiveID .

            # --- derived triples ---
            ?archive rico:hasDerivedArchiveNumber ?archiveN .
            ?archive rico:hasInventoryNumber ?inv .
            ?archive sdo:identifier ?invNum .
            ?archive sdo:url ?archiveLink .

            ?person ?p ?o .
            ?o ?p1 ?o1 .

        }}
        {{
            ### ORIGINAL QUERY
            ?person a sdo:Person .
            ?person rico:isOrWasSubjectOf ?archive .
            bind("{str(archiveID)}" as ?archiveID) .
            ?archive rico:identifier ?archiveID .

            bind(replace(?archiveID, 'NL-HaNA_(.*?)_.*?_.*$','$1') as ?archiveN)
            BIND(REPLACE(?archiveID, "NL-HaNA_.*?_(.*?)_.*$", "$1") AS ?inv)
            BIND(xsd:integer(?inv) AS ?invNum)
            FILTER (?invNum = 45)

            ### ALL PERSON-SUBJECT TRIPLES
            ?person ?p ?o .
            OPTIONAL {{ ?o  ?p1 ?o1 . }}
        }}
    """

    for s, p, o in graph.query(query):
        new_g.add((s, p, o))

    return new_g


###############################################################################
# 5. CALCULATE IE PRECISION, RECALL AND F1-SCORE
###############################################################################
import os
import traceback
import json
import shutil
from statistics import mean
from bs4 import BeautifulSoup
from src.utils import pagexml_to_html
from src.metrics import infomration_extraction_precision_recall
# from src.person_info_extraction import extract_info_LLM
from src.person_info_extraction_ontogpt import extract_person_info as information_extractor
from statistics import mean
from experiment_1 import parse_html_table, extract_persons_from_table

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
    "Precision": [],
    "Recall": [],
    "F1-score": []
}

def process_single_image(image_name, IE_method="ontogpt"):
    """Run the full evaluation pipeline for one image and return metrics."""
    print("\n===================================")
    print(f"Processing {image_name}...")

    pagexml_file = os.path.join(DATA_DIR, f"{image_name}.xml")
    output_html_file = os.path.join(OUTPUT_HTML_DIR, f"{image_name}.html")
    pagexml_to_html(pagexml_file, output_html_file)

    with open(output_html_file, encoding="utf-8") as f:
        pred_html = f.read()

    # --- Information Extraction ---
    logical_rows = parse_html_table(pred_html)

    if IE_method == "llm":
        # TODO: this method do not store row index in the JSON output
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
                    information_extractor(i, row, schema_path=SCHEMA_PATH, json_output=os.path.join(TEMP_DIR, temp_file), temp_dir=TEMP_DIR, llm_model=LLM_MODEL)
                except Exception as e:
                    print(f" ❌ Error processing row {i}: {e}")
                    traceback.print_exc()
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
    
    print(f"Information Extraction - \nPrecision: {precision:.4f}, \nRecall: {recall:.4f}, \nF1-score: {f1_score:.4f}")
    return precision, recall, f1_score

def calculate_IE_score():
    for file in os.listdir(DATA_DIR): 
        if not file.endswith(".xml"): 
            continue 

        image_name = file.replace(".xml", "") 

        try: 
            p, r , f= process_single_image(image_name) 
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




###############################################################################
# MAIN PIPELINE
###############################################################################

def main():
    folio = 45

    print("\n=== 1. Creating subgraph ===")
    graph_path = create_sub_graph_for_folio(folio)

    print("\n=== 2. Counting statistics ===")
    count_new_graph_stats(folio)

    print("\n=== 3. Downloading images ===")
    download_images_for_folio(folio)

    print("\n=== 4. Building JSON files ===")
    build_json_for_images(folio)

    print("\n=== 5. Calculating IE scores ===")
    calculate_IE_score()

if __name__ == "__main__":
    main()