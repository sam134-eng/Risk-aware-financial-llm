import os
from dotenv import load_dotenv
from openai import OpenAI
# Load the API key now from .env file
load_dotenv()
#Create OpenAI client
client= OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
# Ask user for finance related question
question=input("Ask a financial question :")
# Send the question to llm
response = client.chat.completions.create(
    model = "gpt-5.4-mini",
    messages=[
        {"role" : "system",
        "content":(
            "You are a financial assistant."
            "Answer finance related questions logically"
             "For math or calculation questions:\n"
                "1. State the formula clearly.\n"
                "2. Walk through the numbers step by step.\n"
                "3. State the final figure directly.\n"
                "Do not invent facts. "
                "If information is missing or uncertain, say so clearly."
        ) },
        {"role" : "user",
         "content": question
         }
    ]
)
answer=response.choices[0].message.content
print("\nFinancial Assitant:") 
print(answer)
