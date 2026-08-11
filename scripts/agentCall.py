# Testing ruff
from dotenv import load_dotenv
import anthropic
import asyncio
from dotenv import load_dotenv


#********************************************************************************
# ** Defining tool functionality **

async def get_weather(city: str) -> str:
        """Returns fake weather for a city."""
        await asyncio.sleep(1)
        return f"It's sunny in {city}"

def add_numbers(num1: float, num2: float) -> float:
        """Adds two numbers."""
        return num1 + num2

def get_time(city: str) -> str:
        """Returns a fake time for a city."""
        return f"It's 3:00 PM in {city}"
def calculate_discount(price:float, percent=10.0) -> float:
        """Calculate the discount on the price. If the discount % is not provided, the default percent is 10. """
        return price * percent / 100

tools = {
        "get_weather": get_weather,
        "add_numbers": add_numbers,
        "get_time": get_time,
        "calculate_discount": calculate_discount
    }
class Agent:
      def __init__(self, name, tools):
        self.name = name
        self.tools = tools
        self.history = []
      #def ask_claude(self, user_question:str):
      async def ask_claude(self, user_question):
              self.history.append({"role": "user", "content": user_question})
              while True:
                  resp = client.messages.create(
                      model="claude-sonnet-5", max_tokens=1024,
                      tools=tool_schema, messages=self.history,
                  )
                  self.history.append({"role": "assistant", "content": resp.content})
                  if resp.stop_reason != "tool_use":
                      print("".join(b.text for b in resp.content if b.type == "text"))
                      return
                  tool_calls = [b for b in resp.content if b.type == "tool_use"]
                  tool_results = await asyncio.gather(
                      *(self.call_tool(b.name, **b.input) for b in tool_calls)
                  )
                  results = [
                      {"type": "tool_result", "tool_use_id": b.id, "content": str(r)}
                      for b, r in zip(tool_calls, tool_results)
                  ]
                  self.history.append({"role": "user", "content": results})

#Calling the appropriate tool

      async def call_tool(self, tool_name, **kwargs):
        if tool_name not in self.tools:
            return f"Error: unknown tool '{tool_name}'"
        try:
            result = self.tools[tool_name](**kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            return f"Error calling {tool_name}: {e}"

 #    def run(self, plan):
 #       plan: list of dicts like {'tool': 'get_weather', 'args': {'city': 'Mumbai'}}
 #       for step in plan:
 #           result = self.call_tool(step["tool"], **step["args"])
 #           print(f"[{self.name}] {step['tool']}({step['args']}) -> {result}")
#********************************************************
#** Defining tool registry


tool_schema = [
    {
        "name": "get_weather",
        "description": "Get weather for a particular city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "city name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "add_numbers",
        "description": "Add 2 numbers",
        "input_schema": {
            "type": "object",
            "properties": {
                "num1": {"type": "number", "description": "Number 1"},
                "num2": {"type": "number", "description": "Number 2"}
            },
            "required": ["num1", "num2"]
        }
    },
    {
        "name": "get_time",
        "description": "Get time for a particular city",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "city name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculate_discount",
        "description": "Calculate the discount on the price. Default to 10 if none is given ",
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "description": "Price"},
                "percent": {"type": "number", "description": "Discount Default to 10 if none is given", "default": 10}
            },
            "required": ["price"]
        }
    },
]




#********************************************************************************
#** Loading API key and creation of Anthropic Client **
load_dotenv()

client=anthropic.Anthropic()
agent= Agent("Jarvis", tools)

while True:
    user_question=input("Enter a message....")
    print(user_question)
    if user_question=="quit":
        break
    else:
        asyncio.run(agent.ask_claude(user_question))



