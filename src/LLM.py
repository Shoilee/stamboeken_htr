from groq import Groq
import base64
import io

from LLM_key import groq_key, llm_model
from prompt import tsr_html_prompt, cell_detection_prompt, htr_prompt, reconstruct_table_prompt

image_path = "example/stamboeken/NL-HaNA_2.10.50_45_0355.jpg"
# Function to encode the image
def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

def LLM_table_construct(image_path, prompt=tsr_html_prompt, model_name=llm_model, temperature=0):
    client = Groq(api_key=groq_key)
    base64_image = encode_image(image_path)
    content = [{"type": "text", "text": prompt}]

    content.append({
       "type": "image_url",
       "image_url": {
            "url": f"data:image/jpeg;base64,{base64_image}",
        }
    })

    response = client.chat.completions.create(
       model=model_name,
        messages=[
            {
                "role": "user",
                "content": content,
            }
        ],
        temperature=temperature,
    )

    result = response.choices[0].message.content
    print(result)
    return result


def LLM_multi_agent_table_construct(image_path, model_name=llm_model, temperature=0):
    client = Groq(api_key=groq_key)
    base64_image = encode_image(image_path)
    prompt= "Here is a table image. Please collaborate to: (1) detect table cells, (2) run HTR, (3) reconstruct the HTML table."
    content = [{"type": "text", "text": prompt}]

    content.append({
       "type": "image_url",
       "image_url": {
            "url": f"data:image/jpeg;base64,{base64_image}",
        }
    })

    response = client.chat.completions.create(
       model=model_name,
        messages=[
            {
                "role": "user",
                "content": content,
            },
            {
                "role": "user",
                "content": f"{cell_detection_prompt}"
            },
            {
                "role": "user",
                "content": f"{htr_prompt}"
            },
            {
                "role": "user",
                "content": f"{reconstruct_table_prompt}"
            }
        ],
        temperature=temperature,
    )

    result = response.choices[0].message.content
    print(result)
    return result