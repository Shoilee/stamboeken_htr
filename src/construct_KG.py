import json
import csv
from rdflib import Graph, Dataset, Namespace, URIRef, Literal, RDF, BNode
from lxml import etree

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================================================
# MODULE 1 — ASSERTION GRAPH CONSTRUCTION
# ============================================================

def build_assertion_graph(json_obj, image_name, output_path):

    # Namespaces
    SCHEMA = Namespace("https://schema.org/")
    PVN = Namespace("https://personvocab.nl/")
    DBO = Namespace("http://dbpedia.org/ontology/")
    PERSON = Namespace("https://pressingmatter.nl/personbaiscinfo/")
    EX = Namespace("https://www.example.com/")

    predicate_map = {
        "date_of_birth": SCHEMA.birthDate,
        "birth_place": SCHEMA.birthPlace,
        "last_residence": SCHEMA.homeLocation,
        "country_of_nationality": SCHEMA.nationality,
        "military_rank": DBO.militaryRank,
        "basesurname": PVN.baseName,
        "firstnames": PVN.firstName,
        "infix": PVN.infix
    }

    cg = Dataset()
    cg.bind("schema", SCHEMA)
    cg.bind("pvn", PVN)
    cg.bind("dbo", DBO)
    cg.bind("personbasicinfo", PERSON)
    cg.bind("ex", EX)

    assertion_graph_uri = URIRef("http://example.org/assertion")

    for idx, person in enumerate(json_obj["persons"], start=1):
        person_uri = URIRef(f"http://example.org/person/{image_name}/{idx}")
        assertion_graph = Graph(store=cg.store, identifier=assertion_graph_uri)
        assertion_graph.add((person_uri, RDF.type, PERSON.Person))

        for key, value_dict in person.items():

            # -------------------- Name block ---------------------
            if key == "name":
                handle_name_block(
                    person_uri, value_dict, cg, assertion_graph,
                    image_name, predicate_map
                )
                continue

            # -------------------- Normal field -------------------
            handle_standard_field(
                person_uri, key, value_dict, cg, image_name, predicate_map
            )

    cg.serialize(output_path, format="trig")
    return cg


def handle_name_block(person_uri, name_dict, cg, assertion_graph, image_name, predicate_map):
    PVN = Namespace("https://personvocab.nl/")

    name_blank = BNode()
    assertion_graph.add((person_uri, PVN.hasName, name_blank))

    for sub_key, sub_value_dict in name_dict.items():
        value = sub_value_dict.get("value")
        row = sub_value_dict.get("row")
        cells = sub_value_dict.get("cell")
        spans = sub_value_dict.get("original_spans")
        predicate = predicate_map.get(sub_key)

        if not (value and predicate):
            continue

        add_value_to_graph(
            target=name_blank,
            predicate=predicate,
            value=value,
            row=row,
            cells=cells,
            spans=spans,
            cg=cg,
            image_name=image_name
        )


def handle_standard_field(person_uri, key, value_dict, cg, image_name, predicate_map):
    value = value_dict.get("value")
    row = value_dict.get("row")
    cells = value_dict.get("cell")
    spans = value_dict.get("original_spans")
    predicate = predicate_map.get(key)

    if not (value and predicate):
        return

    add_value_to_graph(
        target=person_uri,
        predicate=predicate,
        value=value,
        row=row,
        cells=cells,
        spans=spans,
        cg=cg,
        image_name=image_name
    )


