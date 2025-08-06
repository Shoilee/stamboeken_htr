import requests, os
import xml.etree.ElementTree as ET
from lxml import etree
from tqdm import tqdm


def download_image(url, image_label, output_path):
    try:
        # Send a GET request to the image URL
        response = requests.get(url, stream=True)
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            filename = os.path.join(output_path, image_label)
            # Save the image to the local file
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"Image saved: {filename}")
        else:
            print(f"Failed to download image from {url}. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred while downloading the image: {e}")


def send_get_request_and_process_xml(record_url, target, headers=None):
    namespaces = {
        'oai': 'http://www.openarchives.org/OAI/2.0/',
        'dc': 'http://dublincore.org/documents/dcmi-namespace/',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'mets': 'http://www.loc.gov/METS/',
        'xlink': 'http://www.w3.org/1999/xlink'
    }
    try:
        record_response = requests.get(record_url, headers=headers)

        if record_response.status_code == 200:
            record_root = etree.fromstring(record_response.content)

            # Directory where images will be saved
            image_directory = f"../stamboek_{target}"
            if not os.path.exists(image_directory):
                os.makedirs(image_directory)

            # path query to extract dao element for the given control book
            xpath_query = f'''//did[unitid[@identifier and text()={target}]]//dao[@href]'''
            dao_elements = record_root.xpath(xpath_query, namespaces=namespaces)

            for dao in dao_elements: # Note: Typically, there should be just one element
                # url to access control book
                control_book_url = dao.attrib['href']

                try:
                    control_book_response = requests.get(control_book_url, headers=headers)

                    if control_book_response.status_code == 200:
                        control_book_root = etree.fromstring(control_book_response.content)

                        # Retrieve ID & HREF for all images from given control book
                        xpath_query1 = '//mets:fileGrp[@USE="DEFAULT"]/mets:file/@ID | ' \
                                                    '//mets:fileGrp[@USE="DEFAULT"]/mets:file/mets:FLocat/@xlink:href '
                        query_results = control_book_root.xpath(xpath_query1, namespaces=namespaces)

                        """Convert consecutive pairs in a list to dictionaries with 'id' and 'href' keys."""
                        dictionary_list = []
                        # Iterate through the list two items at a time
                        for i in range(0, len(query_results), 2):
                            if i + 1 < len(query_results):
                                # Create a dictionary for each pair
                                pair_dict = {
                                    "id": str(query_results[i])[:-3],
                                    "href": query_results[i + 1]
                                }
                                dictionary_list.append(pair_dict)

                        for item in tqdm(dictionary_list):
                            print(f"{item['href']}\n")

                            # retrieve correct image label
                            xpath_query2 = f'''//mets:div[@ID="{item['id']}"]/@LABEL'''
                            query_results = control_book_root.xpath(xpath_query2, namespaces=namespaces)
                            
                            download_image(item['href'], str(query_results[0]).split("/")[-1], image_directory)

                except Exception as e:
                    print(f"An error occurred: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # PROVIDE THE URL TO ACCESS RECORD 
    # E.g., Record --> 2.10.36.22
    url = "https://service.archief.nl/gaf/oai/!open_oai.OAIHandler?verb=ListRecords&set=2.10.50&metadataPrefix=oai_ead"
    
    # Record Contains individual Control book)
    # PROVIDE CONTROL BOOK NUMBER OF INTEREST
    control_book_no = "71"

    headers = {
        'Content-Type': 'application/xml',
    }
    send_get_request_and_process_xml(url, control_book_no, headers=headers)
