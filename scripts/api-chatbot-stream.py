import anthropic
from dotenv import load_dotenv

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

    with client.messages.stream(
        model="claude-sonnet-5",
        max_tokens=500,
        thinking={"type":  "disabled"},
        system=f"you are a {persona},  a helpful assistant.",
        messages=messages,

    ) as stream:
        print("Assistant:", end="")
        for text in stream.text_stream:
            print(text, end="")
        print()
        final_message=stream.get_final_message()



    messages.append({"role": "assistant", "content": final_message.content})