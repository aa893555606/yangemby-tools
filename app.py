import streamlit as st
import requests
import json
import datetime
import os
import time
import threading

# --- 1. UI 增强与对齐修复 ---
st.set_page_config(page_title='yangemby-tools', layout='wide')

# 简约默认头像
DEFAULT_AVATAR = "https://cdn-icons-png.flaticon.com/512/149/149071.png"

st.markdown("""
<style>
    /* 用户卡片容器 */
    .user-container {
        background: #ffffff;
        border: 1px solid #f1f5f9;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
    
    /* 药丸标签位置修正：强制放在日期选择器下方并对齐 */
    .pill-container {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 4px;
    }
    
    .day-pill {
        padding: 2px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .pill-green { background-color: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
    .pill-red { background-color: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }

    /* 强制刷新按钮居中 */
    div.stButton > button:first-child {
        display: block;
        margin: 20px auto !important;
        width: 260px;
        border-radius: 20px;
        background: #4f46e5;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. 基础数据处理 ---
CONFIG_FILE = '/app/data/config.json'
DB_FILE = '/app/data/expiry_data.json'
if not os.path.exists('/app/data'): os.makedirs('/app/data')

def load_config():
    default = {"emby_url": "", "emby_key": "", "admin_user": "admin", "admin_pwd": "admin"}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return {**default, **json.load(f)}
    return default

config = load_config()

def sync_to_emby(uid, target_date, policy):
    today = datetime.date.today()
    should_disable = target_date <= today
    policy['IsDisabled'] = should_disable
    try:
        url = f"{config['emby_url']}/Users/{uid}/Policy?api_key={config['emby_key']}"
        requests.post(url, json=policy, timeout=5)
        return True
    except: return False

# 后台检查任务
def auto_check_task():
    while True:
        try:
            c = load_config()
            if c['emby_key'] and os.path.exists(DB_FILE):
                with open(DB_FILE, 'r', encoding='utf-8') as f: db = json.load(f)
                res = requests.get(f"{c['emby_url']}/Users?api_key={c['emby_key']}", timeout=10)
                today_str = str(datetime.date.today())
                for u in res.json():
                    if u.get('Policy', {}).get('IsAdministrator'): continue
                    saved_exp = db.get(u['Id'])
                    if saved_exp:
                        should_be_disabled = saved_exp <= today_str
                        if u['Policy'].get('IsDisabled') != should_be_disabled:
                            u['Policy']['IsDisabled'] = should_be_disabled
                            requests.post(f"{c['emby_url']}/Users/{u['Id']}/Policy?api_key={c['emby_key']}", json=u['Policy'])
        except: pass
        time.sleep(3600)

if "timer_started" not in st.session_state:
    threading.Thread(target=auto_check_task, daemon=True).start()
    st.session_state["timer_started"] = True

# --- 3. 登录检查 (使用最新 st.query_params) ---
if "auth" not in st.session_state:
    st.session_state["auth"] = st.query_params.get("login") == "true"

if not st.session_state["auth"]:
    st.title("🔐 yangemby-tools")
    with st.container(border=True):
        u = st.text_input("账号")
        p = st.text_input("密码", type="password")
        if st.button("登录", use_container_width=True):
            if u == config["admin_user"] and p == config["admin_pwd"]:
                st.session_state["auth"] = True
                st.query_params["login"] = "true"
                st.rerun()
            else: st.error("账号或密码不对")
    st.stop()

# --- 4. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 配置管理")
    nu = st.text_input("Emby 地址", value=config['emby_url'])
    nk = st.text_input("API Key", value=config['emby_key'], type="password")
    na = st.text_input("管理账号", value=config['admin_user'])
    np = st.text_input("管理密码", value=config['admin_pwd'], type="password")
    if st.button("💾 保存配置"):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"emby_url": nu, "emby_key": nk, "admin_user": na, "admin_pwd": np}, f)
        st.success("已保存"); time.sleep(1); st.rerun()
    if st.button("🚪 退出登录"):
        st.session_state["auth"] = False
        st.query_params.clear()
        st.rerun()

# --- 5. 主界面 ---
st.title('🛠️ Emby 用户到期管理')

try:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f: db = json.load(f)
    else: db = {}

    users = requests.get(f"{config['emby_url']}/Users?api_key={config['emby_key']}", timeout=5).json()
    st.info(f"💡 当前已连接：{config['emby_url']} (共 {len(users)} 位用户)")

    today = datetime.date.today()

    for u in users:
        if u.get('Policy', {}).get('IsAdministrator'): continue
        uid, uname = u['Id'], u['Name']
        is_disabled = u['Policy'].get('IsDisabled', False)
        saved_date = db.get(uid, str(today))
        is_forever = (saved_date == "2099-12-31")

        # 使用布局列
        c1, c2, c3, c4 = st.columns([0.6, 1.4, 2.0, 0.6])
        
        with c1:
            # 头像逻辑：没头像的换成默认高级图标
            avatar = f"{config['emby_url']}/Users/{uid}/Images/Primary?api_key={config['emby_key']}" if u.get('PrimaryImageTag') else DEFAULT_AVATAR
            st.image(avatar, width=60)

        with c2:
            st.markdown(f"**{uname}**")
            color = "#ef4444" if is_disabled else "#10b981"
            st.markdown(f"<small style='color:{color}; font-weight:600;'>{'🚫已封禁' if is_disabled else '✅活跃中'}</small>", unsafe_allow_html=True)
        
        with c3:
            # 这里的包裹容器修正了标签出框的问题
            st.markdown('<div class="pill-container">', unsafe_allow_html=True)
            if is_forever:
                st.info("✨ 永久有效")
            else:
                d = st.date_input("到期日期", value=datetime.date.fromisoformat(saved_date), key=f"d_{uid}", label_visibility="collapsed")
                # 计算天数
                delta = (d - today).days
                if delta > 0:
                    st.markdown(f'<div class="day-pill pill-green">⌛ 剩 {delta} 天到期</div>', unsafe_allow_html=True)
                elif delta == 0:
                    st.markdown(f'<div class="day-pill pill-red">⏰ 今天到期</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="day-pill pill-red">⚠️ 已过期 {abs(delta)} 天</div>', unsafe_allow_html=True)

                if str(d) != saved_date:
                    db[uid] = str(d)
                    if sync_to_emby(uid, d, u['Policy']):
                        with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f)
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        
        with c4:
            if st.checkbox("永久", value=is_forever, key=f"f_{uid}") != is_forever:
                new_d = datetime.date(2099, 12, 31) if not is_forever else today
                db[uid] = str(new_d)
                if sync_to_emby(uid, new_d, u['Policy']):
                    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f)
                    st.rerun()
        st.divider()

    # 底部居中按钮
    if st.button("🔄 刷新 Emby 数据并同步"):
        st.rerun()

except Exception as e:
    st.error("📡 无法连接 Emby，请检查侧边栏配置")

st.markdown("<center style='color:#94a3b8; font-size: 0.8rem; margin: 30px 0;'>Power by 靓仔东 | yangemby-tools</center>", unsafe_allow_html=True)