import customtkinter
import psutil
import requests
import datetime
import json
import os
from tkinter import simpledialog, messagebox

CONFIG_FILE = 'config.json'

# 초기 설정 불러오기 또는 생성
def load_or_create_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"api_key": "", "riot_id": "", "loss_limit": 2}, f)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    updated = False

    if not config.get("api_key"):
        config["api_key"] = simpledialog.askstring("API Key 입력", "Riot API Key를 입력하세요:")
        updated = True

    if not config.get("riot_id"):
        config["riot_id"] = simpledialog.askstring("Riot ID 입력", "Riot ID (닉네임#태그)를 입력하세요:")
        updated = True

    if "loss_limit" not in config:
        config["loss_limit"] = 2
        updated = True

    if updated:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)

    return config

config = load_or_create_config()
api_key = config['api_key']
riot_id = config['riot_id']
loss_limit = config['loss_limit']

# Riot ID → PUUID
def get_puuid_from_riot_id(riot_id):
    if "#" not in riot_id:
        return None
    game_name, tag_line = riot_id.split("#")
    url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={api_key}"
    res = requests.get(url)
    if res.status_code != 200:
        return None
    data = res.json()
    return data.get("puuid")

# 클라이언트 종료
def close_lol_client():
    killed = False
    for proc in psutil.process_iter(['name']):
        try:
            proc_name = proc.info['name']
            if proc_name and any(x in proc_name.lower() for x in ['league', 'riot', 'vanguard']):
                proc.kill()
                killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed

# 패수 확인 및 UI 반영
def check_losses():
    try:
        puuid = get_puuid_from_riot_id(riot_id)
        if not puuid:
            status_label.configure(text="Riot ID 조회 실패")
            return

        today = datetime.datetime.now().strftime('%Y-%m-%d')
        match_url = f'https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=10&api_key={api_key}'
        match_ids = requests.get(match_url).json()

        wins, losses = 0, 0
        match_texts = []

        for match_id in match_ids:
            detail_url = f'https://asia.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={api_key}'
            match_detail = requests.get(detail_url).json()
            game_date = datetime.datetime.fromtimestamp(match_detail['info']['gameCreation'] / 1000).strftime('%Y-%m-%d')
            if game_date != today:
                continue

            for p in match_detail['info']['participants']:
                if p['puuid'] == puuid:
                    result = "승" if p['win'] else "패"
                    match_texts.append(f"{result} | 챔피언: {p['championName']} | KDA: {p['kills']}/{p['deaths']}/{p['assists']}")
                    if p['win']:
                        wins += 1
                    else:
                        losses += 1

        match_result_box.configure(state="normal")
        match_result_box.delete(1.0, "end")
        if match_texts:
            match_result_box.insert("end", "\n".join(match_texts))
        else:
            match_result_box.insert("end", "오늘 경기 없음")
        match_result_box.configure(state="disabled")

        if losses > loss_limit:
            closed = close_lol_client()
            result = f"{wins}승 {losses}패 - 클라이언트 종료됨" if closed else f"{wins}승 {losses}패 - 종료 실패"
        else:
            result = f"{wins}승 {losses}패 - 계속 가능"

        status_label.configure(text=result)

    except Exception as e:
        status_label.configure(text=f"에러: {str(e)}")

# 패배 기준 설정
def change_loss_limit():
    global loss_limit
    new_val = simpledialog.askinteger("패배 한계 설정", "롤 클라이언트를 종료할 패배 수 (1~5):", minvalue=1, maxvalue=5)
    if new_val:
        loss_limit = new_val
        config['loss_limit'] = new_val
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        messagebox.showinfo("설정 완료", f"패배 한계가 {loss_limit}으로 변경되었습니다.")

# UI 구성
customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("blue")

app = customtkinter.CTk()
app.geometry("600x500")
app.title("찐막 (JinMak)")

title = customtkinter.CTkLabel(app, text="찐막 (JinMak)", font=("Pretendard", 24))
title.pack(pady=10)

status_label = customtkinter.CTkLabel(app, text="상태: 대기 중", font=("Pretendard", 16))
status_label.pack(pady=10)

check_button = customtkinter.CTkButton(app, text="오늘 전적 확인", command=check_losses)
check_button.pack(pady=5)

force_close_button = customtkinter.CTkButton(app, text="롤 클라 강제 종료", fg_color="red", command=lambda: (
    close_lol_client(),
    status_label.configure(text="롤 클라이언트 강제 종료됨")
))
force_close_button.pack(pady=5)

setting_button = customtkinter.CTkButton(app, text="설정 (패배 한계)", command=change_loss_limit)
setting_button.pack(pady=5)

match_result_box = customtkinter.CTkTextbox(app, height=250, width=550)
match_result_box.pack(pady=10)
match_result_box.insert("end", "아직 전적 정보가 없습니다.")
match_result_box.configure(state="disabled")

app.mainloop()
