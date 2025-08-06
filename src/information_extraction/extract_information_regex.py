from typing import Any

import os
from lxml import etree
import re
import csv


# Function to process each XML file
def extract_textequiv(file_path):
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

        output_file = os.path.splitext(file_path)[0] + ".csv"
        with open(output_file, "w") as f:
            csvwriter = csv.writer(f)
            # Write header row
            csvwriter.writerow(["TextRegion ID", "TextLine ID", "TextEquiv Text"])

            # Extract and print the required information
            for line in result:
                text_region_id = line.getparent().get("id")
                text_line_id = line.get("id")
                text_equiv_text = line.find("ns:TextEquiv/ns:PlainText", namespaces={
                    'ns': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}).text
                csvwriter.writerow([text_region_id, text_line_id, text_equiv_text])

    except etree.XMLSyntaxError:
        print(f"Error parsing {file_path}. File may be malformed.")


"""
Pseudo-code:
        |---------------------------|---------------------------|---------------------------------------------|--------------------------------------|---------------------------------|
        | Case                      | Search Keyword or Pattern  | Description                                 | Regex Pattern                        | Captured Information            |
        |---------------------------|---------------------------|---------------------------------------------|--------------------------------------|---------------------------------|
        | **1: Vader (Father)**     | `Vader`                   | Checks if line contains "Vader"             | `.*Vader\s+(.+)`                    | Text after "Vader" (Father's name) |
        | **2: Moeder (Mother)**    | `Moeder`                  | Checks if line contains "Moeder"            | `.*Moeder\s+(.+)`                   | Text after "Moeder" (Mother's name) |
        | **3: Geboorte datum (DOB)**| `Geboren`                | Checks if line contains "Geboren"           | `Geboren\s+(.+)`                    | Text after "Geboren" (Date of Birth) |
        | **4: Geboorte Plaats (Place of Birth)** | `te`        | Checks if line starts with "te"             | `^te\s+(.+)`                        | Text after "te" (Place of Birth) |
        | **5: Laatste Woonplaats (Last Residence)** | `laatst gewoond te` | Checks if line contains "laatst gewoond te" | `laatst\s*gewoond te\s+(.+)` | Text after "laatst gewoond te" (Last Residence) |
        | **6: Campaigns**          | `4-digit year followed by place name`| Checks if starts with 4 digit and followed by strings | `\b(\d{4})\s+([a-zA-Z]+[\sa-zA-Z]*)` | 4 digit as Year, string as place |
        | **7: Military Postings**          | `more than 1 date pattern`| Checks if strings has more than one date patterns | `.*?[0-9]{1,2}\s[A-Z]+[a-z]*\s[1-9]{4}\.*` | String before the date as Context, date as Event Date |
"""


