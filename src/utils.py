from shapely.geometry import Polygon
from lxml import etree
import csv
import os
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

def check_polygone_overlap(poly1:str, poly2:str, threshold=0.5) -> bool:
    """
    Check if polygon 1 is at least `threshold` inside polygon 2.

    Args:
        poly1: Co-ordinates string for polygon 1
        poly2: Co-ordinates string for polygon 2
        threshold: Float between 0 and 1, e.g., 0.9 means 90% of poly1 is inside poly2

    Returns:
        True if A is at least `threshold` inside B, else False
    """
    try:
        polygon1 = Polygon(parse_polygon_string(poly1))
        polygon2 = Polygon(parse_polygon_string(poly2))
    except Exception as e:
        print(f"Error parsing polygon string: {e}")
        return False

    if not polygon1.is_valid or not polygon2.is_valid:
        print("Error: One of the polygons is invalid.")
        return False
    
    intersection_area = polygon1.intersection(polygon2).area
    area_1 = polygon1.area

    coverage = intersection_area / area_1 if area_1 > 0 else 0
    return coverage >= threshold


def compute_iou(poly1:str, poly2:str):
    """
    Calculate the overlap area between two polygons.
    
    Returns:
        float: The area of overlap between the two polygons.
    """
    from shapely.geometry import Polygon
    
    polygon1 = Polygon(parse_polygon_string(poly1))
    polygon2 = Polygon(parse_polygon_string(poly2))
    
    if not polygon1.is_valid or not polygon2.is_valid:
        return 0.0
    
    intersection = polygon1.intersection(polygon2).area
    if intersection == 0:
        return 0.0
    union = polygon1.union(polygon2).area
    
    return intersection / union if union > 0 else 0.0
            
def parse_polygon_string(polygon_str):
    """
    Parses polygon coordinate strings into a list of (x, y) float tuples.
    
    Supports:
    - Semicolon-separated: "x1,y1;x2,y2;..."
    - Space-separated:     "x1,y1 x2,y2 ..."
    
    Returns:
    - List of (x, y) float tuples
    """
    # Normalize the separators
    cleaned = polygon_str.replace(";", " ").strip()
    points = cleaned.split()
    
    coords = []
    for point in points:
        if not point.strip():
            continue
        try:
            x_str, y_str = point.strip().split(",")
            coords.append((float(x_str), float(y_str)))
        except ValueError:
            print(f"Skipping invalid point: {point}")
            continue
    return coords

def extract_textline(file_path, output_path):
    try:
        # Load the XML content (from a file)
        root = etree.parse(file_path)

        # XPath query to get TextRegion id, TextLine id, and TextEquiv text without nested Word tags
        result = root.xpath(
            '//ns:TextRegion/ns:TextLine[ns:TextEquiv[not(ancestor::ns:Word)]]',
            namespaces={'ns': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}
        )

        if result is None:
            # Log file name if no TextEquiv tag is found
            with open(os.path.join(output_path, "image_htr_error.txt"), "a+") as error_log:
                error_log.write(f"{file_path}\n")
            print(f"No TextEquiv tag found in {file_path}. Logged in image_htr_error.txt.")
            return

        output_file = os.path.join(output_path, (os.path.basename(file_path) + ".csv"))
        with open(output_file, "w+") as f:
            csvwriter = csv.writer(f)
            # Write header row
            csvwriter.writerow(["TextRegion ID", "TextLine ID", "TextRegion Coords", "TextEquiv Text"])

            # Extract and print the required information
            for line in result:
                text_region_id = line.getparent().get("id")
                text_line_id = line.get("id")
                text_line_coords = line.find("ns:Coords", namespaces={
                    'ns': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}).get("points")
                text_equiv_text = line.find("ns:TextEquiv/ns:PlainText", namespaces={
                    'ns': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}).text
                csvwriter.writerow([text_region_id, text_line_id, text_line_coords, text_equiv_text])
            
            return output_file

    except etree.XMLSyntaxError:
        print(f"Error parsing {file_path}. File may be malformed.")


def swap_row_col(file_path):
    import csv
    with open(file_path, 'r') as f:
        reader = csv.reader(f)

        # swap col 0 with col 2 anf col 1 with col 3
        data = list(reader)
        swapped_data = []
        for row in data:
            if len(row) >= 4:
                row[0], row[2] = row[2], row[0]
                row[1], row[3] = row[3], row[1]
            swapped_data.append(row)
        output_file = file_path
        with open(output_file, 'w', newline='') as f_out:
            writer = csv.writer(f_out)
            writer.writerows(swapped_data)
        print(f"Swapped data written to {output_file}")


