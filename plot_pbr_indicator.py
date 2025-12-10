
import datetime
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import timedelta
from collections import defaultdict

def pick_first_workday_each_week(data_dict):
    """
    從輸入字典中，依照每週挑出第一個有效工作日。
    優先順序：星期一 -> 星期二 -> ... -> 星期日
    """
    # 將 key 轉成 datetime.date
    parsed = {datetime.strptime(k, "%Y%m%d").date(): v for k, v in data_dict.items()}

    # 依照週分組 (year, week_number)
    weeks = defaultdict(list)
    for d in parsed.keys():
        year, week_num, _ = d.isocalendar()  # isocalendar: (year, week, weekday)
        weeks[(year, week_num)].append(d)

    result = {}
    # 每週挑出第一個有效工作日
    for (year, week_num), days in weeks.items():
        days_sorted = sorted(days)
        # 按照星期一到星期日的優先順序
        for wd in range(7):  # 0=Monday ... 6=Sunday
            for d in days_sorted:
                if d.weekday() == wd:
                    result[d.strftime("%Y%m%d")] = parsed[d]
                    break
            else:
                continue
            break

    return result

def calc_indicator_pandas(data_dict, close_prices, length=20, band_range=2):
    """
    data_dict: pick_first_workday_each_week 回傳的字典 { "YYYYMMDD": value1 }
    close_prices: 台指期收盤價字典 { "YYYYMMDD": 收盤價 }
    length: 布林通道天數
    band_range: 上下寬度
    """

    # 建立 DataFrame
    df1 = pd.DataFrame(list(data_dict.items()), columns=["date", "value1"])
    df2 = pd.DataFrame(list(close_prices.items()), columns=["date", "close"])

    # 合併
    df = pd.merge(df1, df2, on="date", how="inner")
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df = df.sort_values("date").reset_index(drop=True)

    # value1 的 3 日平均
    df["value1_ma"] = df["value1"].rolling(3).mean()
    df["value1_std"] = df["value1"].rolling(length).std()
    df["up1"] = df["value1_ma"].rolling(length).mean() + band_range * df["value1_std"]
    df["down1"] = df["value1_ma"].rolling(length).mean() - band_range * df["value1_std"]
    df["tsepbr_pb"] = (df["value1_ma"] - df["down1"]) * 100 / (df["up1"] - df["down1"])

    # 收盤價的 3 日平均
    df["close_ma"] = df["close"].rolling(3).mean()
    df["close_std"] = df["close"].rolling(length).std()
    df["up"] = df["close_ma"].rolling(length).mean() + band_range * df["close_std"]
    df["down"] = df["close_ma"].rolling(length).mean() - band_range * df["close_std"]
    df["c_pb"] = (df["close_ma"] - df["down"]) * 100 / (df["up"] - df["down"])

    # value3 = tsepbr_pb - c_pb
    df["value3"] = df["tsepbr_pb"] - df["c_pb"]

    # 移除 NaN，只保留 close 和 value3 都有值的筆數
    df = df.dropna(subset=["close", "value3"]).reset_index(drop=True)

    return df

def get_stock_close_batch(date_keys, stock_id):
    """
    批次取得台灣個股收盤價
    date_keys: list of "YYYYMMDD" 字串 (例如 list(w_cache.keys()))
    stock_id: 股票代號 (數字，例如 2330, 2317)
    回傳: { "YYYYMMDD": Close }
    """
    # 股票代號轉成 Yahoo Finance 格式
    if stock_id == "^TWII":
        ticker_symbol = stock_id
    else:
        ticker_symbol = f"{stock_id}.TW"

    # 轉成 datetime.date
    dates = [datetime.strptime(d, "%Y%m%d").date() for d in date_keys]
    start = min(dates)
    end = max(dates) + timedelta(days=1)

    # 抓取個股資料
    stock = yf.Ticker(ticker_symbol)
    hist = stock.history(start=start, end=end)

    result = {}
    for d in dates:
        d_str = d.strftime("%Y%m%d")
        try:
            close_price = hist.loc[d.strftime("%Y-%m-%d")]["Close"]
            result[d_str] = float(close_price)
        except KeyError:
            result[d_str] = None  # 若該日沒有資料，填 None
    return result

def plot_close_and_value3(df_result, code, text="Day"):
    """
    繪製上下兩個子圖：
    上圖：收盤價走勢 (高度 2)
    下圖：PB-C 指標 (value3) 走勢 (高度 1)
    df_result: pandas DataFrame，需包含 "date", "close", "value3" 欄位
    """
    fig, axes = plt.subplots(
        2, 1, figsize=(10, 5), sharex=True,
        gridspec_kw={"height_ratios": [2, 1]}  # 上圖:下圖 = 2:1
    )

    # 上圖：收盤價
    axes[0].tick_params(labelbottom=True)  # 開啟上圖的 x 軸標籤
    axes[0].plot(df_result["date"], df_result["close"], marker=".", color="blue", label="Close Price")
    axes[0].set_title(f"{code} {text} Closing price trend")
    axes[0].set_xlabel("Data")
    axes[0].set_ylabel("Close")
    axes[0].legend()
    axes[0].grid(True)

    # 下圖：value3
    axes[1].plot(df_result["date"], df_result["value3"], marker=".", color="orange", label="PB-C")
    axes[1].set_title(f"{code} PB-C {text} Indicator Trends")
    axes[1].set_xlabel("PB-C")
    axes[1].set_ylabel("PB-C Value")
    axes[1].legend()
    axes[1].grid(True)

    plt.tight_layout()
    plt.show()

def week_plot(cache, show_length=0):
    code = input("請輸入目標股票代號 ")
    w_cache = pick_first_workday_each_week(cache)
    if show_length == 0:
        w_cache2 = w_cache
    else:
        w_cache2 = dict(list(w_cache.items())[-show_length:])

    close_prices = get_stock_close_batch(w_cache2, code)
    df_result = calc_indicator_pandas(w_cache2, close_prices, length=20, band_range=2)
    plot_close_and_value3(df_result, code, "Week")

def day_plot(cache, show_length=0):
    code = input("請輸入目標股票代號 ")
    if show_length == 0:
        cache2 = cache
    else:
        cache2 = dict(list(cache.items())[-show_length:])

    close_prices = get_stock_close_batch(cache2, code)
    df_result = calc_indicator_pandas(cache2, close_prices, length=20, band_range=2)
    plot_close_and_value3(df_result, code, "Day")