def add_value_to_graph(target, predicate, value, row, cells, spans, cg, image_name):
    """Adds a value to multiple graphs depending on provenance."""
    # Add to assertion graph
    assertion_graph_uri = URIRef("http://example.org/assertion")
    assertion_graph = Graph(store=cg.store, identifier=assertion_graph_uri)
    assertion_graph.add((target, predicate, Literal(value)))

    # Row-based graphs
    if row is not None:
        graph_uri = URIRef(f"http://example.org/graph/{image_name}/row_{int(row)}")
        g = Graph(store=cg.store, identifier=graph_uri)
        g.add((target, predicate, Literal(value)))

    # Cell-based graphs
    if isinstance(cells, list):
        for cell in cells:
            graph_uri = URIRef(f"http://example.org/graph/{image_name}/{cell}")
            g = Graph(store=cg.store, identifier=graph_uri)
            g.add((target, predicate, Literal(value)))
    elif cells:
        graph_uri = URIRef(f"http://example.org/graph/{image_name}/{cells}")
        g = Graph(store=cg.store, identifier=graph_uri)
        g.add((target, predicate, Literal(value)))

    # Text span graphs
    if isinstance(spans, list):
        for span in spans:
            graph_uri = URIRef(f"http://example.org/text_span/{image_name}/{str(span).replace(':', '_')}")
            g = Graph(store=cg.store, identifier=graph_uri)
            g.add((target, predicate, Literal(value)))
    elif spans:
        graph_uri = URIRef(f"http://example.org/text_span/{image_name}/{str(spans).replace(':', '_')}")
        g = Graph(store=cg.store, identifier=graph_uri)
        g.add((target, predicate, Literal(value)))


# ============================================================
# MODULE 2 — PROVENANCE GRAPH
# ============================================================

def extract_elements_with_row(data):
    results = []

    def recurse(node):
        if isinstance(node, dict):
            if "row" in node:
                results.append(node)
            for v in node.values():
                recurse(v)
        elif isinstance(node, list):
            for item in node:
                recurse(item)

    recurse(data)
    return results


def get_cell_info(root, cell_id):
    cell = root.find(f".//{{*}}TableCell[@id='{cell_id}']")
    if cell is None:
        return None
    coords = cell.find(".//{*}Coords")
    return {
        "cell_id": cell_id,
        "row": cell.get("row"),
        "col": cell.get("col"),
        "coords": coords.get("points") if coords is not None else None
    }


def add_provenance_graph(json_path, pagexml_path, stamboek_nummer, output_path):
    EX = Namespace("http://example.org/ontology/")
    PROV = Namespace("http://www.w3.org/ns/prov#")
    RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
    CSVW = Namespace("http://www.w3.org/ns/csvw#")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

    json_data = load_json(json_path)
    elements = extract_elements_with_row(json_data)

    tree = etree.parse(pagexml_path)
    root = tree.getroot()

    g = Dataset()
    g.bind("ex", EX)
    g.bind("prov", PROV)
    g.bind("csvw", CSVW)
    g.bind("skos", SKOS)
    g.bind("rdfs", RDFS)

    provenance_graph_uri = URIRef("http://example.org/provenance")
    provenance_graph = Graph(store=g.store, identifier=provenance_graph_uri)

    for elem in elements:
        process_row_provenance(elem, provenance_graph, root, stamboek_nummer)

    g.serialize(output_path, format="trig")
    return g


