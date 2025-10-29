import re
import json
from bs4 import BeautifulSoup
from groq import Groq
import io
from src.LLM_key import groq_key

def generate_prompt(cells):
    prompt = f"""
    You are given cells of a single row of a table (one person).  
    Extract the information from this row.

    Cells of the Row:+
    {str([cell for cell in cells])}

    Rules:
    - This row corresponds to a single person.
    - Search all cell text for the following fields:
    - vader: The father’s name (after "Vader").
    - moeder: The mother’s name (after "Moeder").
    - geboorte_datum: The date after "Geboren Den".
    - geboorte_plaats: The place after "Geboortplaats".
    - laatste_woonplaats: The place after "Laatste Woonplaats".
    - For each extracted value, also include the cell’s HTML `id` where the value was found as “cell”.
    - If a field is not present, return None.
    - Output JSON in the following structure:

    Generate only the JSON for this row.

    {{
    "vader": {{"value": "...", "cell": "..."}},
    "moeder": {{"value": "...", "cell": "..."}},
    "geboorte_datum": {{"value": "...", "cell": "..."}},
    "geboorte_plaats": {{"value": "...", "cell": "..."}},
    "laatste_woonplaats": {{"value": "...", "cell": "..."}}
    }}

    """
    return prompt

def extract_info_LLM(cells, model_name="llama-3.3-70b-versatile", temperature=.5):
    client = Groq(api_key=groq_key)
    
    prompt = generate_prompt(cells)
    
    
    response_format = { "type": "json_object" }
    content = [{"type": "text", "text": prompt}]

    response = client.chat.completions.create(
       model=model_name,
        messages=[
            {
                "role": "user",
                "content": content,
            }
        ],
        temperature=temperature,
        response_format=response_format,
    )

    result = response.choices[0].message.content
    return result

def extract_info_regex(cells):
    person = {
        'vader': {'value': None, 'cell': None},
        'moeder': {'value': None, 'cell': None},
        'geboorte_datum': {'value': None, 'cell': None},
        'geboorte_plaats': {'value': None, 'cell': None},
        'laatste_woonplaats': {'value': None, 'cell': None}
    }
    for cell in cells:
        text = cell['text']
        cell_id = cell.get('id')

        vader_match = re.search(r'Vader.?\s+([^\n,<]+)', text, re.IGNORECASE)
        moeder_match = re.search(r'Moeder.?\s+([^\n,<]+)', text, re.IGNORECASE)
        geboorte_datum_match = re.search(r'Geboren\s*den\s*([^\n,<]+)', text, re.IGNORECASE)
        geboorte_plaats_match = re.search(r'Geboorte\s*plaats.?\s*([^\n,<]+)', text, re.IGNORECASE)
        laatste_woonplaats_match = re.search(r'Laatste\s*Woonplaats.?\s*([^\n,<]+)', text, re.IGNORECASE)

        if vader_match:
            person['vader'] = {'value': vader_match.group(1).strip(), 'cell': cell_id}
        if moeder_match:
            person['moeder'] = {'value': moeder_match.group(1).strip(), 'cell': cell_id}
        if geboorte_datum_match:
            person['geboorte_datum'] = {'value': geboorte_datum_match.group(1).strip(), 'cell': cell_id}
        if geboorte_plaats_match:
            person['geboorte_plaats'] = {'value': geboorte_plaats_match.group(1).strip(), 'cell': cell_id}
        if laatste_woonplaats_match:
            person['laatste_woonplaats'] = {'value': laatste_woonplaats_match.group(1).strip(), 'cell': cell_id}
 
    if all(v['value'] is None for v in person.values()):
        return json.dumps({
            'vader': {'value': None, 'cell': None},
            'moeder': {'value': None, 'cell': None},
            'geboorte_datum': {'value': None, 'cell': None},
            'geboorte_plaats': {'value': None, 'cell': None},
            'laatste_woonplaats': {'value': None, 'cell': None}
        })
    return json.dumps(person)


if __name__ == "__main__":
    # Example usage
    with open("../data/labels/NL-HaNA_2.10.50_45_0355.html", 'r', encoding='utf-8') as f:
        label_html = f.read()

    soup = BeautifulSoup(label_html, "html.parser")
    table = soup.find("table")

    soup = BeautifulSoup(label_html, "html.parser")
    table = soup.find("table")

    persons = []

    for row in table.find_all("tr"):
        cells = row.find_all("td")

        if not cells:
            continue  # skip header or empty rows
        
        # print(generate_prompt(cells))
        person = json.loads(extract_info_regex(cells))
        if all(v['value']==None for v in person.values()):
            continue
        print(person)
        persons.append(person)
