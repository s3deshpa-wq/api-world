import datetime
import json
from json import JSONDecodeError

from pydantic import BaseModel, ValidationError
import anthropic

from dotenv import load_dotenv


load_dotenv()

client=anthropic.Anthropic()

class Invoice(BaseModel):
    name: str
    amount: float
    date: str
    category: str

example=Invoice(
name="Acme Office Supplies",
    date="2026-03-14",
    amount=249.99,
    category="Office Supplies",
).model_dump_json(indent=2)

prompt_template=f"""Extract invoice details from the text below. Return them as JSON
                 Your output must match this exact shape (this is just an example, not the real data): {example}

Rules: 
- Output ONLY valid JSON matching this shape.
- Do not include any explanation, commentary, or text before or after the JSON.
- "amount" must be a number, not a string.
- "date" must be in YYYY-MM-DD format.

Invoice Text
---

{{invoice_text}}
---
"""
invoice_text = """
Bill To: Priya Sharma
Invoice Date: March 14, 2026
Description: Printer paper, toner cartridges, sticky notes
Total Due: $249.99
"""

filled_prompt=prompt_template.replace("{invoice_text}",invoice_text)

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=300,
    messages=[{"role": "user", "content": filled_prompt}],
)

raw_output=""
for b in response.content:
    if b.type == "text":
        raw_output+=b.text
        break
print("=== Raw model output ===")
print(raw_output)

try:
    data=json.loads(raw_output)
    invoice=Invoice(**data)
    print("\n=== Validated Invoice object ===")
    print(invoice)
except (JSONDecodeError, ValidationError) as e:
    print("\n=== Validation Errors ===\n")
    print(e)