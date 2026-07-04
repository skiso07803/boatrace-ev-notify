# -*- coding: utf-8 -*-
"""共通設定: 場コード・URL・EV閾値"""

BASE = "https://www.boatrace.jp/owpc/pc/race"

VENUES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津",   "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}

# コース別1着率の全国ベース(進入枠なり想定)
COURSE_BASE_WIN = {1: 0.55, 2: 0.14, 3: 0.12, 4: 0.11, 5: 0.06, 6: 0.02}

# EV判定(過去の設計方針を踏襲)
EV_RECOMMEND = 1.2   # これ以上のみ通知
EV_FORBID = 1.1      # これ未満は厳禁(表示もしない)

TAKEOUT = 0.25       # 控除率25%

TOP_N = 10

def racelist_url(jcd: str, rno: int, hd: str) -> str:
    return f"{BASE}/racelist?rno={rno}&jcd={jcd}&hd={hd}"

def odds3t_url(jcd: str, rno: int, hd: str) -> str:
    return f"{BASE}/odds3t?rno={rno}&jcd={jcd}&hd={hd}"

def raceindex_url(jcd: str, hd: str) -> str:
    return f"{BASE}/raceindex?jcd={jcd}&hd={hd}"

def index_url(hd: str) -> str:
    return f"{BASE}/index?hd={hd}"
