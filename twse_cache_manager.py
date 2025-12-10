
import os
import json
import time
import calendar
import requests
import subprocess
import pandas as pd
from io import StringIO
from collections import defaultdict
from datetime import datetime, timedelta

class TWSECacheManager:
    def __init__(self, name, email, pat, branch="main"):
        self.branch = branch
        self.user_name = name
        self.user_email = email
        self.pat = pat
        self.cache = None

    # 取得本地 json
    def get_json(self, json_name):
        try:
            with open(json_name, "r", encoding="utf-8") as f:
                cache = json.load(f)
                if cache is None: cache = {}
            return cache

        except FileNotFoundError:
            print(f"找不到檔案 {json_name}")
            return {}
        except json.JSONDecodeError:
            print(f"{json_name} 格式錯誤")
            return {}

    # 更新並排序本地 json
    def update_json(self, json_name, json_data):
        sort_data = dict(sorted(json_data.items(), key=lambda x: x[0]))

        # 存回 JSON
        with open(json_name, "w", encoding="utf-8") as f:
            json.dump(sort_data, f, ensure_ascii=False, indent=4)

        print(f"已依日期排序並更新 {json_name}")

    def git_init(self):
        """初始化 Git repo，若不存在則 clone，存在則 pull"""
        subprocess.run(["git", "config", "--global", "user.name", self.user_name])
        subprocess.run(["git", "config", "--global", "user.email", self.user_email])
        repo_url = f"https://{self.user_name}:{self.pat}@github.com/{self.user_name}/TSE_PBR_Data.git"

        if not os.path.exists(".git"):
            # 建議 clone 到新資料夾 repo
            try:
                subprocess.run(["git", "clone", repo_url, "repo"], check=True)
                os.chdir("repo")
                print(f"✅ 已 clone 遠端 repo TSE_PBR_Data.git 到本地 repo/")
            except subprocess.CalledProcessError as e:
                print("❌ clone 失敗，請檢查分支名稱或 Token")
                print(e.stderr)
        else:
            # 已存在 → 確保遠端正確，然後 pull
            subprocess.run(["git", "remote", "remove", "origin"], capture_output=True)
            subprocess.run(["git", "remote", "add", "origin", repo_url])
            subprocess.run(["git", "pull", "origin", self.branch], check=True)
            print(f"🔄 已更新本地 repo，分支 {self.branch}")

    # 上傳或更新檔案
    def git_commit_and_push(self, file_path, commit_msg):
        """提交檔案並推送到 GitHub"""
        # 如果檔案不在當前目錄，嘗試加上 repo/
        if not os.path.exists(file_path):
            repo_path = os.path.join("repo", file_path)
            if os.path.exists(repo_path):
                file_path = repo_path
            else:
                print(f"檔案 {file_path} 不存在，無法提交")
                return

        subprocess.run(["git", "add", file_path])

        # 避免空 commit
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode == 0:
            print("沒有變更需要提交")
            return

        subprocess.run(["git", "commit", "-m", commit_msg])
        subprocess.run(["git", "push", "origin", self.branch])
        print(f"已提交並推送 {file_path} 到 {self.branch}")

    # 刪除檔案
    def git_delete_file(self, file_path, commit_msg="刪除檔案"):
        """刪除檔案並推送到 GitHub"""
        # 如果檔案不在當前目錄，嘗試加上 repo/
        if not os.path.exists(file_path):
            repo_path = os.path.join("repo", file_path)
            if os.path.exists(repo_path):
                file_path = repo_path
            else:
                print(f"檔案 {file_path} 不存在，跳過刪除")
                return

        try:
            subprocess.run(["git", "rm", file_path], check=True)
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            subprocess.run(["git", "push", "origin", self.branch], check=True)
            print(f"已刪除 {file_path} 並推送到 {self.branch}")
        except subprocess.CalledProcessError:
            os.remove(file_path)
            print(f"檔案 {file_path} 不在 Git 追蹤中，已刪除本地檔案")

    # 下載最新版本
    def git_download(self):
        """從 GitHub 拉取最新版本"""
        try:
            subprocess.run(["git", "pull", "origin", self.branch])
            print(f"已下載最新版本 {self.branch}")
        except subprocess.CalledProcessError:
            if os.path.exists("repo") and not os.path.exists(".git"):
                os.chdir("repo")

            try:
                subprocess.run(["git", "pull", "origin", self.branch], check=True)
                print(f"✅ 已下載最新版本 {self.branch}")
            except subprocess.CalledProcessError as e:
                print("❌ 下載失敗，請檢查分支或遠端設定")
                print(e.stderr)

    # cache 初始化
    def cache_init(self):
        self.git_init()
        try:
            self.git_download()
            return self.get_json('json_data.json')
        except:
            print('沒有檔案下載')
            return {}

    def show_cache(self, ):
        cache = self.cache_init()
        print(f'現有 Cache 長度: {len(cache)}')
        self.show_Inf(cache, {"20251201": 949})

