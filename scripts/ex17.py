import anthropic
import glob
from dotenv import load_dotenv

load_dotenv()
import os
client=anthropic.Anthropic()

file_paths = [
    "/Users/shaileshdeshpande/Library/CloudStorage/OneDrive-Personal/Self-Training/Claude/Ex10.pdf",
    "/Users/shaileshdeshpande/Library/CloudStorage/OneDrive-Personal/Self-Training/Claude/Ex11.pdf",
    "/Users/shaileshdeshpande/Library/CloudStorage/OneDrive-Personal/Self-Training/Claude/Ex12.pdf",
    "/Users/shaileshdeshpande/Library/CloudStorage/OneDrive-Personal/Self-Training/Claude/Ex13.pdf",
]
file_ids=[]
for path in file_paths:
    with open(path,"rb") as f:
        uploaded = client.beta.files.upload(
        file=(path.split("/")[-1], f, "application/pdf"),
)
file_ids.append(uploaded.id)

content_blocks = [{"type": "text", "text": "Summarize these documents."}]
for fid in file_ids:
    content_blocks.append({
        "type": "document",
        "source": {"type": "file", "file_id": fid}
    })

response = client.beta.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": content_blocks}],
    betas=["files-api-2025-04-14"],
)
print(response)