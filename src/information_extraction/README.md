## Extract Information using Regex Patterns
| Case                                       | Search Keyword or Pattern             | Description                                           | Regex Pattern                              | Captured Information                                  |
|--------------------------------------------|---------------------------------------|-------------------------------------------------------|--------------------------------------------|-------------------------------------------------------|
| **1: Vader (Father)**                      | `Vader`                               | Checks if line contains "Vader"                       | `.*Vader\s+(.+)`                           | Text after "Vader" (Father's name)                    |
| **2: Moeder (Mother)**                     | `Moeder`                              | Checks if line contains "Moeder"                      | `.*Moeder\s+(.+)`                          | Text after "Moeder" (Mother's name)                   |
| **3: Geboorte datum (DOB)**                | `Geboren`                             | Checks if line contains "Geboren"                     | `Geboren\s+(.+)`                           | Text after "Geboren" (Date of Birth)                  |
| **4: Geboorte Plaats (Place of Birth)**    | `te`                                  | Checks if line starts with "te"                       | `^te\s+(.+)`                               | Text after "te" (Place of Birth)                      |
| **5: Laatste Woonplaats (Last Residence)** | `laatst gewoond te`                   | Checks if line contains "laatst gewoond te"           | `laatst\s*gewoond te\s+(.+)`               | Text after "laatst gewoond te" (Last Residence)       |
| **6: Campaigns**                           | `4-digit year followed by place name` | Checks if starts with 4 digit and followed by strings | `\b(\d{4})\s+([a-zA-Z]+[\sa-zA-Z]*)`       | 4 digit as Year, string as place                      |
| **7: Military Postings**                   | `more than 1 date pattern`            | Checks if strings has more than one date patterns     | `.*?[0-9]{1,2}\s[A-Z]+[a-z]*\s[1-9]{4}\.*` | String before the date as Context, date as Event Date |


## Extract Information using LLM

```
python Llama.py
```