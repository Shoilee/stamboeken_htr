# %%
from rdflib import Dataset, URIRef, Graph

# --- Load your TriG dataset ---
ds = Dataset()
ds.parse("Bronbeek_Data/Stamboeken.trig", format="trig")

# %% [markdown]
# ### Create Sub-graph for folio 45

# %%
def set_query(batch_size, offset):
    query_str = f"""
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rico: <https://www.ica.org/standards/RiC/ontology#>
        PREFIX sdo:  <https://schema.org/> 
        PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>

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

            # --- include ALL triples where ?person is subject ---
            ?person ?p ?o .
            # --- include ALL descendant triples until leaf ---
            ?o ?p1 ?o1 .

        }}
        WHERE 
        {{
            ### ORIGINAL QUERY
            ?person a sdo:Person .
            ?person rico:isOrWasSubjectOf ?archive .
            ?archive rico:identifier ?archiveID .

            BIND(REPLACE(?archiveID, "NL-HaNA_(.*?)_.*?_.*$", "$1") AS ?archiveN)
            BIND(REPLACE(?archiveID, "NL-HaNA_.*?_(.*?)_.*$", "$1") AS ?inv)
            BIND(xsd:integer(?inv) AS ?invNum)
            FILTER (?invNum = 45)

            ### ALL PERSON-SUBJECT TRIPLES
            ?person ?p ?o .
            OPTIONAL {{ ?o  ?p1 ?o1 . }}
    }}
    LIMIT {batch_size}
    OFFSET {offset}

    """
    return query_str


# %%
import time

batch_size = 100
offset = 0
timeout_minutes = 5
timeout_seconds = timeout_minutes * 60
last_success_time = time.time()

out_graph = Graph()

try:
    while True:
        query = set_query(batch_size, offset)

        print(f"\nRunning batch with OFFSET = {offset} ...")

        total_results_this_round = 0

        # Iterate over all named graphs in the dataset
        for g in ds.graphs():
            try:
                results = g.query(query)
            except Exception as e:
                print(f"Query failed in graph {g.identifier}: {e}")
                continue

            rows = list(results)
            total_results_this_round += len(rows)

            # Add results to the output graph
            for s, p, o in rows:
                # print(f"{s}, {p}, {o}")
                out_graph.add((s, p, o))

        # If any results found → reset the timer
        if total_results_this_round > 0:
            last_success_time = time.time()
            offset += batch_size
        else:
            print("⚠️ No results found in this batch.")

            # Check if >10 minutes have passed without results
            if time.time() - last_success_time > timeout_seconds:
                print("⏳ No results found for more than 10 minutes. Stopping.")
                break

            # Wait a bit before trying again
            time.sleep(5)
            offset += batch_size  # advance anyway to avoid infinite loop
finally:
    print("\n✔️ Finished querying.")
    print(f"Total triples collected: {len(out_graph)}")
    out_graph.serialize("folio_45_graph.ttl", format="turtle")
    print("Saved constructed graph → folio_45_graph.ttl")

# %% [markdown]
# ### Count the number of person in new graph

# %%
from rdflib import Graph
g=Graph()
g.parse('folio_45_graph.ttl', format="turtle")