def pagexml_to_html(pagexml_file, output_file):
    # Register the PAGE namespace
    ns = {"pc": "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"}

    # Parse the XML
    tree = ET.parse(pagexml_file)
    root = tree.getroot()

    # Find the TableRegion
    table_region = root.find(".//pc:TableRegion", ns)

    # Collect all cells
    cells = []
    for cell in table_region.findall("pc:TableCell", ns):
        row = int(cell.attrib.get("row", 0))
        col = int(cell.attrib.get("col", 0))
        colspan = int(cell.attrib.get("colSpan", 1))   # default = 1
        rowspan = int(cell.attrib.get("rowSpan", 1))   # default = 1
        cell_id = cell.attrib.get("id", "")

        # Collect text lines (respect reading order)
        lines = []
        for tl in sorted(cell.findall("pc:TextLine", ns), key=lambda x: int(x.attrib["custom"].split("index:")[1].split(";")[0]) if "custom" in x.attrib else 9999):
            unicode_el = tl.find(".//pc:Unicode", ns)
            if unicode_el is not None and unicode_el.text:
                lines.append(unicode_el.text.strip())

        # Fallback for cell-level TextEquiv (if no lines)
        if not lines:
            for unicode_el in cell.findall("pc:TextEquiv/pc:Unicode", ns):
                if unicode_el.text:
                    lines.append(unicode_el.text.strip())

        cell_text = "<br/>".join(lines)

        cells.append({
            "row": row,
            "col": col,
            "colspan": colspan,
            "rowspan": rowspan,
            "id": cell_id,
            "text": cell_text
        })

    # Build HTML table
    max_row = max(c["row"] for c in cells)
    max_col = max(c["col"] for c in cells)

    # Group by row
    rows = {}
    for c in cells:
        rows.setdefault(c["row"], []).append(c)

    # Sort each row by column
    for r in rows:
        rows[r] = sorted(rows[r], key=lambda x: x["col"])

    # Construct HTML string
    html = ["<table border='1'>"]
    for r in range(max_row + 1):
        html.append("  <tr>")
        for c in rows.get(r, []):
            html.append(
                f"    <td id='{c['id']}' "
                f"row='{c['row']}' col='{c['col']}' "
                f"colspan='{c['colspan']}' rowspan='{c['rowspan']}'>"
                f"{c['text']}</td>"
            )
        html.append("  </tr>")
    html.append("</table>")

    html_str = "\n".join(html)

    table = BeautifulSoup(html_str, "html.parser")

    # Save to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(table.prettify())

    return html_str


def extract_HTML(text):
    # ```html
    # ```
    start_index = text.find('```html')
    end_index = text.rfind('</table>')
    if start_index != -1 and end_index != -1:
        s = text[start_index + 7:end_index + 8]
        s = s.strip()
        soup = BeautifulSoup(s, 'html.parser')
        cleaned_html = str(soup.table)
        cleaned_html = cleaned_html.replace("\n", "")
        return cleaned_html
    else:
        start_index = text.find('<table>')
        if start_index != -1 and end_index != -1:
            s = text[start_index:end_index + 8]
            s = s.strip()
            soup = BeautifulSoup(s, 'html.parser')
            cleaned_html = str(soup.table)
            cleaned_html = cleaned_html.replace("\n", "")
            return cleaned_html
        raise Exception("Parse error! Not find HTML in LLM response!")


def format_td(html):
    html = html.replace("\n", "")
    html = html.replace(".", "")
    html = html.replace(".*", "")
    html = html.replace("<thead>", "").replace("</thead>", "")
    html = html.replace("<tbody>", "").replace("</tbody>", "")
    return html




if __name__ == "__main__":
    # polygon_str1 = "1021,1055 1071,1048 1118,1034 1131,1078 1077,1093 1027,1100" # line region (smaller polygone)
    # polygon_str2 = "1031.3846,974.5904;1122.732,974.5985;1122.7303,1081.7006;1031.3759,1081.7185" # cell region (larger polygone)
    
    # print(check_polygone_overlap(polygon_str1, polygon_str2, threshold=0.5))  
    # print(compute_iou(polygon_str1, polygon_str2)) 
    extract_textline("image_samples/page/NL-HaNA_2.10.50_45_0355.xml", output_path="output")
