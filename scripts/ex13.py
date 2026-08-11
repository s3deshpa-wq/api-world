"""Testing ruff"""

from dotenv import load_dotenv
import anthropic
import json

load_dotenv()
client=anthropic.Anthropic()

weather_tool = {
    "name": "weather", "description": "Get the current weather for a given city...",
     "input_schema":
          {"type": "object", "properties": {"city": {"type": "string", "description": "..."}
                                            },
            "required": ["city"],
           },
      }
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

messages=[{"role": "user", "content" : "What is the weather in Mumbai?"},]
response=client.messages.create(model="claude-sonnet-5", max_tokens=1000,  tools=[weather_tool],
                            messages=[{"role": "user", "content": "What's the weather in Mumbai?"}],
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