# %%
query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix rico: <https://www.ica.org/standards/RiC/ontology#>
prefix sdo:  <https://schema.org/> 
prefix dbo:  <http://dbpedia.org/ontology/>
prefix xsd:  <http://www.w3.org/2001/XMLSchema#>
prefix pvn:  <https://w3id.org/pnv#>
prefix ricrst: <https://www.ica.org/standards/RiC/vocabularies/recordSetTypes#>
SELECT (COUNT(DISTINCT ?person) AS ?p) (COUNT(DISTINCT ?archiveID) AS ?a) WHERE {
      ?person a sdo:Person .
      ?person rico:isOrWasSubjectOf ?archive.
      ?archive rico:identifier ?archiveID.

      bind(replace(?archiveID, 'NL-HaNA_(.*?)_.*?_.*$','$1') as ?archiveN)
      bind(replace(?archiveID, 'NL-HaNA_.*?_(.*?)_.*$','$1') as ?inv)

      # CAST inv to integer
      BIND(xsd:integer(?inv) AS ?invNum)
      FILTER (?invNum=45)
  
      bind(uri(concat('https://www.nationaalarchief.nl/onderzoeken/archief/', ?archiveN,'/invnr/',?inv,'/file/', ?archiveID)) as ?archiveLink)

}
"""

for row in g.query(query):
    print(f"The number of unique person in new graph: {row.p}\nThe number of unique image in new graph: {row.a}")

# %% [markdown]
# ### Download image using achivalLink

# %%
from src.image_downlaod.download_stamboeken import process_archive_link
from src.image_downlaod.download_control_book import download_image
def download_image_from_graph(graph, output_directory):
    query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        prefix rico: <https://www.ica.org/standards/RiC/ontology#>
        prefix sdo:  <https://schema.org/> 
        prefix dbo:  <http://dbpedia.org/ontology/>
        prefix xsd:  <http://www.w3.org/2001/XMLSchema#>
        prefix pvn:  <https://w3id.org/pnv#>
        prefix ricrst: <https://www.ica.org/standards/RiC/vocabularies/recordSetTypes#>
        SELECT ?archiveID ?archiveLink WHERE {
            ?person a sdo:Person .
            ?person rico:isOrWasSubjectOf ?archive.
            ?archive rico:identifier ?archiveID.

            bind(replace(?archiveID, 'NL-HaNA_(.*?)_.*?_.*$','$1') as ?archiveN)
            bind(replace(?archiveID, 'NL-HaNA_.*?_(.*?)_.*$','$1') as ?inv)

            # CAST inv to integer
            BIND(xsd:integer(?inv) AS ?invNum)
            FILTER (?invNum=45)
        
            bind(uri(concat('https://www.nationaalarchief.nl/onderzoeken/archief/', ?archiveN,'/invnr/',?inv,'/file/', ?archiveID)) as ?archiveLink)

        }
    """
    for row in graph.query(query):
        image_name = f"{row.archiveID}.jpg" 
        download_url = process_archive_link(row.archiveLink, image_name)

        if download_url:
            download_image(download_url, image_name, output_directory)
        else:
            print(f"Download URL not found for {image_name}")

# %%
from rdflib import Graph
g=Graph()
g.parse('folio_45_graph.ttl', format="turtle")
download_image_from_graph(g, 'data/images')

# %% [markdown]
# ### build the true information extraction json 

# %%
def construct_image_graph(archiveID, graph):
    new_graph = Graph()
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
    # print(query)
    for row in graph.query(query):
        s, p, o = row
        new_graph.add((s, p, o))
    
    # print(f"Constructed graph with {len(new_graph)} triples")
    return new_graph

# %%
"""
Graph to JSON Converter 
Description:
    Reads an RDF/Turtle graph file and converts person-related data
    into a structured JSON format without double-wrapping values.
"""

import os
import json
from rdflib import Graph, Namespace


