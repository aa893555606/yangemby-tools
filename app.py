import streamlit as st
import requests
import json
import datetime
import os
import time
import threading
from datetime import timezone, timedelta

# --- 1. 初始化与配置 ---
st.set_page_config(page_title='yangemby-tools', layout='wide')
DB_FILE = '/app/data/expiry_data.json'
CONFIG_FILE = '/app/data/config.json'
DEFAULT_AVATAR = "https://cdn-icons-png.flaticon.com/512/149/149071.png"
file_lock = threading.Lock()

if not os.path.exists('/app/data'): os.makedirs('/app/data')

def load_config():
    default = {"emby_url": "", "emby_key": "", "admin_user": "admin", "admin_pwd": "admin", "auto_ban_popcorn": False}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**default, **json.load(f)}
        except: pass
    return default

# 使用 session_state 确保配置在刷新时不丢失
if 'cfg' not in st.session_state:
    st.session_state.cfg = load_config()

config = st.session_state.cfg
http_session = requests.Session()

# --- 2. 核心逻辑工具 ---
def safe_save_db(data):
    with file_lock:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

def safe_load_db():
    if not os.path.exists(DB_FILE): return {}
    with file_lock:
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}

def format_relative_time(date_str):
    if not date_str: return "从未登录"
    try:
        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.datetime.now(timezone.utc)
        diff = now - dt
        if diff.days > 0: return f"{diff.days} 天前"
        if diff.seconds > 3600: return f"{diff.seconds // 3600} 小时前"
        if diff.seconds > 60: return f"{diff.seconds // 60} 分钟前"
        return "刚刚"
    except: return "未知时间"

def sync_to_emby(uid, target_date, policy, current_config=None):
    """同步到期状态到 Emby (核心封禁/解封逻辑)"""
    # 如果没传配置，则使用全局配置
    cfg = current_config if current_config else config
    if not cfg.get('emby_url') or not cfg.get('emby_key'): return False

    today = datetime.date.today()
    # 逻辑：到期时间 <= 今天 则禁用；如果是 2099-12-31 (永久) 则不禁用
    is_forever = (target_date == datetime.date(2099, 12, 31))
    should_disable = (target_date <= today) and not is_forever
    
    if policy.get('IsDisabled') != should_disable:
        policy['IsDisabled'] = should_disable
        try:
            url = f"{cfg['emby_url']}/Users/{uid}/Policy?api_key={cfg['emby_key']}"
            r = requests.post(url, json=policy, timeout=5)
            return r.status_code == 204 or r.status_code == 200
        except: return False
    return True

# --- 3. 后台全自动巡检线程 (每2分钟一次) ---
def auto_sync_worker():
    """后台静默运行，无需打开网页"""
    print("🚀 [yangemby-tools] 后台自动巡检线程已启动 (2分钟/次)...")
    while True:
        try:
            cfg = load_config()
            db = safe_load_db()
            if cfg.get('emby_url') and cfg.get('emby_key'):
                url = f"{cfg['emby_url']}/Users?api_key={cfg['emby_key']}"
                users = requests.get(url, timeout=10).json()
                for u in users:
                    uid = u['Id']
                    if uid in db:
                        target_dt = datetime.date.fromisoformat(db[uid])
                        sync_to_emby(uid, target_dt, u['Policy'], cfg)
                print(f"✅ [后台巡检] {datetime.datetime.now().strftime('%H:%M:%S')} 同步完成")
        except Exception as e:
            print(f"❌ [后台巡检出错]: {e}")
        time.sleep(120) # 2分钟

# 启动线程
if "worker_started" not in st.session_state:
    threading.Thread(target=auto_sync_worker, daemon=True).start()
    st.session_state["worker_started"] = True

