import os
from dotenv import load_dotenv
from promptlayer import PromptLayer
import openai
import json
import datetime

# Set up the PromptLayer client
load_dotenv('.env')
promptlayer_client = PromptLayer(api_key=os.getenv("PROMPTLAYER_API_KEY"))

# Set up the OpenAI client
OpenAI = promptlayer_client.openai.OpenAI
client = OpenAI()

# Set up some constants
MYCHATGPT_PROMPT_NAME = "MyChatGPT" # The name of the prompt template in PromptLayer
USER_CLIENT = "mychatgpt-cli-client"
today_date = datetime.datetime.now().strftime("%Y-%m-%d")
location = "New York City"

### HELPER FUNCTIONS ###

# Calculator tool for the LLM to call
def calculator(function_call):
  parsed_args = json.loads(function_call.arguments)
  return eval(parsed_args['expression'])

# Helper function to parse the LLM response
def parse_llm_response(response_message):
    if response_message.content is not None:
        print(response_message.content)
    if response_message.tool_calls is not None:
        tool_call = response_message.tool_calls[0]
        call_id = tool_call.id
        if tool_call.function.name == "calculator":
            evaluated = calculator(tool_call.function)
            print("$ ", evaluated)
            return {
                "role": "tool",
                "tool_call_id": call_id,
                "content": str(evaluated),
                "name": "calculator",
            }
        else:
            print("Function call not supported")
    return None

# Helper function to track the response in PromptLayer
def track_response_promptlayer(pl_id, input_variables, prompt_name, group_id):
    # Associate the response with the prompt template
    promptlayer_client.track.prompt(
        request_id=pl_id,
        prompt_input_variables=input_variables,
        prompt_name=prompt_name,
    )
    
    # Track some client metadata
    promptlayer_client.track.metadata(
        request_id=pl_id,
        metadata={
            "client": USER_CLIENT,
        }
    )
    
    # Associate the response with a group
    promptlayer_client.track.group(
        request_id=pl_id,
        group_id=group_id,
    )

### MAIN FUNCTION ###

def main():
    user_input = input("Welcome to MyChatGPT! How can I help?\n> ")
    
    # Input variables to inject into the prompt template
    input_variables = {
        "question": user_input,
        "date": today_date,
        "location": location,
    }

    # Fetch the prompt template from PromptLayer and construct it
    mychatgpt_prompt = promptlayer_client.templates.get(MYCHATGPT_PROMPT_NAME, {
        "provider": "openai",
        "input_variables": input_variables,
    })

    # Let's make the first LLM call
    response, pl_id = client.chat.completions.create(
        **mychatgpt_prompt['llm_kwargs'],
        pl_tags=["mychatgpt-dev"],
        return_pl_id=True
    )

    # Track the response in PromptLayer
    pl_group_id = promptlayer_client.group.create()
    track_response_promptlayer(pl_id, input_variables, MYCHATGPT_PROMPT_NAME, pl_group_id)

    # Parse the response and print it
    response_message = response.choices[0].message
    parsed_message = parse_llm_response(response_message)
    
    # Build a list of messages to continue the conversation
    messages = mychatgpt_prompt['llm_kwargs']['messages']
    messages.append(response_message)
    if parsed_message is not None:
        messages.append(parsed_message)

    # Now continue the conversation in a loop...
    while True:
        user_input = input("> ")
        messages.append({"role": "user", "content": user_input})

        # Update the prompt template with the new messages
        mychatgpt_prompt['llm_kwargs']['messages'] = messages
        
        response, pl_id = client.chat.completions.create(
            **mychatgpt_prompt['llm_kwargs'],
            pl_tags=["mychatgpt-dev"],
            return_pl_id=True
        )
        track_response_promptlayer(pl_id, {**input_variables, "question": user_input}, MYCHATGPT_PROMPT_NAME, pl_group_id)

        response_message = response.choices[0].message
        messages.append(response_message)

        parsed_message = parse_llm_response(response_message)
        if parsed_message is not None:
            messages.append(parsed_message)

if __name__ == "__main__":
    main()