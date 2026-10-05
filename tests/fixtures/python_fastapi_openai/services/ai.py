import os

from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def ask(text: str) -> str:
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": text}],
    )
    return response.choices[0].message.content or ""
