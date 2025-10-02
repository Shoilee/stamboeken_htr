import os
import shutil
from bs4 import BeautifulSoup

def read_html_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()
    
def write_html_file(file_path, content):
    with open(file_path, 'w+', encoding='utf-8') as file:
        soup = BeautifulSoup(content, 'html.parser')
        file.write(soup.prettify()) 

def read_json_file(file_path):
    import json
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)
    
def write_json_file(file_path, data):
    import json
    with open(file_path, 'w+', encoding='utf-8') as file:
        json.dump(data, file, indent=4) 

def copy_file(file_name, source_path, output_path):
    source_path = os.path.join(source_path, file_name)
    destination_path = os.path.join(output_path, file_name)
    if os.path.exists(source_path):
        shutil.copy(source_path, destination_path)
        print(f"Copied {file_name} to {output_path}")
    else:
        print(f"{file_name} not found in {source_path}")


# Function to delete the image
def delete_file(file_name, output_path):
    image_path = os.path.join(output_path, file_name)
    if os.path.exists(image_path):
        os.remove(image_path)
        os.remove(image_path+".done")
        print(f"Deleted {file_name} from {output_path}")
    else:
        print(f"{file_name} not found in {output_path}")