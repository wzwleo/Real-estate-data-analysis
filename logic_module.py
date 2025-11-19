import pandas as pd

def run_analysis(user_input):
    df = pd.read_csv("house.csv")
    price = df["price"].mean()

    return f"平均價格：{price}"
result = run_analysis("台中")
