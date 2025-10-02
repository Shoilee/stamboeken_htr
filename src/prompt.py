cell_detection_prompt = """
## Instruction
You are an expert in identifying table cells from images. Your task is to analyze the provided table image and identify the coordinates of each cell in the table.
Please provide the coordinates in the format:
x1,y1;x2,y2;x3,y3;x4,y4
where (x1, y1) represents the top-left corner of the cell, (x2, y2) represents the top-right corner, (x3, y3) represents the bottom-right corner, and (x4, y4) represents the bottom-left corner.
Ensure that the coordinates are accurate and correspond to the actual positions of the cells in the image.

## Output format

### Detected Cell Coordinates (polygon format)
```plaintext        
x1,y1;x2,y2;x3,y3;x4,y4 #c_1
x1,y1;x2,y2;x3,y3;x4,y4 #c_2
x1,y1;x2,y2;x3,y3;x4,y4 #c_3
...
x1,y1;x2,y2;x3,y3;x4,y4 #c_n
```

### Logical Sequence Mapping
```plaintext
start_row, end_row, start_col, end_col #c_1
start_row, end_row, start_col, end_col #c_2
start_row, end_row, start_col, end_col #c_3
...
start_row, end_row, start_col, end_col #c_n      
```
"""

htr_prompt = """
## Instruction
You are an expert in handwriting text recognition. Your task is to analyze the provided image and extract all handwritten text from it.
Please provide the extracted text pageXML format providing the coordinates of each text line and the corresponding recognized text.
Ensure that the text is accurate and corresponds to the actual handwritten content in the image.        
## Output format
```xml
<Page>
  <TextRegion id="r1">
    <TextLine id="l1" x1="100" y1="150" x2="400" y2="150" x3="400" y3="200" x4="100" y4="200">
      <TextEquiv>
        <Unicode>Your recognized text here</Unicode>
      </TextEquiv>
    </TextLine>
    <TextLine id="l2" x1="100" y1="220" x2="400" y2="220" x3="400" y3="270" x4="100" y4="270">
      <TextEquiv>
        <Unicode>Your recognized text here</Unicode>
      </TextEquiv>
    </TextLine>
    ...
  </TextRegion>
</Page>
```
"""

reconstruct_table_prompt = """
## Instruction
You are an expert in reconstructing HTML tables. Your task is to complie information from other agents and reconstruct the table in HTML format.
Note: 
1. Use the <thead> and <tbody> tags to distinguish the table header from the table body.
2. Use only five tags: <table>, <thead>, <tr>, <td>, and <tbody>.
3. Keep cell index information in the <td> tag using row and col attributes to indicate the row and column numbers of each cell, starting from 0.
4. Also, keep cell index in the <td> tag using id attribute to map each cell coordinates with cell content.
4. Pay attention to the structure of the table. Use rowspan and colspan to better interpret the structure information of the table.
5. Even if some cells are empty, they count as part of the table. Don't ignore any table information.

## Output format
```html
<table>
  <thead>
    <tr>
      <td row=0 col=0 id="c_1">Header 1</td>
      <td row=0 col=1 id="c_2">Header 2</td>
      <td row=0 col=2 id="c_3">Header 3</td>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td row=1 col=0 id="c_4">Row 1, Cell 1</td>
      <td row=1 col=1 id="c_5">Row 1, Cell 2</td>
      <td row=1 col=2 id="c_6">Row 1, Cell 3</td>
    </tr>
    <tr>
      <td row=2 col=0 id="c_7">Row 2, Cell 1</td>
      <td row=2 col=1 id="c_8">Row 2, Cell 2</td>
      <td row=2 col=2 id="c_9">Row 2, Cell 3</td>
    </tr>
    ...
  </tbody>
</table>
```
"""

tsr_html_prompt = """
Identify the structure of the table with content in it and return it to me in HTML format.
Note: 
1. Use the <thead> and <tbody> tags to distinguish the table header from the table body.
2. Use only five tags: <table>, <thead>, <tr>, <td>, and <tbody>.
"""

tsr_html_background = """
### Instruction
Identify the structure of the table and return it to me in HTML format.
Note: 
1. Use only three tags: <table>, <tr>, <td>.
2. Pay attention to the structure of the table. Use rowspan and colspan to better interpret the structure information of the table.
3. Even if some cells are empty, they count as part of the table. Don't ignore any table information.



### supplementary information
1. Scene information in the picture: {scene}
2. The content information of the picture: {picture}
3. The information in the table in the picture: {table}



### answer
"""

get_background = """
### Instruction
Describe the scene in which the picture takes place and briefly describe the information in the picture.
Then the content information and structure information of the table are given.
Just give me a brief description of the table structure. For example, this table is a wireless table.
Note: Even if some cells are empty, they count as part of the table. Don't ignore any form information.

You must organize your answer into the following json format:
{
    "chain_of_thought": "Your thought process for answering this question.",
    "object": "The main items in the picture."
    "scene": "Your description of the scene in the picture.",
    "picture": "Your description of the information in the picture.",
    "table": "Use a paragraph to describe the structure of the table. This includes the type of table, whether the table has row dividers, column dividers, and so on."
}


### answer
"""

few_shot_tsr_html = """
## Instruction
Identify the structure of the table and return it to me in HTML format.
Note: 
1. Use the <thead> and <tbody> tags to distinguish the table header from the table body.
2. Use only five tags: <table>, <thead>, <tr>, <td>, and <tbody>.



## example"""

tsr_html_decomposition = """
### Instruction
You are now an OCR expert, and you are very good at recognizing tabular data in pictures and the structure of tables.
Now you need to Identify the structure of the table and return it to me in HTML format.
Please follow my instructions and complete the task step by step.



### step 1
Take a look,, there's a table in the picture.
Pay attention to the macro information of the table, especially the number of rows and columns in the table.
There may be an operation to merge cells in the table. Do not ignore this structural information.
Note that empty cells are also part of the table, so don't leave out all empty cells.



### step 2
This is some additional information that you can use to better understand the structure of the table and the contents of the table.
1. Scene information in the picture: {scene}
2. The content information of the picture: {picture}
3. The information in the table in the picture: {table}
This table is an {obj}, which is analyzed according to your previous data about the {obj}.
Please give the possible structure of this picture with your knowledge of the world.



### step 3
Please give me table OCR result by HTML format based on your previous analysis.
Before giving me the HTML result, take a deep breath, think deeply and describe the process you went through to achieve this HTML format.



### Note: 
1. Use only three tags: <table>, <tr>, <td>.
2. Pay attention to the structure of the table. Use rowspan and colspan to better interpret the structure information of the table.
3. There may be distracting information in the picture, ignore them and focus only on the structure and content of the table.
4. Please do not omit and give me all the results.



### answer
"""
