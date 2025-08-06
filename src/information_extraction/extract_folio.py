import os
from lxml import etree
import re
import csv

# Define the pattern for "folio <integer>"
pattern = re.compile('folio [0-9]+', re.IGNORECASE)


# Function to process each XML file
def process_xml(file_path):
    try:
        # Parse the XML file
        tree = etree.parse(file_path)

        # Define the namespace (taken from the XML)
        namespace = {'ns': 'http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15'}

        # Use XPath to find all PlainText elements
        plain_text_elements = tree.xpath("//ns:PlainText", namespaces=namespace)

        if not plain_text_elements:
            # Log file name if no PlainText tag is found
            with open(os.path.join(output_directory, "image_htr_error.txt"), "a+") as error_log:
                error_log.write(f"{file_path}\n")
            print(f"No PlainText tag found in {file_path}. Logged in image_htr_error.txt.")

        else:
            # If PlainText tags are found, check each one for the pattern
            dict = {'image': None, 'folio': list()}
            for element in plain_text_elements:
                dict['image'] = file_path.split("/")[-1]
                if element.text and pattern.search(element.text):
                    print(f"File: {file_path} | Tag: {element.tag} | Text: {element.text}")
                    dict['folio'].append(element.text)
            return dict

    except etree.XMLSyntaxError:
        print(f"Error parsing {file_path}. File may be malformed.")


# Walk through all .xml files in the folder
def process_all_xml_files(folder):
    folio_list = list()
    for root_dir, _, files in os.walk(folder):
        for file_name in sorted(files):
            if file_name.endswith(".xml"):
                file_path = os.path.join(root_dir, file_name)
                folios = process_xml(file_path)
                if folios:
                    folio_list.append(folios)

    csv_file = os.path.join(output_directory, 'image_to_folio_mapping.csv')
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['image', 'folio'])
        for item in folio_list:
            writer.writerow([item['image'], ', '.join(item['folio'])])
    print(f"Data has been written to {csv_file}")


# Example usage
input_path = "../image_samples/page"
output_directory = '../output'
process_all_xml_files(input_path)