def process_row_provenance(elem, g, root, stamboek_nummer):
    """Handles one JSON row block and creates its provenance triples."""
    PROV = Namespace("http://www.w3.org/ns/prov#")
    EX = Namespace("http://example.org/ontology/")
    CSVW = Namespace("http://www.w3.org/ns/csvw#")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")

    row_id = elem["row"]
    cells = elem.get("cell")
    spans = elem.get("original_spans")

    row_graph_uri = URIRef(f"http://example.org/graph/{stamboek_nummer}/row_{row_id}")
    row_uri = URIRef(f"http://example.org/id/{stamboek_nummer}/row_{row_id}")

    g.add((row_graph_uri, PROV.wasDerivedFrom, row_uri))
    g.add((row_uri, RDF.type, PROV.Entity))
    g.add((row_uri, RDF.type, EX.Row))
    g.add((row_uri, RDFS.label, Literal(f"Row {row_id} from {stamboek_nummer}")))

    # agents
    agent_1 = URIRef("http://example.org/agent/1")
    g.add((agent_1, RDF.type, PROV.Agent))
    g.add((agent_1, RDFS.label, Literal("Jane Doe")))
    g.add((row_graph_uri, PROV.wasAttributedTo, agent_1))
    project_agent = URIRef("http://example.org/agent/2")
    g.add((project_agent, RDF.type, PROV.Agent))
    g.add((project_agent, RDFS.label, Literal("Pressing Matter Project")))
    g.add((agent_1, PROV.actedOnBehalfOf, project_agent))

    # activity
    stamboekenKGConstructionactivity = URIRef(f"http://example.org/activity/stamboekenKGConstructionactivity/{stamboek_nummer}")
    tableConstructionactivity = URIRef(f"http://example.org/activity/TableExtraction/{stamboek_nummer}")
    informationExtractionactivity = URIRef(f"http://example.org/activity/InformationExtraction/{stamboek_nummer}/row_{row_id}")
    KGConstructionactivity = URIRef(f"http://example.org/activity/KGConstruction/{stamboek_nummer}/row_{row_id}")
            
    g.add((stamboekenKGConstructionactivity, RDF.type, PROV.Activity))
    # g.add((named_graph_uri, PROV.wasGeneratedBy, stamboekenKGConstructionactivity))
    g.add((stamboekenKGConstructionactivity, PROV.wasAssociatedWith, agent_1))
    g.add((stamboekenKGConstructionactivity, PROV.wasInformedBy, tableConstructionactivity))
    g.add((tableConstructionactivity, RDF.type, PROV.Activity))
    g.add((stamboekenKGConstructionactivity, PROV.wasInformedBy, informationExtractionactivity))
    g.add((informationExtractionactivity, RDF.type, PROV.Activity))
    g.add((informationExtractionactivity, PROV.used, row_uri))
    g.add((stamboekenKGConstructionactivity, PROV.wasInformedBy, KGConstructionactivity))
    g.add((KGConstructionactivity, RDF.type, PROV.Activity))

    json_URI = URIRef(f"http://example.org/json/{stamboek_nummer}.json")
    g.add((json_URI, RDF.type, PROV.Entity))
    g.add((json_URI, RDFS.label, Literal(f"JSON file: {stamboek_nummer}.json")))
    g.add((KGConstructionactivity, PROV.used, json_URI))

    # TODO: add more information about prov:Activity
    # g.add((stamboekenKGConstructionactivity,PROV.endedAtTime, Literal(end_time)))
    # g.add((stamboekenKGConstructionactivity,PROV.startedAtTime, Literal(start_time)))

    # Create a Table instance URI
    table_uri = URIRef(f"http://example.org/Table/{stamboek_nummer}")
    g.add((table_uri, RDF.type, PROV.Entity))
    g.add((table_uri, RDF.type, EX.Table))
    g.add((table_uri, RDFS.label, Literal(f"Table from {stamboek_nummer}")))
    g.add((table_uri, PROV.wasGeneratedBy, tableConstructionactivity))
    g.add((row_uri, SKOS.partOf, table_uri))
        
    # stamboeken
    stamboek_uri = URIRef(f"http://example.org/Image/{stamboek_nummer}")
    g.add((stamboek_uri, RDF.type, PROV.Entity))
    g.add((stamboek_uri, RDF.type, EX.Image))
    g.add((stamboek_uri, RDFS.label, Literal(f"Stamboek {stamboek_nummer}")))
    g.add((tableConstructionactivity, PROV.used, stamboek_uri))
    g.add((table_uri, PROV.wasDerivedFrom, stamboek_uri))
    national_archives = URIRef("http://example.org/agent/3")
    g.add((national_archives, RDF.type, PROV.Agent))
    g.add((national_archives, RDFS.label, Literal("Nationaal Archief")))
    g.add((stamboek_uri, PROV.wasAttributedTo, national_archives))

    # Cell entries
    if cells:
        if isinstance(cells, list):
            for cell_id in cells:
                process_cell_provenance(cell_id, g, root, stamboek_nummer, row_uri)
        else:
            process_cell_provenance(cells, g, root, stamboek_nummer, row_uri)

    # Text spans
    if spans:
        if isinstance(spans, list):
            for span in spans:
                process_span(span, g, stamboek_nummer, row_uri)
        else:
            process_span(spans, g, stamboek_nummer, row_uri)