# --- 4. 界面样式 ---
st.markdown("""
<style>
    .streaming-tag { color: #3b82f6; font-size: 0.85rem; font-weight: bold; background: #eff6ff; padding: 4px 8px; border-radius: 4px; border-left: 3px solid #3b82f6; }
    .pill { padding: 2px 8px; border-radius: 5px; font-size: 0.7rem; font-weight: 600; }
    .pill-green { background: #dcfce7; color: #166534; }
    .pill-red { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)

# --- 5. 登录验证 ---
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

# --- 6. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 系统配置")
    st.session_state.cfg['emby_url'] = st.text_input("Emby 地址", value=config['emby_url'])
    st.session_state.cfg['emby_key'] = st.text_input("API Key", value=config['emby_key'], type="password")
    
    st.divider()
    st.markdown("### ⛔ 播放器限制")
    ban_state = st.toggle("🚫 实时封禁爆米花播放器", value=st.session_state.cfg.get('auto_ban_popcorn', False))
    if ban_state != st.session_state.cfg.get('auto_ban_popcorn'):
        st.session_state.cfg['auto_ban_popcorn'] = ban_state
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(st.session_state.cfg, f)
        st.toast("配置已更新")

    if st.button("💾 保存基础配置", use_container_width=True):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(st.session_state.cfg, f)
        st.success("配置已保存")
        time.sleep(0.5)
        st.rerun()
    
    if st.button("🚪 退出管理", use_container_width=True):
        st.session_state["auth"] = False
        st.query_params.clear()
        st.rerun()

# --- 7. 数据拉取 ---
try:
    db = safe_load_db()
    users_res = http_session.get(f"{config['emby_url']}/Users?api_key={config['emby_key']}", timeout=5).json()
    sessions_res = http_session.get(f"{config['emby_url']}/Sessions?api_key={config['emby_key']}", timeout=5).json()
    user_active_sessions = {}
    for s in sessions_res:
        uid_s = s.get('UserId')
        if uid_s:
            if uid_s not in user_active_sessions: user_active_sessions[uid_s] = []
            user_active_sessions[uid_s].append(s)
except Exception as e:
    st.error(f"📡 连接 Emby 失败: {e}")
    st.stop()

# --- 8. 主界面展示 ---
st.title('🛠️ yangemby-tools')

col1, col3, col4 = st.columns(3)
col1.metric("总用户", len(users_res))
expired_count = sum(1 for uid, d in db.items() if d <= str(datetime.date.today()) and d != "2099-12-31")
col3.metric("已过期", expired_count)
col4.metric("正在观影", sum(1 for s in sessions_res if 'NowPlayingItem' in s))

st.divider()

today = datetime.date.today()

for u in users_res:
    if u.get('Policy', {}).get('IsAdministrator'): continue
    uid, uname = u['Id'], u['Name']
    policy = u['Policy']
    is_disabled = policy.get('IsDisabled', False)
    saved_date = db.get(uid, str(today))
    is_forever = (saved_date == "2099-12-31")
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([0.5, 1.8, 1.2, 0.5])
        
        with c1:
            avatar = f"{config['emby_url']}/Users/{uid}/Images/Primary?api_key={config['emby_key']}" if u.get('PrimaryImageTag') else DEFAULT_AVATAR
            st.image(avatar, width=70)

        with c2:
            st.markdown(f"### {uname}")
            if uid in user_active_sessions:
                for s in user_active_sessions[uid]:
                    client, device = s.get('Client', ''), s.get('DeviceName', '')
                    is_streaming = 'NowPlayingItem' in s
                    
                    # 爆米花播放器实时封禁逻辑
                    if st.session_state.cfg.get('auto_ban_popcorn') and is_streaming:
                        if any(kw in (client + device) for kw in ["爆米花", "popcorn", "Popcorn"]):
                            if not is_disabled:
                                policy['IsDisabled'] = True
                                http_session.post(f"{config['emby_url']}/Users/{uid}/Policy?api_key={config['emby_key']}", json=policy)
                                is_disabled = True
                                st.toast(f"🚫 自动封禁违规用户: {uname}")

                    if is_streaming:
                        item = s['NowPlayingItem']
                        st.markdown(f"<div class='streaming-tag'>▶️ 正在看: {item.get('Name')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<small style='color:#64748b;'>🖥️ {client} | {device}</small>", unsafe_allow_html=True)
            else:
                last_active = format_relative_time(u.get('LastActivityDate'))
                st.markdown(f"<small style='color:#94a3b8;'>💤 离线 (最后上线: {last_active})</small>", unsafe_allow_html=True)
            
            color = "#ef4444" if is_disabled else "#10b981"
            st.markdown(f"<span style='color:{color}; font-weight:bold; font-size:0.8rem;'>● {'账号已封锁' if is_disabled else '账号正常'}</span>", unsafe_allow_html=True)

        with c3:
            if is_forever:
                st.success("✨ 永久授权用户")
            else:
                try:
                    current_d_obj = datetime.date.fromisoformat(saved_date)
                except:
                    current_d_obj = today
                
                d = st.date_input("到期时间", value=current_d_obj, key=f"d_{uid}")
                delta = (d - today).days
                if delta > 0:
                    st.markdown(f'<span class="pill pill-green">剩余 {delta} 天</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="pill pill-red">已过期 {abs(delta)} 天</span>', unsafe_allow_html=True)
                
                if str(d) != saved_date:
                    db[uid] = str(d)
                    if sync_to_emby(uid, d, policy):
                        safe_save_db(db)
                        st.rerun()

        with c4:
            st.write("永久")
            if st.checkbox("∞", value=is_forever, key=f"f_{uid}") != is_forever:
                new_d = datetime.date(2099, 12, 31) if not is_forever else today
                db[uid] = str(new_d)
                if sync_to_emby(uid, new_d, policy):
                    safe_save_db(db)
                    st.rerun()

st.markdown("<center style='color:#94a3b8; font-size: 0.8rem; margin-top: 50px;'>powered by liangzaidong | yangemby-tools </center>", unsafe_allow_html=True)