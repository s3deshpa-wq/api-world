import base64

from dotenv import load_dotenv
import anthropic
from pathlib import Path

SCRIPT_DIR=Path(__file__).resolve().parent
image_path=SCRIPT_DIR.parent / "KCHS Logo.jpg"
pdf_path=SCRIPT_DIR.parent / "Financial_Advisor_Interview_QA.pdf"

load_dotenv()
client=anthropic.Anthropic()

with open(image_path, "rb") as f:
   data = f.read()
   image_b64 = base64.b64encode(data).decode("utf-8")

with open(pdf_path, "rb") as f:
   data = f.read()
   pdf_b64 = base64.b64encode(data).decode("utf-8")
image_MIME = "image/jpeg"
pdf_MIME = "application/pdf"

content=[
   {"type": "image", "source": {"type": "base64", "media_type": image_MIME, "data": image_b64}},
   {"type" : "document", "source": {"type": "base64", "media_type": pdf_MIME, "data": pdf_b64}},
   {"type": "text", "text": "Is KCHS logo present in the PDF document?"}
 ]
response = client.messages.create (
        model="claude-sonnet-5",
        max_tokens=1000,
        system=f"you are a helpful assistant.",
        messages=[{"role": "user", "content": content}])
reply=next((b.text for b in response.content if b.type == "text"), "None")
print(f"Assistant: {reply}")

