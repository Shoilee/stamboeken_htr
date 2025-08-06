from utils import check_polygone_overlap, extract_textline
import os
import json
import pandas as pd
import json

def load_jsonl(file_path):
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():  # Skip empty lines
                data.append(json.loads(line))
    return data

def find_cell_text(page_lines, cell_lines, output_file):   
    """ Reconstructs a table from the given page lines and table data.

    Args:
        page_lines: A dataFrame of textlines extracted from the pageXML.
        cell_lines: A list of cells bounding box in the table.

    Returns:
        Store json lines in the output file.
    """
    # Check if page and table are not empty
    if len(page_lines)==0 or not cell_lines:
        return
    with open(output_file, 'w') as f:
        for cell_index, cell in enumerate(cell_lines):
            print(f"Processing cell {cell_index + 1}/{len(cell_lines)}")
            matched_lines = []

            for _ , textline in page_lines.iterrows():
                if check_polygone_overlap(textline['TextRegion Coords'], cell, threshold=0.2):
                    print(f"Cell {cell_index + 1} overlaps with textline: {textline['TextEquiv Text']}")
                    matched_lines.append({
                            'TextRegion ID': textline['TextRegion ID'],
                            'TextLine ID': textline['TextLine ID'],
                            'TextEquiv Text': textline['TextEquiv Text'],
                            'TextRegion Coords': textline['TextRegion Coords']
                        })
            
            json_line = {str(cell_index): matched_lines}
            f.write(json.dumps(json_line) + '\n')

def add_text_to_cells(cells, cell_texts):
    """ Adds text to the cells based on their index.

    Args:
        cells: List of cells, where each cell is a tuple:
               (start_row, end_row, start_col, end_col)
        cell_texts: json lines containing text for each cell.

    Returns:
        A list of cells with added text.
    """
    
    for cell_index, cell in enumerate(cells):
        # cell = cell.strip().split(',')
        start_row, end_row, start_col, end_col = map(int, cell.split(","))
        content = ""
        
        for line in cell_texts:
            if str(cell_index) in line:
                if line[str(cell_index)]:
                    # Extract text from the matched lines
                    for item in line[str(cell_index)]:
                        if 'TextEquiv Text' in item:
                            content += item['TextEquiv Text'] + "<br/>"
                        
        
        cells[cell_index] = (start_row, end_row, start_col, end_col, content)
    
    return cells

    

def build_table_from_cells(cells):
    """
    Build a 2D table structure with rowspan, colspan, and merged cells.

    Args:
        cells: List of cells, where each cell is a tuple:
               (start_row, end_row, start_col, end_col, content)

    Returns:
        A 2D list representing the table.
    """
    cells = sorted(cells, key=lambda cell: (cell[0], cell[2]))
    
    # Step 1 & 2: Determine max dimensions of the table
    max_row = max(cell[1] for cell in cells) + 1  
    max_col = max(cell[3] for cell in cells) + 1

    # Step 3: Initialize the table
    table = [[None for _ in range(max_col)] for _ in range(max_row)]

    # Step 4: Iterate through each cell
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

    # write the table to a file
    with open("image_samples/page/NL-HaNA_2.10.50_45_0355_table_structure.txt", "w+") as f:
        for row in table:
            f.write(";".join(str(cell) if cell is not None else "" for cell in row) + "\n")

    # Step 5: Convert the table to HTML-like markup
    return table_to_markup(table)

def table_to_markup(table):
    """
    Converts a 2D table matrix with cell dictionaries into HTML markup.

    Args:
        table (list of list): Table where each cell is either:
                              - a dict with 'rowspan', 'colspan', 'content'
                              - or the string "merged"

    Returns:
        str: HTML-like markup representation of the table
    """
    markup = "<table>"
    for row in table:
        markup += "<tr>"
        for cell in row:
            if cell is None:
                markup += '<td></td>'  # Skip empty cells
            elif cell == "merged":
                continue
            else:
                rsp = cell["rowspan"]
                csp = cell["colspan"]
                content = cell["content"]
                markup += f'<td rowspan="{rsp}" colspan="{csp}">{content}</td>'
        markup += "</tr>"
    markup += "</table>"
    # print(markup)
    return markup


def main(cells_file, structure_file, page_file, json_file):
    with open(cells_file, 'r') as file:
        cell_lines = file.readlines()
    
    with open(structure_file, 'r') as file:
        cells_structure_lines = file.readlines()
    
    # read LOGHI pageXML file
    extract_textline(page_file, output_path="output")
    page_lines = pd.read_csv(page_file, quotechar='\"', escapechar='\\', on_bad_lines='skip')

    # reconstruct cell text
    find_cell_text(page_lines, cell_lines, json_file)
    cells_with_content = add_text_to_cells(cells_structure_lines, load_jsonl(json_file))

    # save cells with content to a new file
    with open(os.path.splitext(json_file)[0] + '.txt', 'w') as f:
        for cell in cells_with_content:
            line = ",".join(str(cell) for cell in cell)
            f.write(line + "\n")
    print(f"Text construction completed and saved to {json_file}")

    
    # build table from cells
    table_html = build_table_from_cells(cells_with_content)
    print("Table structure built successfully.")

    # reconstruct table and save to file
    markup_file = os.path.splitext(json_file)[0] + ".html"
    with open(markup_file, "w", encoding="utf-8") as f:
        f.write(table_html)
    print(f"Table reconstructed and saved to {markup_file}")

if __name__ == "__main__":
    image_name = "NL-HaNA_2.10.50_45_0355.jpg"
    
    # Construct paths for the files
    base_name = os.path.splitext(image_name)[0]  # Remove .jpg
    cells_bounding_box = f"BoundingBoxDetection/data/table/demo_wireless/center/{image_name}.txt"
    cells_structure = f"BoundingBoxDetection/data/table/demo_wireless/logi/{image_name}.txt"
    page_file = f"image_samples/page/{base_name}.csv"
    json_file = os.path.splitext(page_file)[0] + "_table.jsonl"
    
    main(cells_bounding_box, cells_structure, page_file, json_file=json_file)


    # array = []
    # with open("image_samples/page/NL-HaNA_2.10.50_45_0355_table_structure.txt", "r", encoding="utf-8") as f:
    #     for line in f:
    #         row = line.strip().split(";")  # split on spaces
    #         array.append(row)
    # print(table_to_markup(array))