from shapely.geometry import Polygon
from lxml import etree
import csv
import os

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

if __name__ == "__main__":
    # polygon_str1 = "1021,1055 1071,1048 1118,1034 1131,1078 1077,1093 1027,1100" # line region (smaller polygone)
    # polygon_str2 = "1031.3846,974.5904;1122.732,974.5985;1122.7303,1081.7006;1031.3759,1081.7185" # cell region (larger polygone)
    
    # print(check_polygone_overlap(polygon_str1, polygon_str2, threshold=0.5))  
    # print(compute_iou(polygon_str1, polygon_str2)) 
    extract_textline("image_samples/page/NL-HaNA_2.10.50_45_0355.xml", output_path="output")