class RDFToJSONConverter:
    """
    Class to handle RDF graph parsing and conversion to JSON.
    """

    def __init__(self, graph_path: str):
        self.graph_path = graph_path
        self.graph = Graph()
        self.ns_schema = Namespace("https://schema.org/")
        self.ns_pnv = Namespace("https://w3id.org/pnv#")
        self.ns_rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
        self.ns_dbpedia = Namespace("http://dbpedia.org/ontology/")

    def load_graph(self):
        """Load RDF graph from Turtle file."""
        if not os.path.exists(self.graph_path):
            raise FileNotFoundError(f"Graph file not found: {self.graph_path}")
        try:
            self.graph.parse(self.graph_path, format="turtle")
        except Exception as e:
            raise ValueError(f"Failed to parse RDF graph: {e}")

    def extract_persons(self):
        """
        Extract person-related data from RDF graph.
        Returns:
            list: List of person dictionaries.
        """
        persons = []
        for person in self.graph.subjects(predicate=None, object=self.ns_schema.Person):
            # Extract name details
            name_uri = self.graph.value(person, self.ns_pnv.hasName)
            name_data = {
                "label": self._get_literal(name_uri, self.ns_rdfs.label),
                "basesurname": self._get_literal(name_uri, self.ns_pnv.baseSurname),
                "firstnames": self._get_literal(name_uri, self.ns_pnv.firstName),
                "infix": self._get_literal(name_uri, self.ns_pnv.infix),
            }

            # Extract other details
            date_of_birth = self._get_literal(person, self.ns_schema.birthDate)
            birth_place_uri = self.graph.value(person, self.ns_schema.birthPlace)
            birth_place = self._get_literal(birth_place_uri, self.ns_schema.name)
            death_place_uri = self.graph.value(person, self.ns_schema.deathPlace)
            death_place = self._get_literal(death_place_uri, self.ns_schema.name)
            nationality_uri = self.graph.value(person, self.ns_schema.nationality)
            nationality = self._get_literal(nationality_uri, self.ns_schema.name)
            military_rank_uri = self.graph.value(person, self.ns_dbpedia.militaryRank)
            military_rank = self._get_literal(military_rank_uri, self.ns_schema.roleName)

            # Build structured person object
            person_obj = {
                "name": self._wrap_name(name_data),
                "date_of_birth": self._wrap_single(date_of_birth or "Not mentioned"),
                "birth_place": self._wrap_single(birth_place or "Not mentioned"),
                "last_residence": self._wrap_single(death_place or "Not mentioned"),
                "country_of_nationality": self._wrap_single(nationality or "Not applicable"),
                "military_rank": self._wrap_single(military_rank or "Not applicable")
            }
            persons.append(person_obj)
        return persons

    def _get_literal(self, subject, predicate):
        """Get literal value for a given subject and predicate."""
        if subject:
            value = self.graph.value(subject, predicate)
            return str(value) if value else None
        return None

    def _wrap_name(self, data):
        """
        Wrap name fields in required JSON structure.
        Each key gets its own wrapper.
        """
        wrapped = {}
        for key, value in data.items():
            wrapped[key] = {
                "value": value,
                "row": None,
                "cell": None,
                "original_spans": None
            }
        return wrapped

    def _wrap_single(self, value):
        """
        Wrap a single field in required JSON structure.
        """
        return {
            "value": value,
            "row": None,
            "cell": None,
            "original_spans": None
        }

    def convert_to_json(self):
        """Convert RDF data to JSON structure."""
        persons = self.extract_persons()
        return {"persons": persons}


def save_json(data, output_path):
    """Save JSON data to a file."""
    try:
        with open(output_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        print(f"✅ JSON saved to {output_path}\n")
    except Exception as e:
        raise IOError(f"Failed to save JSON: {e}")


def main():
    """
    Main function to demonstrate RDF to JSON conversion.
    Example usage:
        python rdf_to_json.py
    """
    print("Starting RDF to JSON conversion...")

    # Example files (replace with your paths)
    graph_file = "stamboeken.ttl"  # RDF/Turtle file
    output_file = "output.json"

    try:
        converter = RDFToJSONConverter(graph_file)
        converter.load_graph()
        json_data = converter.convert_to_json()
        save_json(json_data, output_file)
    except Exception as e:
        error_type = type(e).__name__
        print(f"❌ [ERROR] Failed to convert RDF to JSON.")
        print(f"   → Error Type: {error_type}")
        print(f"   → Details: {e}")
        print("   → Suggested Fix: Check RDF file format and namespaces.\n")

# %%
# construct temporary graph out of all persons in a single stamboeken
import os
from pathlib import Path
from rdflib import Graph

# Define the image directory
image_dir = 'data/images'

g=Graph()
g.parse('folio_45_graph.ttl', format="turtle")

# Process each image
for file in os.listdir(image_dir):
    if file.endswith('.jpg'):
        image_path = os.path.join(image_dir, file)
        print(f"Processing: {file.replace('.jpg', '')} ...")
        image_graph = construct_image_graph(file.replace('.jpg', ''), graph=g)
        # print(len(image_graph))
        output_ttl = f"data/graph/{file}.ttl"
        image_graph.serialize(output_ttl, format="turtle")

        print("Starting RDF to JSON conversion...\n")

        # Example files (replace with your paths)
        graph_file = output_ttl  # RDF/Turtle file
        output_file = os.path.join("data/labels/info", f"{file.replace('.jpg', '.json')}")

        try:
            converter = RDFToJSONConverter(graph_file)
            converter.load_graph()
            json_data = converter.convert_to_json()
            save_json(json_data, output_file)
        except Exception as e:
            error_type = type(e).__name__
            print(f"❌ [ERROR] Failed to convert RDF to JSON.")
            print(f"   → Error Type: {error_type}")
            print(f"   → Details: {e}")
            print("   → Suggested Fix: Check RDF file format and namespaces.\n")

# %% [markdown]
# ### Calculate IE Precision, Recall and F1

# %%



