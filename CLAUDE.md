# CLAUDE.md

This is a research codebase. It turns images of handwritten historical tables (Dutch colonial military registers, the *stamboeken*, from Nationaal Archief inventory `NL-HaNA_2.10.50`) into RDF Knowledge Graphs. Every graph keeps **cell-level provenance**: each fact traces back through entity, text span, cell, row and table to the source image. See [README.md](README.md) and [pipeline_diagram.png](pipeline_diagram.png).

## Pipeline

```
Image (.jpg) ──► Table reconstruction ──► PageXML ──► HTML table ──► Information Extraction (JSON) ──► RDF (assertion + provenance .trig)
```

1. **Table reconstruction** (TSR + HTR). There are three competing approaches, and comparing them is the subject of the experiments:
   - `transkribus`: PageXML exported from the Transkribus UI. This step is manual.
   - `ml`: LORE-TSR cell detection (submodule [Image2TableBoundingBoxDetection/](Image2TableBoundingBoxDetection/)) plus Loghi HTR (submodule [loghi/](loghi/), run through Docker), merged by polygon overlap in [src/reconstruct_table.py](src/reconstruct_table.py).
   - `llm` / `llm_multi`: vision LLM through Groq. Single prompt: [src/LLM.py](src/LLM.py). Modular or multi-turn: submodule [Image2Table_LLM/](Image2Table_LLM/) (`run_modular_llm.py`). [src/llm_pagexml.ipynb](src/llm_pagexml.ipynb) converts the LLM output to PageXML.
   - The dispatcher is [src/run_scripts.py](src/run_scripts.py): `--exp_name {ml,transkribus,llm,llm_multi} --data_path ... [--output_path ...]`.
2. **PageXML → HTML**: `pagexml_to_html` in [src/utils.py](src/utils.py). Each `<td>` keeps its `id`, `row`, `col`, `rowspan` and `colspan` so that provenance can be traced later.
3. **Information Extraction**: the HTML is parsed into logical rows, expanding rowspans, with one row per person. Each row goes to OntoGPT ([src/person_info_extraction_ontogpt.py](src/person_info_extraction_ontogpt.py)), which shells out to `ontogpt extract` using a LinkML template in [data/schema/](data/schema/). The default model is `ollama/llama3`. The extracted text spans are then mapped back to cell IDs. Alternatives:
   - [src/person_info_extraction.py](src/person_info_extraction.py): Groq LLM prompt, or regex.
   - [src/information_extraction/](src/information_extraction/): regex rules.
4. **KG construction** produces `data/triples/<image>_assertion.trig` and `_provenance.trig`, using CIDOC-CRM, PROV, CSVW and `dc:isPartOf`. The provenance graph is validated with pyshacl against [data/schema/data_provenance.ttl](data/schema/data_provenance.ttl).
   - [src/constructMilitaryPostingEventsKG.py](src/constructMilitaryPostingEventsKG.py) handles the `militarypostingevents.yaml` schema.
   - [src/constructPersonBasicInfoKG.py](src/constructPersonBasicInfoKG.py) handles the `personbasicinfo.yaml` schema.
   - The two scripts share most of their structure, so a change to one usually needs mirroring in the other.

## Schemas ([data/schema/](data/schema/))
- `personbasicinfo.yaml`: LinkML/OntoGPT template for a person's name, parents, birth and similar fields.
- `militarypostingevents.yaml`: LinkML/OntoGPT template for military postings: unit, place, time span, rank and note. The `annotations.prompt` fields are the actual instructions given to the LLM.
- `data_provenance.ttl`: SHACL shapes for Table, Row, Cell and span provenance.

## Experiments and evaluation (repo root)
- [experiment_1.py](experiment_1.py) / [baseline.py](baseline.py): for each PageXML in `data/tables/pagexml`, these compute **mAP** (cell polygon IoU with Hungarian matching), **TEDS / TEDS-Struct**, and IE **precision, recall and F1** against the labels. All metrics are in [src/metrics.py](src/metrics.py).
- [experiment_1b.py](experiment_1b.py): measures the share of extracted values that carry cell provenance, and recomputes IE scores after dropping values without provenance.
- [experiment_2.py](experiment_2.py): builds a subgraph for folio 45 from the existing Bronbeek KG (`Bronbeek_Data/Stamboeken.trig`, a symlink to local data), downloads the images and builds JSON ground truth.
- [main.py](main.py): a skeleton end-to-end runner. Only `PageXML2HTML` and `html2IE` are implemented. `Image2PageXML` and `IE2KG` are stubs.
- Notebooks in [experiment/](experiment/), `experiment_*.ipynb` and `test.ipynb`/`temp.ipynb` hold exploratory and statistics work.
- Ground truth is in [data/labels/](data/labels/): `polygons/*.polygons.json` for cell geometry, `tables/*.html` for table structure and text, and `info/` for IE labels, which is gitignored.

## Running things
- Run scripts **from the repo root**. Root scripts and [src/metrics.py](src/metrics.py) import with `from src.X import ...`. But [src/run_scripts.py](src/run_scripts.py), [src/reconstruct_table.py](src/reconstruct_table.py) and [src/LLM.py](src/LLM.py) use bare imports (`from utils import ...`), so they only work when run from inside `src/` or with `src/` on `PYTHONPATH`. Check which style a file uses before running it or adding imports.
- Paths such as `data/...` are hardcoded constants at the top of each script and are relative to the CWD.
- Environment: `conda env create -f htr_env.yml` (Python 3.11; it includes rdflib, pyshacl, ontogpt, groq, apted and shapely). LORE-TSR needs its own Python 3.7 env, described in the README. Loghi needs Docker images plus downloaded models.
- OntoGPT with `ollama/llama3` needs a local Ollama server running.
- There is no test suite, linter or build step. Verify changes by running the relevant script or experiment on the five folio-45 images in `data/images/`.

## Secrets and data
- Groq credentials live in `.env` (`LLM_MODEL`, `GROQ_API_KEY`) and in `src/LLM_key.py` / `Image2Table_LLM/LLM_key.py` (`groq_key`, `llm_model`). All of these are gitignored. Never print or commit them.
- `data/*` is gitignored except `data/schema/` and `data/labels/`. `exp-1/`, `exp-2/`, `output/`, `stamboek_*/` and `samples/` are also gitignored. `Bronbeek_Data` is a symlink to the user's Desktop.
- `loghi`, `Image2TableBoundingBoxDetection` and `Image2Table_LLM` are git submodules, two of them the user's own forks. Commit changes inside them in their own repos.

## Other
- [src/webapp/](src/webapp/): a small Flask tool for viewing PageXML cell polygons over images and correcting them.
- [src/image_downlaod/](src/image_downlaod/): scripts that download register images. The misspelled directory name is the real one.
- Filenames follow the pattern `NL-HaNA_2.10.50_<inventory>_<page>.jpg`, and derived files append an extension, e.g. `...0143.jpg.html` or `...0143.jpg.json`.
