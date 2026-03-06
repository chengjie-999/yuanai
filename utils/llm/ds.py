from openai import OpenAI


def dk():
    DEEPSEEK_API_KEY = 'sk-d0b3bf178759483e8e40020f5d00ee02'

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com")

    return client


if __name__ == '__main__':
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": f"介绍一下自己"},
    ]
    dk = dk()
    response1 = dk.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        # tools=tools
        # stream=True
    )
    print(response1.choices[0].message.content)
