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
PUSH_LOG_FILE = '/app/data/push_log.json' 
DEFAULT_AVATAR = "https://cdn-icons-png.flaticon.com/512/149/149071.png"
file_lock = threading.Lock()

if not os.path.exists('/app/data'): os.makedirs('/app/data')

def load_config():
    default = {"emby_url": "", "emby_key": "", "admin_user": "admin", "admin_pwd": "admin", "auto_ban_popcorn": False, "bark_key": ""}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**default, **json.load(f)}
        except: pass
    return default

if 'cfg' not in st.session_state:
    st.session_state.cfg = load_config()

config = st.session_state.cfg
http_session = requests.Session()

# --- Bark 推送函数 ---
def send_bark_msg(title, content):
    cfg = load_config()
    bark_key = cfg.get('bark_key')
    if not bark_key: return
    try:
        bark_key = bark_key.strip().strip('/')
        url = f"https://api.day.app/{bark_key}/{title}/{content}"
        requests.get(url, timeout=5)
    except Exception as e:
        print(f"Bark 推送失败: {e}")

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

def load_push_log():
    if not os.path.exists(PUSH_LOG_FILE): return {}
    try:
        with open(PUSH_LOG_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {}

def save_push_log(log):
    with open(PUSH_LOG_FILE, 'w', encoding='utf-8') as f: json.dump(log, f)

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

def sync_to_emby(uid, target_date, policy, current_config=None, ban_reason="到期封禁"):
    """同步到期状态到 Emby"""
    cfg = current_config if current_config else config
    if not cfg.get('emby_url') or not cfg.get('emby_key'): return False

    today = datetime.date.today()
    is_forever = (target_date == datetime.date(2099, 12, 31))
    should_disable = (target_date < today) and not is_forever
    
    if policy.get('IsDisabled') != should_disable:
        policy['IsDisabled'] = should_disable
        try:
            url = f"{cfg['emby_url']}/Users/{uid}/Policy?api_key={cfg['emby_key']}"
            r = requests.post(url, json=policy, timeout=5)
            if r.status_code in [200, 204]:
                user_url = f"{cfg['emby_url']}/Users/{uid}?api_key={cfg['emby_key']}"
                u_info = requests.get(user_url, timeout=5).json()
                uname = u_info.get('Name', uid)
                
                if should_disable:
                    status_display = f"🚫 账号已封禁 ({ban_reason})"
                    send_bark_msg("yangemby 封禁通知", f"用户: {uname}\n原因: {ban_reason}")
                else:
                    status_display = "✅ 账号已激活/延期"
                    send_bark_msg("yangemby 解封通知", f"用户: {uname}\n状态: 已重新激活")
                
                try: st.toast(status_display, icon="ℹ️")
                except: pass
                return True
            return False
        except: return False
    return True

# --- 3. 后台全自动巡检线程 ---
def auto_sync_worker():
    print("🚀 [yangemby-tools] 后台自动巡检线程已启动...")
    while True:
        try:
            cfg = load_config()
            db = safe_load_db()
            push_log = load_push_log()
            
            tz_beijing = timezone(timedelta(hours=8))
            now_bj = datetime.datetime.now(tz_beijing)
            today_str = now_bj.strftime('%Y-%m-%d')
            is_push_time = (now_bj.hour == 8 and 30 <= now_bj.minute <= 35)

            if cfg.get('emby_url') and cfg.get('emby_key'):
                u_url = f"{cfg['emby_url']}/Users?api_key={cfg['emby_key']}"
                users = requests.get(u_url, timeout=10).json()
                s_url = f"{cfg['emby_url']}/Sessions?api_key={cfg['emby_key']}"
                sessions = requests.get(s_url, timeout=10).json()
                
                if cfg.get('auto_ban_popcorn'):
                    violating_user_ids = set()
                    for s in sessions:
                        if 'NowPlayingItem' in s:
                            client = s.get('Client', '')
                            device = s.get('DeviceName', '')
                            if any(kw in (client + device).lower() for kw in ["爆米花", "popcorn"]):
                                uid_s = s.get('UserId')
                                if uid_s:
                                    violating_user_ids.add(uid_s)
                    
                    for uid_v in violating_user_ids:
                        u_target = next((user for user in users if user['Id'] == uid_v), None)
                        if u_target and not u_target['Policy'].get('IsDisabled'):
                            u_target['Policy']['IsDisabled'] = True
                            p_url = f"{cfg['emby_url']}/Users/{uid_v}/Policy?api_key={cfg['emby_key']}"
                            requests.post(p_url, json=u_target['Policy'], timeout=5)
                            uname = u_target.get('Name', uid_v)
                            send_bark_msg("🚨 播放中违规封禁", f"用户: {uname}\n原因: 正在使用违规播放器观影")

                for u in users:
                    uid = u['Id']
                    if uid in db:
                        if db[uid] == "1970-01-01": continue
                        
                        target_dt = datetime.date.fromisoformat(db[uid])
                        is_currently_disabled = u['Policy'].get('IsDisabled', False)
                        date_expired = (target_dt < now_bj.date()) and (db[uid] != "2099-12-31")
                        
                        if date_expired or not is_currently_disabled:
                            sync_to_emby(uid, target_dt, u['Policy'], cfg, ban_reason="到期封禁")
                        
                        if db[uid] != "2099-12-31":
                            days_left = (target_dt - now_bj.date()).days
                            log_key = f"{uid}_{today_str}"
                            if days_left == 0 and is_push_time:
                                if push_log.get(log_key) != "final":
                                    send_bark_msg("⚠️ 最后警告", f"用户: {u['Name']}\n账号今日到期。")
                                    push_log[log_key] = "final"
                            elif days_left in [1, 3] and push_log.get(log_key) is None:
                                if is_push_time:
                                    send_bark_msg("⏳ 续费提醒", f"用户: {u['Name']}\n还有 {days_left} 天到期。")
                                    push_log[log_key] = "warning"
                save_push_log(push_log)
        except Exception as e:
            print(f"❌ [巡检出错]: {e}")
        time.sleep(60)

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
    st.title("🛠️ yangemby-tools")
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
    st.markdown("### 🔔 消息推送")
    st.session_state.cfg['bark_key'] = st.text_input("Bark 推送 Key", value=config.get('bark_key', ''), help="在 iPhone Bark App 获取")
    if st.button("⚡ 测试推送"):
        if st.session_state.cfg['bark_key']:
            send_bark_msg("yangemby-tools", "这是一条测试推送消息，配置成功！")
            st.toast("测试消息已发送")
        else:
            st.error("请先填写 Bark Key")

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

# --- 统计栏修改点 ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("总用户", len(users_res))
# 计算已封禁的用户（Policy.IsDisabled 为 True）
banned_count = sum(1 for u in users_res if u.get('Policy', {}).get('IsDisabled', False))
col2.metric("已封禁", banned_count)
expired_count = sum(1 for uid, d in db.items() if d <= str(datetime.date.today()) and d not in ["2099-12-31", "1970-01-01"])
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
    is_manual_ban = (saved_date == "1970-01-01")
    
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
                    if 'NowPlayingItem' in s:
                        item = s['NowPlayingItem']
                        st.markdown(f"<div class='streaming-tag'>▶️ 正在看: {item.get('Name')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<small style='color:#64748b;'>🖥️ {client} | {device}</small>", unsafe_allow_html=True)
            else:
                last_active = format_relative_time(u.get('LastActivityDate'))
                st.markdown(f"<small style='color:#94a3b8;'>💤 离线 (最后上线: {last_active})</small>", unsafe_allow_html=True)
            color = "#ef4444" if is_disabled else "#10b981"
            st.markdown(f"<span style='color:{color}; font-weight:bold; font-size:0.8rem;'>● {'账号已封锁' if is_disabled else '账号正常'}</span>", unsafe_allow_html=True)

        with c3:
            if is_disabled:
                final_reason = "管理员封禁"
                is_expired_ban = False
                try:
                    expiry_dt = datetime.date.fromisoformat(saved_date)
                    if is_manual_ban:
                        final_reason = "管理员手动封禁"
                    elif expiry_dt < today and saved_date != "2099-12-31":
                        final_reason = "到期封禁"
                        is_expired_ban = True
                    else:
                        for s in sessions_res:
                            if s.get('UserId') == uid and any(kw in str(s.get('Client','')).lower() for kw in ["爆米花", "popcorn"]):
                                final_reason = "违规播放器封禁"
                                break
                except: pass

                st.error(f"🚫 该账号已被封锁\n\n原因: **{final_reason}**")
                
                if st.button("🔓 立即解封", key=f"unban_{uid}", use_container_width=True):
                    if is_manual_ban:
                        db[uid] = str(today)
                        toast_msg = f"✅ 已恢复权限: {uname}"
                    elif is_expired_ban:
                        new_expiry = today + timedelta(days=30)
                        db[uid] = str(new_expiry)
                        toast_msg = f"✅ 已延期30天解封: {uname}"
                    else:
                        toast_msg = f"✅ 已解封: {uname} (日期不变)"
                    
                    policy['IsDisabled'] = False 
                    requests.post(f"{config['emby_url']}/Users/{uid}/Policy?api_key={config['emby_key']}", json=policy, timeout=5)
                    safe_save_db(db)
                    st.toast(toast_msg)
                    send_bark_msg("🔓 解封通知", f"管理员解封了用户: {uname}")
                    time.sleep(0.8) 
                    st.rerun()
            elif is_forever:
                st.success("✨ 永久授权用户")
                if st.button("🚫 立即禁用", key=f"ban_f_{uid}", use_container_width=True):
                    db[uid] = "1970-01-01" 
                    policy['IsDisabled'] = True
                    requests.post(f"{config['emby_url']}/Users/{uid}/Policy?api_key={config['emby_key']}", json=policy, timeout=5)
                    safe_save_db(db)
                    st.toast(f"🚫 已封禁永久用户: {uname}")
                    send_bark_msg("🚫 手动封禁", f"管理员手动禁用了永久用户: {uname}")
                    time.sleep(0.8)
                    st.rerun()
            else:
                current_d_obj = datetime.date.fromisoformat(saved_date) if saved_date != "1970-01-01" else today
                d = st.date_input("到期时间", value=current_d_obj, key=f"d_{uid}")
                delta = (d - today).days
                if delta >= 0:
                    st.markdown(f'<span class="pill pill-green">剩余 {delta + 1} 天</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="pill pill-red">已过期 {-delta} 天</span>', unsafe_allow_html=True)
                
                if st.button("🚫 立即禁用", key=f"ban_n_{uid}", use_container_width=True):
                    db[uid] = "1970-01-01" 
                    policy['IsDisabled'] = True
                    requests.post(f"{config['emby_url']}/Users/{uid}/Policy?api_key={config['emby_key']}", json=policy, timeout=5)
                    safe_save_db(db)
                    st.toast(f"🚫 已手动封禁: {uname}")
                    send_bark_msg("🚫 手动封禁", f"管理员手动禁用了用户: {uname}")
                    time.sleep(0.8)
                    st.rerun()

                if str(d) != saved_date and saved_date != "1970-01-01":
                    db[uid] = str(d)
                    if sync_to_emby(uid, d, policy):
                        safe_save_db(db)
                        st.rerun()

        with c4:
            if not is_disabled:
                st.write("永久")
                if st.checkbox("∞", value=is_forever, key=f"f_{uid}") != is_forever:
                    new_d = datetime.date(2099, 12, 31) if not is_forever else today
                    db[uid] = str(new_d)
                    if sync_to_emby(uid, new_d, policy):
                        safe_save_db(db)
                        st.rerun()
            else:
                st.write("状态")
                st.markdown("⚠️已锁")

st.markdown("<center style='color:#94a3b8; font-size: 0.8rem; margin-top: 50px;'>powered by liangzaidong | yangemby-tools </center>", unsafe_allow_html=True)