import os
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from lxml import etree
import json

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Helper: parse PageXML and extract TableCell polygons
def parse_pagexml(file_path):
    """
    Returns list of polygons: [{"id": "t1c1", "points": [[x1,y1],[x2,y2],...]]}
    """
    ns = {"pc": "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"}
    tree = etree.parse(file_path)
    root = tree.getroot()
    polygons = []
    for cell in root.xpath("//pc:TableCell", namespaces=ns):
        cell_id = cell.get("id")
        coords_el = cell.find(".//pc:Coords", namespaces=ns)
        if coords_el is None:
            continue
        points_str = coords_el.get("points")  # e.g. "652,320 652,590 1312,590 1311,320"
        # Split into x,y pairs
        pts = []
        for pair in points_str.strip().split():
            if ',' in pair:
                x_str, y_str = pair.split(',', 1)
                try:
                    x = float(x_str)
                    y = float(y_str)
                    pts.append([x, y])
                except ValueError:
                    continue
        if pts:
            polygons.append({"id": cell_id, "points": pts})
    return polygons

# Route: serve uploaded files (images)
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Index: upload form
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Upload: handle image + xml and redirect to result page
@app.route('/upload', methods=['POST'])
def upload():
    image_file = request.files.get('image')
    xml_file = request.files.get('xml')

    if not image_file:
        return "No image uploaded", 400

    image_filename = image_file.filename
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
    image_file.save(image_path)

    xml_filename = None
    polygons = []
    if xml_file:
        xml_filename = xml_file.filename
        xml_path = os.path.join(app.config['UPLOAD_FOLDER'], xml_filename)
        xml_file.save(xml_path)
        polygons = parse_pagexml(xml_path)

    # Save polygons as json (server-side) so result page can fetch them
    polygons_json_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename + ".polygons.json")
    with open(polygons_json_path, "w", encoding="utf-8") as f:
        json.dump(polygons, f, ensure_ascii=False, indent=2)

    # Redirect to result page with the image filename
    return redirect(url_for('result', image=image_filename))

# Result page: show image and polygons overlay
@app.route('/result')
def result():
    image = request.args.get('image')
    if not image:
        return redirect(url_for('index'))
    polygons_json_url = url_for('uploaded_file', filename=image + ".polygons.json")
    image_url = url_for('uploaded_file', filename=image)
    return render_template('result.html', image_url=image_url, polygons_url=polygons_json_url, image_name=image)

# Endpoint: save polygons posted from client after edit
@app.route('/save_polygons', methods=['POST'])
def save_polygons():
    payload = request.get_json()
    image = payload.get("image")
    polygons = payload.get("polygons", [])
    if not image:
        return jsonify({"error": "image not specified"}), 400
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], image + ".polygons.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(polygons, f, ensure_ascii=False, indent=2)
    return jsonify({"message": "Polygons saved", "path": save_path})

if __name__ == "__main__":
    app.run(debug=True)
 