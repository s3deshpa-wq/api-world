from dotenv import load_dotenv
import anthropic
import json

load_dotenv()
client=anthropic.Anthropic()

tools =[{
    "name": "get_weather", "description": "Get the current weather for a given city...",
     "input_schema":
          {"type": "object", "properties": {"city": {"type": "string", "description": "The city name e.g 'Rome'"}
                                            },
            "required": ["city"],
           },
      },
{
    "name" : "calculate", "description": "Calculate a mathematical expression",
    "input_schema":
          {"type": "object", "properties": {"expression": {"type": "string", "description": "The mathematical expression e.g '2+2'"}
                                            },
            "required": ["expression"],
           },
      },
{
    "name" : "search_notes", "description": "Search user's personal notes for a keyword and return matching snippets",
          "input_schema":
          {"type": "object", "properties": {"query": {"type": "string", "description": "The keyword or a phrase to search for in notes"}
                                                            },
            "required": ["query"],
           },
      },

]


def get_weather(city: str) -> dict:
    fake_data = {
        "tokyo": {"temperature_c": 27, "condition": "Partly cloudy", "humidity": 62},
        "london": {"temperature_c": 18, "condition": "Light rain", "humidity": 80},
        "new york": {"temperature_c": 24, "condition": "Sunny", "humidity": 45},
        "mumbai": {"temperature_c": 31, "condition": "Humid, scattered showers", "humidity": 78},
    }
    default = {"temperature_c": 21, "condition": "Clear skies", "humidity": 50}
    result = fake_data.get(city.strip().lower(), default)
    return {"city": city, **result}
def calculate(city: str) -> dict:
    fake_data = {
        "tokyo": {"temperature_c": 27, "condition": "Partly cloudy", "humidity": 62},
        "london": {"temperature_c": 18, "condition": "Light rain", "humidity": 80},
        "new york": {"temperature_c": 24, "condition": "Sunny", "humidity": 45},
        "mumbai": {"temperature_c": 31, "condition": "Humid, scattered showers", "humidity": 78},
    }
    default = {"temperature_c": 21, "condition": "Clear skies", "humidity": 50}
    result = fake_data.get(city.strip().lower(), default)
    return {"city": city, **result}
def search_notes(city: str) -> dict:
    fake_data = {
        "tokyo": {"temperature_c": 27, "condition": "Partly cloudy", "humidity": 62},
        "london": {"temperature_c": 18, "condition": "Light rain", "humidity": 80},
        "new york": {"temperature_c": 24, "condition": "Sunny", "humidity": 45},
        "mumbai": {"temperature_c": 31, "condition": "Humid, scattered showers", "humidity": 78},
    }
    default = {"temperature_c": 21, "condition": "Clear skies", "humidity": 50}
    result = fake_data.get(city.strip().lower(), default)
    return {"city": city, **result}
messages=[{"role": "user", "content" : "What is the weather in Mumbai?"},]
response=client.messages.create(model="claude-sonnet-5", max_tokens=1000,  tools=[weather_tool, calculate_tool, search_notes_tool],
                            messages=[{"role": "user", "content": "What's the weather in london, and what's 45 times 12?"}],
                                )

if response.stop_reason=="tool_use":
    tool_use_block=next(b for b in response.content if b.type=="tool_use")
    city=tool_use_block.input["city"]
    weather_result=get_weather(city)

messages.append({"role": "assistant", "content": response.content})
messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use_block.id,
                                             "content": json.dumps(weather_result)}],
                })

final_response=client.messages.create(model="claude-sonnet-5", max_tokens=1000, tools=[weather_tool], messages=messages)
print("stop_reason:", final_response.stop_reason)
for b in final_response.content:
    if b.type=="text":
        print(b.text)

