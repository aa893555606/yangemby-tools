import streamlit as st
import requests
import json
import datetime
import os
import time
import threading

# --- 1. 基础配置 ---
st.set_page_config(page_title='yangemby-tools', layout='wide')

# 目录和文件路径
CONFIG_FILE = '/app/data/config.json'
DB_FILE = '/app/data/expiry_data.json'
if not os.path.exists('/app/data'): os.makedirs('/app/data')

# --- 2. 核心：智能读取配置 ---
def load_config():
    # A. 默认配置（优先尝试从环境变量读取，没有就用空）
    default = {
        "emby_url": os.getenv("EMBY_URL", ""),
        "emby_key": os.getenv("EMBY_API_KEY", ""),
        "admin_user": os.getenv("ADMIN_USERNAME", "admin"),
        "admin_pwd": os.getenv("ADMIN_PASSWORD", "admin")
    }
    # B. 如果本地有 config.json（说明你在网页改过），则以文件为准
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            file_config = json.load(f)
            return {**default, **file_config}
    return default

config = load_config()

# --- 3. 核心功能函数 ---
def sync_single_user(uid, new_date, policy):
    today = datetime.date.today()
    should_disable = new_date <= today
    with st.spinner('同步中...'):
        policy['IsDisabled'] = should_disable
        try:
            requests.post(f"{config['emby_url']}/Users/{uid}/Policy?api_key={config['emby_key']}", json=policy, timeout=5)
            db = {}
            if os.path.exists(DB_FILE):
                with open(DB_FILE, 'r', encoding='utf-8') as f: db = json.load(f)
            db[uid] = str(new_date)
            with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, ensure_ascii=False, indent=4)
            st.toast("✅ 同步成功")
        except Exception as e:
            st.error(f"失败: {e}")

def auto_check_task():
    while True:
        try:
            c = load_config()
            if c.get("emby_key") and os.path.exists(DB_FILE):