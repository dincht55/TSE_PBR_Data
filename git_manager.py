import os
import json
import subprocess

class GitManager:
    def __init__(self, name, email, pat, branch="main"):
        self.branch = branch
        self.user_name = name
        self.user_email = email
        self.pat = pat
        self.repo_dir = "repo"

    # 統一 Git 指令執行
    def run_git_command(self, args, check=True):
        try:
            result = subprocess.run(["git"] + args,
                         check=check,
                         capture_output=True,
                         text=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"❌ Git 指令失敗: {' '.join(args)}")
            print(e.stderr)
            return None

    # 取得本地 JSON
    def get_json(self, json_name):
        try:
            with open(json_name, "r", encoding="utf-8") as f:
                cache = json.load(f)
                if cache is None:
                    cache = {}
            return cache
        except FileNotFoundError:
            print(f"找不到檔案 {json_name}")
            return {}
        except json.JSONDecodeError:
            print(f"{json_name} 格式錯誤")
            return {}

    # 更新並排序 JSON
    def update_json(self, json_name, json_data):
        sort_data = dict(sorted(json_data.items(), key=lambda x: x[0]))
        with open(json_name, "w", encoding="utf-8") as f:
            json.dump(sort_data, f, ensure_ascii=False, indent=4)
        print(f"已依日期排序並更新 {json_name}")

    # 初始化 Git repo
    def git_init(self):
        """初始化 Git repo，若不存在則 clone，存在則 pull 最新版本"""
        self.run_git_command(["config", "--global", "user.name", self.user_name])
        self.run_git_command(["config", "--global", "user.email", self.user_email])

        repo_url = f"https://{self.user_name}:{self.pat}@github.com/{self.user_name}/TSE_PBR_Data.git"

        if not os.path.exists(".git"):
            try:
                self.run_git_command(["clone", repo_url, self.repo_dir])
                os.chdir(self.repo_dir)
                print(f"✅ 已 clone 遠端 repo 到 {self.repo_dir}/")
            except Exception:
                print("❌ clone 失敗，請檢查分支名稱或 Token")
                return
        else:
            self.run_git_command(["remote", "remove", "origin"], check=False)
            self.run_git_command(["remote", "add", "origin", repo_url])

        try:
            self.run_git_command(["pull", "origin", self.branch])
            print(f"🔄 已初始化並下載最新版本，分支 {self.branch}")
        except Exception:
            if os.path.exists(self.repo_dir) and not os.path.exists(".git"):
                os.chdir(self.repo_dir)
            self.run_git_command(["pull", "origin", self.branch])
            print(f"✅ 已下載最新版本 {self.branch}")

    # 提交並推送檔案
    def git_commit_and_push(self, file_path, commit_msg):
        if not os.path.exists(file_path):
            repo_path = os.path.join(self.repo_dir, file_path)
            if os.path.exists(repo_path):
                file_path = repo_path
            else:
                print(f"檔案 {file_path} 不存在，無法提交")
                return

        self.run_git_command(["add", file_path])
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode == 0:
            print("沒有變更需要提交")
            return

        self.run_git_command(["commit", "-m", commit_msg])
        self.run_git_command(["push", "origin", self.branch])
        print(f"已提交並推送 {file_path} 到 {self.branch}")

    # 刪除檔案
    def git_delete_file(self, file_path, commit_msg="刪除檔案"):
        if not os.path.exists(file_path):
            repo_path = os.path.join(self.repo_dir, file_path)
            if os.path.exists(repo_path):
                file_path = repo_path
            else:
                print(f"檔案 {file_path} 不存在，跳過刪除")
                return

        try:
            self.run_git_command(["rm", file_path])
            self.run_git_command(["commit", "-m", commit_msg])
            self.run_git_command(["push", "origin", self.branch])
            print(f"已刪除 {file_path} 並推送到 {self.branch}")
        except Exception:
            os.remove(file_path)
            print(f"檔案 {file_path} 不在 Git 追蹤中，已刪除本地檔案")
