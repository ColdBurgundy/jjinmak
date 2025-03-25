import customtkinter
import psutil
import requests
import datetime
import json
import os
import threading
import time
from tkinter import messagebox

CONFIG_FILE = 'config.json'
AUTO_CHECK_INTERVAL = 600  # 10분

QUEUE_ID_MAP = {
    420: "솔로랭크",
    430: "일반게임",
    440: "자유랭크",
    450: "칼바람 나락"
}


def load_or_create_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    required_keys = ['api_key', 'riot_id', 'loss_limit', 'auto_mode']
    if not all(k in config for k in required_keys):
        return None
    return config


def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4)


def get_puuid_from_riot_id(riot_id, api_key):
    try:
        if "#" not in riot_id:
            return None
        game_name, tag_line = riot_id.split("#")
        url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={api_key}"
        res = requests.get(url)
        if res.status_code != 200:
            return None
        return res.json().get("puuid")
    except:
        return None


def get_today_matches(puuid, api_key):
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    match_url = f'https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=10&api_key={api_key}'
    match_ids = requests.get(match_url).json()
    wins, losses = 0, 0
    logs = []

    for match_id in match_ids:
        detail_url = f'https://asia.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={api_key}'
        match_detail = requests.get(detail_url).json()
        info = match_detail['info']
        game_date = datetime.datetime.fromtimestamp(info['gameCreation'] / 1000).strftime('%Y-%m-%d')
        if game_date != today:
            continue

        queue_id = info.get("queueId", -1)
        game_mode = QUEUE_ID_MAP.get(queue_id, f"기타 ({queue_id})")

        for p in info['participants']:
            if p['puuid'] == puuid:
                result = "승" if p['win'] else "패"
                logs.append(f"[{game_mode}] {result} | 챔피언: {p['championName']} | {p['kills']}/{p['deaths']}/{p['assists']}")
                if p['win']:
                    wins += 1
                else:
                    losses += 1
    return wins, losses, logs


def close_lol_client():
    killed = False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and any(x in proc.info['name'].lower() for x in ['league', 'riot']):
                proc.kill()
                killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return killed


class JinMakApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("찐막 (JjinMak)")
        self.geometry("720x620")
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("blue")

        self.config_data = load_or_create_config()
        if not self.config_data:
            self.config_data = {
                "api_key": "",
                "riot_id": "",
                "loss_limit": 2,
                "auto_mode": False
            }
            save_config(self.config_data)

        self.puuid = get_puuid_from_riot_id(self.config_data["riot_id"], self.config_data["api_key"])

        self.auto_mode = customtkinter.BooleanVar(value=self.config_data["auto_mode"])

        self.init_ui()

        self.too_many_losses = False  # 패배 초과 여부 저장용 플래그

        if self.auto_mode.get():
            self.start_auto_check()

    def init_ui(self):
        self.title_label = customtkinter.CTkLabel(self, text="찐막 (JjinMak)", font=("맑은 고딕", 24, "bold"))
        self.title_label.pack(pady=10)

        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        self.date_label = customtkinter.CTkLabel(self, text=f"오늘 날짜: {today_str}", font=("맑은 고딕", 14))
        self.date_label.pack()

        self.info_label = customtkinter.CTkLabel(
            self,
            text=f"소환사: {self.config_data['riot_id']} | 패배 한계: {self.config_data['loss_limit']}패",
            font=("맑은 고딕", 14)
        )
        self.info_label.pack(pady=5)

        self.status_label = customtkinter.CTkLabel(self, text="상태: 대기 중", font=("맑은 고딕", 14))
        self.status_label.pack(pady=5)

        self.auto_check = customtkinter.CTkCheckBox(self, text="자동 종료 기능", variable=self.auto_mode, command=self.toggle_auto_mode)
        self.auto_check.pack(pady=5)

        button_frame = customtkinter.CTkFrame(self)
        button_frame.pack(pady=10)

        self.check_button = customtkinter.CTkButton(button_frame, text="오늘 전적 확인", command=self.check_losses)
        self.check_button.pack(side="left", padx=10)

        self.close_button = customtkinter.CTkButton(button_frame, text="클라이언트 종료", fg_color="red", command=self.manual_close)
        self.close_button.pack(side="left", padx=10)

        self.setting_button = customtkinter.CTkButton(button_frame, text="설정", command=self.open_settings)
        self.setting_button.pack(side="left", padx=10)

        self.result_box = customtkinter.CTkTextbox(self, height=300, width=680)
        self.result_box.pack(pady=10)
        self.result_box.insert("end", "전적 정보가 여기에 표시됩니다.")
        self.result_box.configure(state="disabled")

        self.update_button_state()

    def update_button_state(self):
        state = "disabled" if self.auto_mode.get() else "normal"
        self.check_button.configure(state=state)
        self.close_button.configure(state=state)

    def toggle_auto_mode(self):
        self.config_data["auto_mode"] = self.auto_mode.get()
        save_config(self.config_data)
        self.update_button_state()
        if self.auto_mode.get():
            self.start_auto_check()

    def check_losses(self):
        if not self.puuid:
            self.status_label.configure(text="PUUID 조회 실패")
            return

        wins, losses, logs = get_today_matches(self.puuid, self.config_data["api_key"])
        self.result_box.configure(state="normal")
        self.result_box.delete(1.0, "end")
        self.result_box.insert("end", "\n".join(logs) if logs else "오늘 경기 없음")
        self.result_box.configure(state="disabled")

        self.status_label.configure(text=f"오늘 전적: {wins}승 {losses}패")

        self.too_many_losses = losses > self.config_data["loss_limit"]  # 패배 초과 여부 저장

        if losses > self.config_data["loss_limit"]:
            if close_lol_client():
                self.status_label.configure(text=f"{losses}패 → 클라이언트 종료됨")
            else:
                self.status_label.configure(text=f"{losses}패 → 종료 실패")

    def manual_close(self):
        if close_lol_client():
            self.status_label.configure(text="클라이언트 강제 종료 완료")
        else:
            self.status_label.configure(text="클라이언트 종료 실패")

    def is_client_running(self):
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and 'league' in proc.info['name'].lower():
                    return True
            except:
                continue
        return False

    def start_auto_check(self):
        def auto_check_loop():
            while self.auto_mode.get():
                self.check_losses()
                time.sleep(AUTO_CHECK_INTERVAL)

        def monitor_client_loop():
            while True:
                if self.auto_mode.get() and self.too_many_losses and self.is_client_running():
                    closed = close_lol_client()
                    if closed:
                        self.status_label.configure(text="클라이언트 실시간 감지 → 종료됨")
                time.sleep(5)  # 클라 감시는 5초 간격

        # threading.Thread(target=loop, daemon=True).start()
        threading.Thread(target=auto_check_loop, daemon=True).start()
        threading.Thread(target=monitor_client_loop, daemon=True).start()

    def open_settings(self):
        if hasattr(self, "setting_panel") and self.setting_panel.winfo_exists():
            return  # 이미 열려있으면 무시

        self.setting_panel = customtkinter.CTkFrame(self, width=400, height=320, corner_radius=12)
        self.setting_panel.place(relx=0.5, rely=0.5, anchor="center")

        # 입력 필드
        riot_entry = customtkinter.CTkEntry(self.setting_panel, placeholder_text="Riot ID", width=300)
        riot_entry.insert(0, self.config_data["riot_id"])
        riot_entry.pack(pady=10)

        loss_option = customtkinter.CTkOptionMenu(self.setting_panel, values=["1", "2", "3", "4", "5"])
        loss_option.set(str(self.config_data["loss_limit"]))
        loss_option.pack(pady=10)

        auto_var = customtkinter.BooleanVar(value=self.config_data["auto_mode"])
        auto_check = customtkinter.CTkCheckBox(self.setting_panel, text="자동 종료 기능", variable=auto_var)
        auto_check.pack(pady=10)

        # 버튼 묶음
        def save():
            if not messagebox.askyesno("설정 저장", "변경 사항을 저장할까요?"):
                return
            self.config_data["riot_id"] = riot_entry.get()
            self.config_data["loss_limit"] = int(loss_option.get())
            self.config_data["auto_mode"] = auto_var.get()
            save_config(self.config_data)
            self.puuid = get_puuid_from_riot_id(self.config_data["riot_id"], self.config_data["api_key"])
            self.auto_mode.set(self.config_data["auto_mode"])
            self.info_label.configure(
                text=f"소환사: {self.config_data['riot_id']} | 패배 한계: {self.config_data['loss_limit']}패"
            )
            self.update_button_state()
            self.setting_panel.destroy()

        def cancel():
            self.setting_panel.destroy()

        button_frame = customtkinter.CTkFrame(self.setting_panel)
        button_frame.pack(pady=15)

        customtkinter.CTkButton(button_frame, text="저장", command=save).pack(side="left", padx=5)
        customtkinter.CTkButton(button_frame, text="취소", command=cancel).pack(side="left", padx=5)
        customtkinter.CTkButton(button_frame, text="닫기", command=self.setting_panel.destroy).pack(side="left", padx=5)




if __name__ == "__main__":
    app = JinMakApp()
    app.mainloop()