# ------------------------ download funcation ------------------------
    def download_twse_csv(self, date_str: str) -> dict[str, int]:
        """
        下載台灣證交所指定日期的 BWIBBU CSV 檔，並轉成 pandas DataFrame
        - 若該日期沒有資料，回傳空的 DataFrame
        - 回傳完整 DataFrame、股價淨值比 < 1 的篩選 DataFrame、有效日期字串
        """
        print(f'設定下載日期：{date_str}')
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={date_str}&response=csv"
        response = requests.get(url)

        if response.status_code == 200 and len(response.content) > 0:
            try:
                try:
                    csv_text = response.content.decode("utf-8-sig")
                except UnicodeDecodeError:
                    csv_text = response.content.decode("big5", errors="ignore")

                # 嘗試讀取 CSV
                df = pd.read_csv(StringIO(csv_text), skiprows=1).dropna(how="all")

                if df.empty or "股價淨值比" not in df.columns:
                    print(f"{date_str} 沒有交易資料，回傳空 Dict")
                    return {}

                # 將股價淨值比轉成數字
                df["股價淨值比"] = pd.to_numeric(df["股價淨值比"], errors="coerce")

                print(f"已成功下載 {date_str} 的資料，共 {len(df)} 筆")

                # 篩選股價淨值比 < 1
                pb_df = df.loc[df["股價淨值比"] < 1].copy()

                return {date_str: len(pb_df)}

            except Exception as e:
                print(f"{date_str} 讀取失敗：{e}")
                return {}
        else:
            print(f"{date_str} 無效或沒有資料")
            return {}


    def month_dates(self, today: str):
        """
        輸入: today -> YYYYMMDD
        輸出: dict -> [YYYYMM, YYYYMMDD, ...]
        """
        if type(today) == int: today = str(today)
        dt = datetime.strptime(today, "%Y%m%d")
        dates = []
        for i in range(0, 33):  # 往前 32 天
            prev_day = dt - timedelta(days=i)
            if prev_day.weekday() < 5:
                dates.append(prev_day.strftime("%Y%m%d"))

        # 由舊到新排序
        return dates[::-1]


    def batch_download_twse(self, month_dates: dict, cache: dict) -> dict:
        """
        使用 get_recent_dates() 取得日期集合，
        依序呼叫 download_twse_csv() 下載資料，
        若有重複日期則直接使用之前已下載的結果，跳過重複下載。
        """
        results = {}
        for d in month_dates:
            if d in cache:
                results[d] = cache[d]
                # 如果已下載過，直接取用
                print(f"日期 {d} 已下載過，直接使用快取結果")
            else:
                # 沒下載過 → 呼叫 download_twse_csv
                inf = self.download_twse_csv(d)
                cache.update(inf)
                results.update(inf)
                time.sleep(0.5)

        return results, cache

    def pick_first_workday_each_week(self, data_dict):
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


    def show_Inf(self, key_value: dict, index_map: dict = {"20251201": 949}):
        # 先排序日期
        sorted_dates = sorted(key_value.keys())

        # 預設 index 從 1
        index_dict = {}

        # 如果有指定起始日期
        if index_map:
            for start_date, start_index in index_map.items():
                if start_date in sorted_dates:
                    pos = sorted_dates.index(start_date)

                    # 往後遞增
                    idx = start_index
                    for d in sorted_dates[pos:]:
                        index_dict[d] = idx
                        idx += 1

                    # 往前遞減
                    idx = start_index - 1
                    for d in reversed(sorted_dates[:pos]):
                        index_dict[d] = idx
                        idx -= 1
                else:
                    # 沒有指定日期 → 全部從 1 開始
                    for i, d in enumerate(sorted_dates, start=1):
                        index_dict[d] = i
        else:
            # 沒有 index_map → 全部從 1 開始
            for i, d in enumerate(sorted_dates, start=1):
                index_dict[d] = i

        # 輸出結果
        for d in sorted_dates:
            c = key_value[d]
            print(f'tseARR[{index_dict[d]},1]={d};   tseARR[{index_dict[d]},2]={c};')

    def get_monthly_data(self, m, setDateIndex={"20251201": 949}, show=True):
        print(f'執行 {m} 近31天的更新')

        cache = self.cache_init()
        print(f'現有 Cache 長度: {len(cache)}')

        days = self.month_dates(m)
        results = {}

        for d in days:
            if d in cache:
                results[d] = cache[d]
                # 如果已下載過，直接取用
                print(f"日期 {d} 已下載過，直接使用快取結果")
            else:
                # 沒下載過 → 呼叫 download_twse_csv
                inf = self.download_twse_csv(d)
                cache.update(inf)
                results.update(inf)
                time.sleep(1)

        self.update_json('json_data.json', cache)
        self.git_commit_and_push("json_data.json", "更新 TWSE 資料")

        if show:
            print("\n結果顯示：")
            self.show_Inf(results, setDateIndex)


    def main(self, show=True):
        cache = self.cache_init()

        # 取得近日日期
        dates = self.month_dates(datetime.today().strftime("%Y%m%d"))

        # 下載所有日期資料
        all_results, cache = self.batch_download_twse(dates, cache)

        self.update_json('json_data.json', cache)

        self.git_commit_and_push("json_data.json", "更新 TWSE 資料")

        if show:
            print('\n顯示近31天的結果：')
            # 顯示近期結果
            self.show_Inf(all_results)
        else:
            return cache
