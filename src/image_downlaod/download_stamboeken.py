import re
import os
import time
import json
import requests
import openpyxl
from lxml import etree
from tqdm import tqdm
from download_control_book import download_image
import random


def parse_html_content(content):
    """
    Parse HTML content and extract the <script> element of type 'application/json'.
    
    Args:
        content (str): HTML content to parse.
    
    Returns:
        dict: Parsed JSON data from the <script> tag, or None if not found.
    """
    parser = etree.HTMLParser()
    tree = etree.fromstring(content, parser)
    script_element = tree.xpath('//script[@type="application/json"]')

    if script_element:
        script_text = script_element[0].text
        return json.loads(script_text)
    else:
        print("No <script> element with type='application/json' found.")
        return None


def extract_download_url(parsed_json, image_filename):
    """
    Extract the download URL for a specific image from the parsed JSON data.
    
    Args:
        parsed_json (dict): JSON data extracted from the HTML content.
        image_filename (str): Name of the image file to find the URL for.
    
    Returns:
        str: The download URL for the image, or None if not found.
    """
    try:
        view_response_str = parsed_json["na_viewer"]["view_response"]
        view_response = json.loads(view_response_str)

        for file in view_response.get("files", []):
            if file["filename"] == image_filename:
                return file["downloadURI"]
    except KeyError as e:
        print(f"Key error while extracting download URL: {e}")
    return None


def process_archive_link(archive_link, image_filename):
    """
    Fetch the archive link content and extract the download URL for the image.
    
    Args:
        archive_link (str): URL of the archive page.
        image_filename (str): Name of the image file.
    
    Returns:
        str: The download URL for the image, or None if not found.
    """
    try:
        response = requests.get(archive_link, headers={'Content-Type': 'application/xml'})
        if response.status_code == 200:
            parsed_json = parse_html_content(response.content)
            if parsed_json:
                return extract_download_url(parsed_json, image_filename)
        else:
            print(f"Failed to fetch archive link: {archive_link}, status code: {response.status_code}")
    except Exception as e:
        print(f"Error while processing archive link: {e}")
    return None


def parse_excel_rows(file_path):
    """
    Parse rows from an Excel file using openpyxl.
    
    Args:
        file_path (str): Path to the Excel file.
    
    Yields:
        dict: Row data as a dictionary.
    """
    workbook = openpyxl.load_workbook(file_path, read_only=True)
    rows = workbook.active.rows
    headers = [str(cell.value) for cell in next(rows)]

    for row in rows:
        yield dict(zip(headers, (cell.value for cell in row)))


def download_images_from_excel(input_file, output_directory):
    """
    Download images listed in an Excel file by constructing archive URLs.
    
    Args:
        input_file (str): Path to the Excel file containing image data.
        output_directory (str): Directory to save the downloaded images.
    """
    start_time = time.perf_counter()
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # pick random two integer from 1 to 200000
    random_indices = random.sample(range(1, 200001), 20)
    print(f"Random indices selected: {random_indices}")
    counter = 0

    for idx, row in enumerate(tqdm(parse_excel_rows(input_file), desc="Processing rows")):
        if counter == 20:
            break
        if idx not in random_indices:
            continue
        counter += 1
        stamboeken_number = row.get("NA_nummer")
        if stamboeken_number and (match := re.search(r'NL-HaNA_(.*?)_(.*?)_.*$', stamboeken_number)):
            archive_number, inventory_number = match.groups()
            archive_link = (
                f"https://www.nationaalarchief.nl/onderzoeken/archief/"
                f"{archive_number}/invnr/{inventory_number}/file/{stamboeken_number}?tab=download"
            )
            image_filename = f"{stamboeken_number}.jpg"
            download_url = process_archive_link(archive_link, image_filename)

            if download_url:
                download_image(download_url, image_filename, output_directory)
            else:
                print(f"Download URL not found for {stamboeken_number}")
        else:
            print(f"Invalid NA_nummer pattern for row: {row}")

    elapsed_time = time.perf_counter() - start_time
    print(f"Completed downloading images in {elapsed_time:.2f} seconds.")


if __name__ == "__main__":
    INPUT_FILE = 'Bronbeek_Data/Stamboeken_combined.xlsx'
    OUTPUT_DIRECTORY = 'data/images'
    download_images_from_excel(INPUT_FILE, OUTPUT_DIRECTORY)
