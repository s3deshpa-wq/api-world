from dotenv import load_dotenv
import anthropic


load_dotenv()
import os


client=anthropic.Anthropic()
persona='Redevelopment subject matter expert'
messages = []

while True:
    user_input = input(f"You: ")
    print('user input:', user_input)
    if user_input.lower() == 'quit':
        break
    messages.append({"role": "user", "content": user_input})

    response = client.messages.create (
        model="claude-sonnet-5",
        max_tokens=1000,
        system=f"you are a {persona},  a helpful assistant.",
        messages=messages

    )
    reply=next((b.text for b in response.content if b.type == "text"), "None")
    print(f"Assistant: {reply}")
    messages.append({"role": "assistant", "content": reply})