from dotenv import load_dotenv
import anthropic


load_dotenv()
import os

print(repr(os.environ.get("ANTHROPIC_API_KEY")))
client=anthropic.Anthropic()
response =client.messages.create(model="claude-sonnet-5", max_tokens=200, messages=[{"role": "user", "content": "Hello!"}])
print(response.content[0].text)