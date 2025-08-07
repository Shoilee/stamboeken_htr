from utils import check_polygone_overlap, extract_textline
import os
import json
import pandas as pd


def load_jsonl(file_path):
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def find_cell_text(page_lines, cell_lines, output_file):
    if len(page_lines) == 0 or not cell_lines:
        return

    with open(output_file, 'w') as f:
        for cell_index, cell in enumerate(cell_lines):
            # print(f"Processing cell {cell_index + 1}/{len(cell_lines)}")
            matched_lines = []

            for _, textline in page_lines.iterrows():
                if check_polygone_overlap(textline['TextRegion Coords'], cell, threshold=0.2):
                    # print(f"Cell {cell_index + 1} overlaps with textline: {textline['TextEquiv Text']}")
                    matched_lines.append({
                        'TextRegion ID': textline['TextRegion ID'],
                        'TextLine ID': textline['TextLine ID'],
                        'TextEquiv Text': textline['TextEquiv Text'],
                        'TextRegion Coords': textline['TextRegion Coords']
                    })

            json_line = {str(cell_index): matched_lines}
            f.write(json.dumps(json_line) + '\n')


def add_text_to_cells(cells, cell_texts):
    for cell_index, cell in enumerate(cells):
        start_row, end_row, start_col, end_col = map(int, cell.split(","))
        content = ""
        for line in cell_texts:
            if str(cell_index) in line:
                for item in line[str(cell_index)]:
                    if 'TextEquiv Text' in item:
                        content += str(item['TextEquiv Text']) + "<br/>"
        cells[cell_index] = (start_row, end_row, start_col, end_col, content)
    return cells


def build_table_from_cells(cells, output_file):
    cells = sorted(cells, key=lambda cell: (cell[0], cell[2]))
    max_row = max(cell[1] for cell in cells) + 1
    max_col = max(cell[3] for cell in cells) + 1

    table = [[None for _ in range(max_col)] for _ in range(max_row)]

    for cell in cells:
        start_row, end_row, start_col, end_col, content = cell
        rowspan = 1 + end_row - start_row
        colspan = 1 + end_col - start_col

        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                if row == start_row and col == start_col and table[row][col] != "merged":
                    table[row][col] = {
                        "rowspan": rowspan,
                        "colspan": colspan,
                        "content": content
                    }
                else:
                    table[row][col] = "merged"

    with open(output_file, "w+") as f:
        for row in table:
            f.write(";".join(str(cell) if cell is not None else "" for cell in row) + "\n")

    return table_to_markup(table)


def table_to_markup(table):
    markup = "<table>"
    for row in table:
        markup += "<tr>"
        for cell in row:
            if cell is None:
                markup += '<td></td>'
            elif cell == "merged":
                continue
            else:
                rsp = cell["rowspan"]
                csp = cell["colspan"]
                content = cell["content"]
                markup += f'<td rowspan="{rsp}" colspan="{csp}">{content}</td>'
        markup += "</tr>"
    markup += "</table>"
    return markup


def main(cells_file, structure_file, page_file, json_file, image_name):
    with open(cells_file, 'r') as file:
        cell_lines = file.readlines()

    with open(structure_file, 'r') as file:
        cells_structure_lines = file.readlines()

    csv_file = extract_textline(page_file, output_path=(os.path.dirname(page_file) + "/../" + "csv/"))
    page_lines = pd.read_csv(csv_file, quotechar='\"', escapechar='\\', on_bad_lines='skip')

    find_cell_text(page_lines, cell_lines, json_file)
    cells_with_content = add_text_to_cells(cells_structure_lines, load_jsonl(json_file))

    with open(os.path.join("data", "htr", "csv", image_name +'.txt'), 'w') as f:
        for cell in cells_with_content:
            line = ",".join(str(cell) for cell in cell)
            f.write(line + "\n")
    # print(f"Text construction completed and saved to {json_file}")

    table_html = build_table_from_cells(cells_with_content, output_file=os.path.join("data", "tables", "2D", image_name + ".txt"))
    print("Table structure built successfully.")

    markup_file = os.path.join("data", "tables", "html", image_name+ ".html")
    with open(markup_file, "w", encoding="utf-8") as f:
        f.write(table_html)
    print(f"Table reconstructed and saved to {markup_file}")


if __name__ == "__main__":
    image_path = "data/images/"
    image_files = [f for f in os.listdir(image_path) if f.endswith(".jpg")]

    for image_name in image_files:
        base_name = os.path.splitext(image_name)[0]

        cells_bounding_box = f"data/tables/cells/center/{image_name}.txt"
        cells_structure = f"data/tables/cells/logi/{image_name}.txt"
        page_file = f"data/htr/page/{base_name}.xml"
        json_file = f"data/tables/json/{image_name}.jsonl"

        print(f"\nProcessing image: {image_name}")
        main(cells_bounding_box, cells_structure, page_file, json_file, image_name)