def extract_information(xml_file, output_file):
    """
        Extracts genealogy information, i.e.,:
            - Vader (father)
            - Moeder (mother)
            - Geboorte datum (birth date)
            - Geboorte Plaats (birthplace)
            - Laatste Woonplaats (last residence)
        Extract  campaigns (LAST COLUMN); leaving the special comment from the same column
        from the XML content based on different cases.

        Parameters:
        xml_file (file): XML data as a file

        Returns:
        dict: Extracted genealogy information.

    """

    try:
        root = etree.parse(xml_file)

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

        # WHEN HTR DONE SUCCESSFULLY!
        genealogy_info = {
            "Vader": None,
            "Moeder": None,
            "Geboorte datum": None,
            "Geboorte Plaats": None,
            "Laatste Woonplaats": None
        }
        campaign_list = list()
        event_list = list()

        text_by_region = {}

        # Extract and print the required information
        for line in result:
            text_region_id = line.getparent().get("id")
            text_line_id = line.get("id")
            text_equiv_text = line.find("ns:TextEquiv/ns:PlainText", namespaces={
                'ns': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}).text

            if text_equiv_text is None:
                continue

            # Concatenate text for each text_region_id
            if text_region_id in text_by_region:
                # Append new text for existing text_region_id
                text_by_region[text_region_id] += f" {text_equiv_text}"
            else:
                # Initialize entry for new text_region_id
                text_by_region[text_region_id] = text_equiv_text

            # Case 1: Extract Vader
            vader_match = re.search(r'.*Vader\s+(.+)', text_equiv_text, re.IGNORECASE)
            if vader_match:
                genealogy_info["Vader"] = vader_match.group(1).strip()

            # Case 2: Extract Moeder
            moeder_match = re.search(r'.*Moeder\s+(.+)', text_equiv_text, re.IGNORECASE)
            if moeder_match:
                genealogy_info["Moeder"] = moeder_match.group(1).strip()

            # Case 3: Extract Geboorte datum (e.g., "Geboren: 01-01-1900")
            geboorte_datum_match = re.search(r'Geboren\s+(.+)', text_equiv_text, re.IGNORECASE)
            if geboorte_datum_match:
                genealogy_info["Geboorte datum"] = geboorte_datum_match.group(1).strip()

            # Case 4: Extract Geboorte Plaats (e.g., "te Amsterdam")
            geboorte_plaats_match = re.search(r'^te\s+(.+)', text_equiv_text, re.IGNORECASE)
            if geboorte_plaats_match:
                if genealogy_info["Geboorte Plaats"] is None:
                    genealogy_info["Geboorte Plaats"] = geboorte_plaats_match.group(1).strip()

            # Case 5: Extract Laatste Woonplaats (e.g., "laatst gewoond te Rotterdam")
            laatste_woonplaats_match = re.search(r'laatst\s*gewoond te\s+(.+)', text_equiv_text, re.IGNORECASE)
            if laatste_woonplaats_match:
                genealogy_info["Laatste Woonplaats"] = laatste_woonplaats_match.group(1).strip()

            # Case 6: Extract campaign (e.g., "1809 Zeeland")

            campaign_match = re.search(r'\b(\d{4})\s+([a-zA-Z]+.*)', text_equiv_text, re.IGNORECASE)
            if campaign_match:
                campaign = {"Year": campaign_match.group(1).strip(), "Place": campaign_match.group(2).strip()}
                campaign_list.append(campaign)

        # Extract Event --> Military posting information
        for region_id, concatenated_text in text_by_region.items():
            # print(f"Region ID: {region_id}, Text: {concatenated_text}")
            date_pattern = r'[0-9]{1,2}\s[A-Z]+[a-z]*\s[1-9]{4}\.*' # 2-digit(date) followed by string(month) followed by 4-digit(year)
            pattern = rf"(.*?{date_pattern})"
            event_lines = re.findall(pattern, concatenated_text)
            if len(event_lines) >= 2:
                for event in event_lines:
                    match = re.search(rf'(.*)?({date_pattern})', event, re.IGNORECASE)
                    event_dict = {
                        'Context': match.group(1).strip(),
                        'Date': match.group(2).strip()
                    }
                    event_list.append(event_dict)

        with open(output_file, 'a') as f:
            csvwriter = csv.writer(f)
            csvwriter.writerow(
                [''.join(xml_file.split('/')[-1].split(".")[:-1]),
                 genealogy_info["Vader"],
                 genealogy_info["Moeder"],
                 genealogy_info["Geboorte datum"],
                 genealogy_info["Geboorte Plaats"],
                 genealogy_info["Laatste Woonplaats"],
                 ';'.join([str(dict) for dict in campaign_list]),
                 ';'.join([str(event) for event in event_list])])

    except etree.XMLSyntaxError:
        print(f"Error parsing {file_path}. File may be malformed.")


# Walk through all .xml files in the folder
def process_all_xml_files(folder):
    output_file = os.path.join(output_path, 'regex_extracted_information.csv')
    with open(output_file, 'w+') as f:
        csvwriter = csv.writer(f)
        # Write header row
        csvwriter.writerow(["stamboeken", "Vader", "Moeder", "Geboorte datum", "Geboorte Plaats", "Laatste Woonplaats", "Campaigns"])

    for root_dir, _, files in os.walk(folder):
        for file_name in sorted(files):
            if file_name.endswith(".xml"):
                file_path = os.path.join(root_dir, file_name)
                print(f"Processing xml: {file_path}...")
                # extract_textequiv(file_path)

                extract_information(file_path, output_file)


# Example usage
input_path = "../image_samples/page"
output_path = '../output'

process_all_xml_files(input_path)
# print(extract_information("../image_samples/page/NL-HaNA_2.10.50_71_0006.xml", "out.csv")) # perfect exmaple NL-HaNA_2.10.50_71_0006.xml
