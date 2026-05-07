import os.path

import pandas as pd
from diagrams import Diagram, Edge
# 注意：diagrams==0.20.0 仅支持以下两个组件表示数据相关节点，无 Table 类
from diagrams.generic.storage import Storage

from utils.data_path import root_path

save_path = r'data/aitools'
save_path = os.path.join(root_path(), save_path)

# 1. 加载/模拟CSV/Excel数据（避免文件不存在报错，可独立运行）
try:
    df_user = pd.read_csv("用户表.csv", encoding="utf-8")
    df_order = pd.read_csv("订单表.csv", encoding="utf-8")
    df_product = pd.read_csv("商品表.csv", encoding="utf-8")
    df_order_item = pd.read_csv("订单详情表.csv", encoding="utf-8")
except FileNotFoundError:
    # 模拟DataFrame，适配无本地CSV/Excel文件的场景
    df_user = pd.DataFrame({"user_id": [1, 2], "user_name": ["张三", "李四"], "age": [25, 30]})
    df_order = pd.DataFrame({"order_id": [101, 102], "order_no": ["ORD001", "ORD002"], "user_id": [1, 1]})
    df_product = pd.DataFrame({"product_id": [201, 202], "product_name": ["手机", "电脑"], "price": [3999, 5999]})
    df_order_item = pd.DataFrame({"item_id": [301, 302], "order_id": [101, 101], "product_id": [201, 202]})


# 2. 自动提取数据表字段（用于图表展示）
def get_table_fields(df):
    return "\n".join([f"- {col}" for col in df.columns])


user_fields = get_table_fields(df_user)
order_fields = get_table_fields(df_order)
product_fields = get_table_fields(df_product)
order_item_fields = get_table_fields(df_order_item)

# 3. 生成数据表关系模型图（适配 diagrams==0.20.0，无 Table 类）
with Diagram("CSV/Excel业务数据模型图（diagrams==0.20.0）",
             show=True,  # 生成后自动打开图片
             filename="csv_excel_business_model_020",
             outformat="png",  # 仅支持单一格式（旧版本对列表格式支持不佳）
             direction="LR"):  # 左右布局，更清晰展示表关系

    # 方案A：用 Storage 组件表示数据表（推荐，可视化效果更贴合CSV/Excel表）
    user_table = Storage(f"用户表\n(user)\n{user_fields}")
    order_table = Storage(f"订单表\n(order)\n{order_fields}")
    product_table = Storage(f"商品表\n(product)\n{product_fields}")
    order_item_table = Storage(f"订单详情表\n(order_item)\n{order_item_fields}")

    # 定义表之间的业务关联关系（逻辑不变，可视化效果清晰）
    user_table >> Edge(label="一对多\n关联字段：user_id", color="blue", style="dashed") >> order_table
    order_table >> Edge(label="一对多\n关联字段：order_id", color="green", style="solid") >> order_item_table
    product_table >> Edge(label="一对多\n关联字段：product_id", color="red", style="solid") >> order_item_table

print("数据模型图生成完成！文件名为：csv_excel_business_model_020.png")