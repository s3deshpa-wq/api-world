"""
Traced agent loop — watch `history` grow, one step at a time.

Run:  python agent_traced.py
Needs: pip install anthropic python-dotenv   (and ANTHROPIC_API_KEY in a .env file)

Every mutation of self.history is printed, so you can see exactly what gets
sent to the API on each pass of the loop.
"""
# I am testing branch feature in git
#

from dotenv import load_dotenv
import anthropic

# ============================================================================
# TOOLS — plain Python functions. Claude can never run these itself.
# ============================================================================

def get_weather(city: str) -> str:
    return f"It's sunny in {city}"

def add_numbers(num1: float, num2: float) -> float:
    return num1 + num2

def get_time(city: str) -> str:
    return f"It's 3:00 PM in {city}"

def calculate_discount(price: float, percent: float = 10.0) -> float:
    return price * percent / 100

tools = {
    "get_weather": get_weather,
    "add_numbers": add_numbers,
    "get_time": get_time,
    "calculate_discount": calculate_discount,
}

# ============================================================================
# SCHEMA — this is ALL Claude sees. Your Python defaults are invisible to it,
# so anything about optionality must be stated in the description.
# ============================================================================

tool_schema = [
    {
        "name": "get_weather",
        "description": "Get weather for a particular city",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "city name"}},
            "required": ["city"],
        },
    },
    {
        "name": "add_numbers",
        "description": "Add 2 numbers",
        "input_schema": {
            "type": "object",
            "properties": {
                "num1": {"type": "number", "description": "Number 1"},
                "num2": {"type": "number", "description": "Number 2"},
            },
            "required": ["num1", "num2"],
        },
    },
    {
        "name": "get_time",
        "description": "Get time for a particular city",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "city name"}},
            "required": ["city"],
        },
    },
    {
        "name": "calculate_discount",
        "description": (
            "Calculate the discount amount on a price. If the user does not "
            "specify a discount percentage, omit the 'percent' argument "
            "entirely and a default of 10% will be applied."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "description": "Price"},
                "percent": {
                    "type": "number",
                    "description": "Discount percent. Optional — defaults to 10 if omitted.",
                    "default": 10.0,
                },
            },
            "required": ["price"],
        },
    },
]

# ============================================================================
# PRETTY PRINTING — so history is readable instead of a wall of base64
# ============================================================================

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"

def banner(text):
    print(f"\n{BOLD}{'=' * 70}\n{text}\n{'=' * 70}{RESET}")

def describe_block(b):
    """One readable line per content block."""
    if isinstance(b, dict):                       # blocks we constructed
        if b.get("type") == "tool_result":
            return f"tool_result  (for {b['tool_use_id']})  ->  {b['content']}"
        return f"{b.get('type')}  {b}"
    # blocks the SDK gave us
    if b.type == "text":
        return f'text         "{b.text}"'
    if b.type == "thinking":
        return f"thinking     <{len(b.thinking)} chars, signature hidden>"
    if b.type == "tool_use":
        return f"tool_use     {b.name}({b.input})   id={b.id}"
    return f"{b.type}"

def show_history(history, label):
    print(f"\n{DIM}--- history after {label} — {len(history)} message(s) ---{RESET}")
    for i, msg in enumerate(history):
        content = msg["content"]
        if isinstance(content, str):
            print(f"  [{i}] {msg['role']:<9} : \"{content}\"")
        else:
            print(f"  [{i}] {msg['role']:<9} :")
            for b in content:
                print(f"          {describe_block(b)}")
    print(f"{DIM}{'-' * 60}{RESET}")


# ============================================================================
# THE AGENT
# ============================================================================

class Agent:
    def __init__(self, name, tools):
        self.name = name
        self.tools = tools
        self.history = []      # THE conversation. The API remembers nothing.
        self.tool_log = []     # separate audit trail, not sent to the API

    def call_tool(self, tool_name, **kwargs):
        if tool_name not in self.tools:
            return f"Error: unknown tool '{tool_name}'"
        try:
            result = self.tools[tool_name](**kwargs)
            self.tool_log.append((tool_name, kwargs, result))
            return result
        except Exception as e:
            return f"Error calling {tool_name}: {e}"

    def ask_claude(self, user_question, max_turns=10):

        # -- STEP 1 -----------------------------------------------------
        # Add the human's question to the transcript.
        self.history.append({"role": "user", "content": user_question})
        banner("STEP 1 — append the user's question")
        show_history(self.history, "step 1")

        for turn in range(1, max_turns + 1):

            # -- STEP 2 -------------------------------------------------
            # Send the ENTIRE transcript. Not just the last message —
            # the API is stateless and has no memory of prior calls.
            banner(f"STEP 2 — loop pass {turn}: sending all {len(self.history)} message(s) to the API")
            resp = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=1024,
                tools=tool_schema,
                messages=self.history,
            )
            print(f"  Claude replied with {len(resp.content)} block(s):")
            for b in resp.content:
                print(f"      {describe_block(b)}")
            print(f"  {BOLD}stop_reason = {resp.stop_reason!r}{RESET}")

            # -- STEP 3 -------------------------------------------------
            # Append Claude's reply UNMODIFIED. The tool_use ids and the
            # thinking signatures must survive intact or the next call fails.
            self.history.append({"role": "assistant", "content": resp.content})
            banner("STEP 3 — append Claude's reply verbatim")
            show_history(self.history, "step 3")

            # -- STEP 4 -------------------------------------------------
            # Is Claude done, or is it blocked waiting on us?
            if resp.stop_reason != "tool_use":
                banner("STEP 4 — stop_reason is not 'tool_use' → we're done")
                text = "".join(b.text for b in resp.content if b.type == "text")
                print(f"\n{BOLD}ANSWER:{RESET} {text or '[no text in response]'}\n")
                if resp.stop_reason == "max_tokens":
                    print("  (warning: hit max_tokens, answer may be truncated)")
                return text

            banner("STEP 4 — stop_reason IS 'tool_use' → Claude is blocked, keep looping")

            # -- STEP 5 -------------------------------------------------
            # Run each requested tool. Claude may request several at once.
            banner("STEP 5 — run the requested tool(s)")
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    print(f"  calling: {b.name}(**{b.input})")
                    output = self.call_tool(b.name, **b.input)
                    print(f"  returned: {output!r}")
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": b.id,     # ties this answer to that request
                        "content": str(output),  # must be a string
                    })

            # -- STEP 6 -------------------------------------------------
            # Send results back as a USER turn. "user" = our side of the wire,
            # whether a human typed it or a function computed it.
            self.history.append({"role": "user", "content": results})
            banner("STEP 6 — append tool results as a 'user' turn, then loop back to STEP 2")
            show_history(self.history, "step 6")

        print("Hit max_turns without a final answer.")
        return None


# ============================================================================
# MAIN
# ============================================================================

load_dotenv()
client = anthropic.Anthropic()
agent = Agent("Jarvis", tools)

print(__doc__)
print("Try:  What's the discount on 6000?")
print("      What's the weather and time in Mumbai?      <- two tools at once")
print("      Add 5 and 7, then tell me the weather there <- multiple loop passes")
print("Type 'quit' to exit, 'history' to dump the transcript.\n")

while True:
    user_question = input("\n>>> ")
    if user_question.strip().lower() == "quit":
        break
    if user_question.strip().lower() == "history":
        show_history(agent.history, "manual dump")
        continue
    if not user_question.strip():
        continue
    agent.ask_claude(user_question)

