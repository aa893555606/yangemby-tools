import streamlit as st
import requests
import json
import datetime
import os
import time
import threading
import schedule

st.set_page_config(page_title='yangemby-tools', layout='wide')

DEFAULT_AVATAR = "https://p.qlogo.cn/gh/2901301/2901301/100"
CONFIG_FILE = '/app/data/config.json'
DB_FILE = '/app/data/expiry_data.json'

if not os.path.exists('/app/data'): 
    os.makedirs('/app/data')

def load_config():
    d = {"emby_url": "http://192.168.1.160:8096", "emby_key": "", "admin_user": "admin", "admin_pwd": "admin"}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return {**d, **json.load(f)}
    return d

def auto_scan():
    c = load_config()
    if not c.get("emby_key"): 
        return
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            r = requests.get(f"{c['emby_url']}/Users?api_key={c['emby_key']}", timeout=10)
            users = r.json()
            today = str(datetime.date.today())
            for u in users:
                uid = u['Id']
                if u.get('Policy', {}).get('IsAdministrator'): 
                    continue
                exp = data.get(uid)
                if not exp: 
                    continue
                dis = exp <= today
                if u['Policy'].get('IsDisabled') != dis:
                    u['Policy']['IsDisabled'] = dis
                    requests.post(f"{c['emby_url']}/Users/{uid}/Policy?api_key={c['emby_key']}", json=u['Policy'])
    except: 
        pass

def scheduler_loop():
    schedule.every().day.at("12:00").do(auto_scan)
    while True:
        schedule.run_pending()
        time.sleep(60)

if "scheduler_started" not in st.session_state:
    threading.Thread(target=scheduler_loop, daemon=True).start()
    st.session_state["scheduler_started"] = True

config = load_config()

if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("🔑 yangemby-tools")
    u_in = st.text_input("Username")
    p_in = st.text_input("Password", type="password")
    if st.button("Login", use_container_width=True):
        if u_in == config["admin_user"] and p_in == config["admin_pwd"]:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

with st.sidebar:
    st.header("Settings")
    s_url = st.text_input("Emby URL", value=config["emby_url"])
    s_key = st.text_input("API Key", value=config["emby_key"], type="password")
    s_user = st.text_input("Admin User", value=config["admin_user"])
    s_pwd = st.text_input("Admin Pwd", value=config["admin_pwd"], type="password")
    if st.button("Save Configuration"):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"emby_url": s_url, "emby_key": s_key, "admin_user": s_user, "admin_pwd": s_pwd}, f)
        st.rerun()
    st.divider()
    if st.button("Logout"):
        st.session_state["auth"] = False
        st.rerun()

st.title('🛠️ yangemby-tools')

try:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            expiry_data = json.load(f)
    else:
        expiry_data = {}

    res = requests.get(f"{config['emby_url']}/Users?api_key={config['emby_key']}", timeout=5)
    users = res.json()
    st.success(f"Connected: {len(users)} Users")

    today = datetime.date.today()
    updates = {}

    for u in users:
        if u.get('Policy', {}).get('IsAdministrator'): 
            continue
        uid, uname = u['Id'], u['Name']
        dis = u.get('Policy', {}).get('IsDisabled', False)
        img = f"{config['emby_url']}/Users/{uid}/Images/Primary?api_key={config['emby_key']}"

        c1, c2, c3, c4 = st.columns([0.6, 1.2, 1.8, 0.6])
        with c1:
            try:
                if requests.head(img, timeout=0.5).status_code != 200: 
                    img = DEFAULT_AVATAR
            except: 
                img = DEFAULT_AVATAR
            st.image(img, width=60)
        with c2:
            st.markdown(f"<div style='margin-top:10px;'><b>{uname}</b></div>", unsafe_allow_html=True)
            clr = "red" if dis else "#28a745"
            txt = "Disabled" if dis else "Active"
            st.markdown(f"<small style='color:{clr};font-weight:bold;'>{txt}</small>", unsafe_allow_html=True)
        with c3:
            cur_val = expiry_data.get(uid, str(today))
            is_f = (cur_val == "2099-12-31")
            if st.session_state.get(f"f_{uid}", is_f):
                st.markdown("<div style='margin-top:20px;'><span style='background-color:#fff3cd;color:#856404;padding:5px 15px;border-radius:15px;font-weight:bold;'>FOREVER</span></div>", unsafe_allow_html=True)
                val = datetime.date(2099, 12, 31)
            else:
                val = st.date_input("Exp", value=datetime.date.fromisoformat(cur_val), key=f"d_{uid}", label_visibility="collapsed")
        with c4:
            f_check = st.checkbox("Inf", value=is_f, key=f"f_{uid}")
            if f_check: 
                val = datetime.date(2099, 12, 31)
            updates[uid] = (val, u['Policy'])
        st.divider()

    if st.button("Sync to Emby", type="primary", use_container_width=True):
        for uid, (dt, pol) in updates.items():
            sd = dt <= today
            if pol.get('IsDisabled') != sd:
                pol['IsDisabled'] = sd
                requests.post(f"{config['emby_url']}/Users/{uid}/Policy?api_key={config['emby_key']}", json=pol)
            expiry_data[uid] = str(dt)
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(expiry_data, f, ensure_ascii=False, indent=4)
        st.rerun()
except:
    st.error("Connection Error")

st.markdown("<br><hr><center style='color:#888;font-size:0.9em;'>Power by 靓仔东</center>", unsafe_allow_html=True)