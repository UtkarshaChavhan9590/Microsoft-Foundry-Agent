import json

from azure.ai.agents.models import FunctionTool


def get_current_weather(location: str) -> str:
    """Get the current weather in a given location"""
    # In a real implementation, this would call a weather API.
    return json.dumps({
        "location": location,
        "temperature": "20°C",
        "condition": "Sunny"
    })

weather_functions = [get_current_weather]

weather_tool = FunctionTool(functions=weather_functions)