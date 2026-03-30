import os
from openai import OpenAI

# 请确保您已将 API Key 存储在环境变量 ARK_API_KEY 中
# 初始化Ark客户端，从环境变量中读取您的API Key
client = OpenAI(
    # 此为默认路径，您可根据业务所在地域进行配置
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 从环境变量中获取您的 API Key。此为默认方式，您可根据需要进行修改
    api_key='39d1f61c-6a58-44e4-8d68-51bd4c31185d',
    # api_key=os.environ.get("ARK_API_KEY"),
)

response = client.chat.completions.create(
    # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
    model="doubao-seed-2-0-pro-260215",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://ts3.tc.mm.bing.net/th/id/OIP-C.lqbXy2awKuipS-0qgaRruAAAAA?pid=ImgDet&w=60&h"
                               "=60&c=7&dpr=1.3&rs=1&o=7&rm=3 "
                    },
                },
                {"type": "text", "text": "这是啥动物"},
            ],
        }
    ],
)

print(response.choices[0])