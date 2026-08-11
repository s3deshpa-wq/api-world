import anthropic

from dotenv import load_dotenv

load_dotenv()

client=anthropic.Anthropic()


# Step 1 & 2: Fixed instructions with placeholder variables
prompt_template = """You are summarizing meeting notes for internal use.

Tone: {{tone}}
Length: {{length}}
Audience: {{audience}}

Meeting notes:
---
The team discussed the Q3 roadmap. Marketing wants to launch the new
campaign by August 15th. Engineering flagged a two-week delay due to
a pending API integration. Sales asked for updated pricing sheets by
next Friday. Action items were assigned to Priya (roadmap doc),
Jordan (API fix timeline), and Sam (pricing sheets).
---

Write the summary now, following the tone, length, and audience above.
"""

# Step 3: Three genuinely different variable combinations
variants = [
    {
        "tone": "formal",
        "length": "3-4 sentences, executive summary style",
        "audience": "senior leadership who did not attend the meeting",
    },
    {
        "tone": "casual",
        "length": "one short paragraph",
        "audience": "a teammate who missed the meeting",
    },
    {
        "tone": "urgent and action-focused",
        "length": "a bulleted list of action items only",
        "audience": "the people directly responsible for follow-up tasks",
    },
]

# Step 4: Fill placeholders, run each through Claude, compare
for i, v in enumerate(variants, start=1):
    filled_prompt = prompt_template
    for key, value in v.items():
        filled_prompt = filled_prompt.replace("{{" + key + "}}", value)

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        messages=[{"role": "user", "content": filled_prompt}],
    )

    print(f"\n=== Variant {i}: {v} ===")
    for block in response.content:
        if block.type == "text":
            print(block.text)
            break