def process_cell_provenance(cell_id, g, root, stamboek_nummer, row_uri):
    PROV = Namespace("http://www.w3.org/ns/prov#")
    CSVW = Namespace("http://www.w3.org/ns/csvw#")
    EX = Namespace("http://example.org/ontology/")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")

    info = get_cell_info(root, cell_id)
    if info is None:
        return

    cell_uri = URIRef(f"http://example.org/id/{stamboek_nummer}/{cell_id}")

    g.add((cell_uri, RDF.type, PROV.Entity))
    g.add((cell_uri, RDFS.label, Literal(f"Cell {cell_id} from {stamboek_nummer}")))
    g.add((cell_uri, CSVW.rowNumber, Literal(info["row"])))
    g.add((cell_uri, CSVW.columnNumber, Literal(info["col"])))
    g.add((cell_uri, EX.ImageRegion, Literal(info["coords"])))
    g.add((cell_uri, SKOS.partOf, row_uri))


def process_span(span, g, stamboek_nummer, row_uri):
    PROV = Namespace("http://www.w3.org/ns/prov#")
    EX = Namespace("http://example.org/ontology/")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")

    span_id = str(span).replace(":", "_")
    span_uri = URIRef(f"http://example.org/id/{stamboek_nummer}/{span_id}")

    g.add((span_uri, RDF.type, PROV.Entity))
    g.add((span_uri, EX.range, Literal(span)))
    g.add((span_uri, SKOS.partOf, row_uri))
    g.add((span_uri, RDFS.label, Literal(f"Span {span}")))


# ============================================================
# MODULE 3 — TRIPLE COUNTING
# ============================================================

def count_triples(path):
    cg = Dataset()
    cg.parse(path, format="trig")
    unique = set(cg.quads((None, None, None, None)))
    spo = set((s, p, o) for s, p, o, _ in unique)
    return len(unique), len(spo)


# ============================================================
# MAIN EXECUTION PIPELINE
# ============================================================
from pyshacl  import validate
import os
def main(directory):
    # Iterate through all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith(".jpg"):
            image_name = filename
            json_path = f"data/json/{image_name}.json"
            pagexml_path = f"data/tables/pagexml/{image_name}.xml"
            assertion_output = f"data/triples/{image_name.replace('.jpg', '')}_assertion.trig"
            provenance_output = f"data/triples/{image_name.replace('.jpg', '')}_provenance.trig"
            provenace_shacl_shape = "data/schema/data_provenance.ttl"

            json_obj = load_json(json_path)

            # 1. Assertion graph
            build_assertion_graph(json_obj, image_name, assertion_output)

            # 2. Provenance graph
            add_provenance_graph(json_path, pagexml_path, image_name, provenance_output)

            # 3. Triple counts
            graphs_total, spo_total = count_triples(assertion_output)
            print(
                f"Triple counts for {image_name}:"
                f"\n\t{graphs_total} quads across all graphs (includes graph/context), and"
                f"\n\t{spo_total} unique triples (subject-predicate-object, graph context ignored)."
            )

            # If SHACL validation is needed
            try:
                conforms, results_graph, results_text = validate(
                        provenance_output,
                        shacl_graph=provenace_shacl_shape,
                        data_graph_format="trig",
                        shacl_graph_format="turtle",
                        inference="rdfs",
                        abort_on_error=False,
                        meta_shacl=False,
                        advanced=False,
                        js=False,
                    )
                print(f"Provenance SHACL Conforms for {image_name}:", conforms)
                print(results_text)
            except Exception as e:
                print("Error during SHACL validation for", image_name, ":", e)


if __name__== "__main__":
    main("data/images")