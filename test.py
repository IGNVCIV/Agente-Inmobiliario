from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("GITHUB_TOKEN"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Hola, ¿funciona la API?"}
    ]
)

print(response.choices[0].message.content)