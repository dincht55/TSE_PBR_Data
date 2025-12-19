
import requests
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

class PlotPBDif:
    def __init__(self):
        pass

    def calculate_bollinger(self, series, window=20, num_std=2):
        """計算布林通道上下軌"""
        ma = series.rolling(window).mean()
        std = series.rolling(window).std()
        upper = ma + num_std * std
        lower = ma - num_std * std
        return upper, lower

    def calculate_indicator(self, df):
        df["本益比"] = pd.to_numeric(df["本益比"], errors='coerce')
        df["殖利率(%)"] = pd.to_numeric(df["殖利率(%)"], errors='coerce')

        # 5日平均
        pe_ma5 = df["本益比"].rolling(5).mean()
        dy_ma5 = df["殖利率(%)"].rolling(5).mean()

        # 本益比布林通道
        pe_up, pe_down = self.calculate_bollinger(pe_ma5, 20, 2)
        pe_percent_b = ((pe_ma5 - pe_down) * 100 / (pe_up - pe_down)).fillna(0)

        # 殖利率布林通道
        dy_up, dy_down = self.calculate_bollinger(dy_ma5, 20, 2)
        dy_percent_b = ((dy_ma5 - dy_down) * 100 / (dy_up - dy_down)).fillna(0)

        # %b_DIF
        percent_b_diff = dy_percent_b - pe_percent_b

        # 加入到 DataFrame
        df["PE_MA5"] = pe_ma5
        df["DY_MA5"] = dy_ma5
        df["PE_percent_b"] = pe_percent_b
        df["DY_percent_b"] = dy_percent_b
        df["percent_b_diff"] = percent_b_diff

        # 刪除含有 NaN 的列及計算欄位為 0 的列
        df = df.dropna().reset_index(drop=True)
        df = df[~((df["PE_percent_b"] == 0) |
            (df["DY_percent_b"] == 0) |
            (df["percent_b_diff"] == 0))].reset_index(drop=True)

        return df

    def get_twse_bwibbu(self, stock_no, start_month):
        today = datetime.today().strftime("%Y%m%d")
        start = pd.Period(str(start_month)[:6], freq="M")
        end = pd.Period(today[:6], freq="M")

        all_data = []
        day = 1
        for period in pd.period_range(start, end, freq="M"):
            while 1:
                date = f"{period.year}{period.month:02d}{day:02d}"
                url = f"https://www.twse.com.tw//exchangeReport//BWIBBU?date={date}&stockNo={stock_no}&response=json"
                res = requests.get(url)
                if res.status_code == 200:
                    try:
                        data = res.json()
                        df = pd.DataFrame(data["data"], columns=data["fields"])
                        all_data.append(df)
                        print(f"{date} 下載完成.")
                        day = 1
                        break
                    except KeyError:
                        day += 1
                        if day > 15:
                            day = 1
                            break
                    except ValueError:
                        print("⚠️ 回傳不是 JSON，可能是查無資料或 API 格式改變")
                        print(res.text)
                        break
                else:
                    print("HTTP 錯誤:", res.status_code)
                    break

        if all_data:
            merged_df = pd.concat(all_data, ignore_index=True)
            # 民國年轉西元年
            def convert_twse_date(date_str):
                parts = date_str.replace("年","/").replace("月","/").replace("日","").split("/")
                year = int(parts[0]) + 1911
                month = int(parts[1])
                day = int(parts[2])
                return f"{year}{month:02d}{day:02d}"

            merged_df["日期"] = merged_df["日期"].apply(convert_twse_date)
            merged_df = merged_df.sort_values("日期").reset_index(drop=True)
            return merged_df
        else:
            return None

    def get_stock_close_batch(self, date_keys, stock_id):
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
        print(dates)
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

    def plot_close_and_percent_b_diff(self, df, stock):
        """
        繪製上下兩個子圖：
        上圖顯示 Close (股價)
        下圖顯示 percent_b_diff (%b_DIF)
        """
        # 確保日期是 datetime 格式
        if not pd.api.types.is_datetime64_any_dtype(df["日期"]):
            df["日期"] = pd.to_datetime(df["日期"])

        # 設定高度比例，上圖:下圖 = 1.5:1
        fig, axes = plt.subplots(
            2, 1, figsize=(10, 5), sharex=True,
            gridspec_kw={'height_ratios': [1.5, 1]}
        )

        # 上圖：Close
        axes[0].plot(df["日期"], df["Close"], marker=".", linestyle="-", color="green", label="Close")
        axes[0].set_title(f"{stock} Close", fontsize=12)
        axes[0].set_ylabel("Close", fontsize=10)
        axes[0].grid(True, linestyle="--", alpha=0.7)
        axes[0].legend()

        # 下圖：percent_b_diff
        axes[1].plot(df["日期"], df["percent_b_diff"], marker=".", linestyle="-", color="blue", label="%b_DIF")
        axes[1].set_title("percent_b_diff", fontsize=12)
        axes[1].set_xlabel("Date", fontsize=10)
        axes[1].set_ylabel("percent_b_diff", fontsize=10)
        axes[1].grid(True, linestyle="--", alpha=0.7)
        axes[1].legend()

        plt.tight_layout()
        plt.show()


    def main(self, stock, start_month):
        df = self.get_twse_bwibbu(stock_no=stock, start_month=start_month)
        tdf = self.calculate_indicator(df)
        re = self.get_stock_close_batch(tdf.日期, stock)

        # 合拼資料
        df_dict = pd.DataFrame(list(re.items()), columns=["日期", "Close"])
        merged_df = pd.merge(tdf, df_dict, on="日期", how="left")
        self.plot_close_and_percent_b_diff(merged_df, stock)

        return merged_df
