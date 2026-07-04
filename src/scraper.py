# -*- coding: utf-8 -*-
"""boatrace.jp スクレイパー

取得対象:
  1. 本日の開催場一覧      (race/index)
  2. 各場のレース締切時刻   (race/raceindex)
  3. 出走表(選手/モーター) (race/racelist)
  4. 3連単オッズ           (race/odds3t)

※ HTML構造は変更される可能性があるため、各parse関数は
   失敗時に None / 空 を返し、呼び出し側でスキップする設計。
   `python -m src.scraper` で本日のデータ取得テストができる。
"""
import re
import time
import datetime as dt
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

from .config import VENUES, racelist_url, odds3t_url, raceindex_url, index_url

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
}
SLEEP = 1.0  # サーバー負荷配慮。1リクエスト1秒以上あける


def _get(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        time.sleep(SLEEP)
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[WARN] fetch failed: {url} ({e})")
        return None


def today_hd() -> str:
    jst = dt.timezone(dt.timedelta(hours=9))
    return dt.datetime.now(jst).strftime("%Y%m%d")


# ---------------------------------------------------------------- 開催場一覧
def fetch_active_venues(hd: str) -> list[str]:
    """本日開催中の場コード一覧を返す"""
    soup = _get(index_url(hd))
    if soup is None:
        return []
    codes = set()
    for a in soup.select("a[href*='jcd=']"):
        m = re.search(r"jcd=(\d{2})", a.get("href", ""))
        if m and m.group(1) in VENUES:
            codes.add(m.group(1))
    return sorted(codes)


# ---------------------------------------------------------------- 締切時刻
def fetch_deadlines(jcd: str, hd: str) -> dict[int, dt.datetime]:
    """{レース番号: 締切予定時刻(JST)} を返す"""
    soup = _get(raceindex_url(jcd, hd))
    if soup is None:
        return {}
    jst = dt.timezone(dt.timedelta(hours=9))
    base = dt.datetime.strptime(hd, "%Y%m%d").replace(tzinfo=jst)
    out: dict[int, dt.datetime] = {}
    # レース番号行に「HH:MM」形式の締切時刻が並ぶ想定
    for row in soup.select("tbody tr"):
        text = row.get_text(" ", strip=True)
        mr = re.search(r"(\d{1,2})R", text)
        mt = re.search(r"(\d{1,2}):(\d{2})", text)
        if mr and mt:
            rno = int(mr.group(1))
            if 1 <= rno <= 12 and rno not in out:
                out[rno] = base.replace(hour=int(mt.group(1)), minute=int(mt.group(2)))
    return out


# ---------------------------------------------------------------- 出走表
@dataclass
class Racer:
    lane: int              # 枠番(進入は枠なり想定)
    name: str = ""
    grade: str = ""        # A1/A2/B1/B2
    win_rate: float = 0.0  # 全国勝率
    motor_rate: float = 0.0  # モーター2連率(%)
    st_avg: float = 0.20   # 平均ST


@dataclass
class RaceCard:
    jcd: str
    rno: int
    hd: str
    racers: list[Racer] = field(default_factory=list)

    @property
    def venue(self) -> str:
        return VENUES.get(self.jcd, self.jcd)


def fetch_racecard(jcd: str, rno: int, hd: str) -> RaceCard | None:
    soup = _get(racelist_url(jcd, rno, hd))
    if soup is None:
        return None
    card = RaceCard(jcd=jcd, rno=rno, hd=hd)

    # 出走表は枠ごとに tbody が分かれている構造(2026年時点)
    tbodies = soup.select("div.table1 table tbody")
    for tb in tbodies:
        text = tb.get_text(" ", strip=True)
        m_lane = re.match(r"\s*([1-6])\s", text)
        if not m_lane:
            continue
        lane = int(m_lane.group(1))
        r = Racer(lane=lane)

        m = re.search(r"(A1|A2|B1|B2)", text)
        if m:
            r.grade = m.group(1)
        # 選手名(全角スペース含む日本語名)
        m = re.search(r"(A1|A2|B1|B2)\s+([\u4e00-\u9fff\u3040-\u30ffー]+[\s　]*[\u4e00-\u9fff\u3040-\u30ffー]+)", text)
        if m:
            r.name = m.group(2).replace("　", "").replace(" ", "")
        # 数値群: 全国勝率(x.xx) → 2連率 → …の順に並ぶ想定。
        nums = re.findall(r"\d+\.\d{2}", text)
        if nums:
            r.win_rate = float(nums[0])
        # モーター2連率: "モーター番号 2連率%" のパターンから推定
        m = re.search(r"(\d{1,3})\s+(\d{1,2}\.\d{2})\s+\d{1,3}\s+\d{1,2}\.\d{2}\s*$", text)
        if m:
            r.motor_rate = float(m.group(2))
        else:
            # フォールバック: 30-70%帯の数値をモーター2連率候補とみなす
            cand = [float(x) for x in nums if 15.0 <= float(x) <= 80.0]
            if cand:
                r.motor_rate = cand[-1]
        # 平均ST(.xx 形式)
        m = re.search(r"0?\.(1[0-9]|2[0-5])\b", text)
        if m:
            r.st_avg = float("0." + m.group(1))

        card.racers.append(r)

    if len(card.racers) != 6:
        print(f"[WARN] racelist parse incomplete: {jcd} {rno}R -> {len(card.racers)}艇")
        return None
    card.racers.sort(key=lambda x: x.lane)
    return card


# ---------------------------------------------------------------- 3連単オッズ
def fetch_odds3t(jcd: str, rno: int, hd: str) -> dict[tuple[int, int, int], float]:
    """{(1着,2着,3着): オッズ} を返す。未発売なら空dict"""
    soup = _get(odds3t_url(jcd, rno, hd))
    if soup is None:
        return {}
    odds: dict[tuple[int, int, int], float] = {}

    # オッズ表: 1着(列ブロック6つ) × 2着 × 3着 のマトリクス構造。
    # セル順序依存を避けるため、行内の「艇番 → オッズ値」ペアを走査する。
    table = soup.select_one("div.table1 table")
    if table is None:
        return {}
    rows = table.select("tbody tr")
    # 2着艇はrowspanで省略されるため列ブロックごとに状態を保持
    current_second = [0] * 6  # 1着=1..6 の各ブロックの現在の2着艇
    for row in rows:
        tds = row.select("td")
        block = 0  # 何番目の1着ブロックか(左から 1着=1,2,...,6)
        i = 0
        while i < len(tds) and block < 6:
            cls = tds[i].get("class") or []
            txt = tds[i].get_text(strip=True)
            if "is-fs14" in cls and txt.isdigit():  # 2着艇番セル(rowspan)
                current_second[block] = int(txt)
                i += 1
                continue
            if txt.isdigit() and i + 1 < len(tds):  # 3着艇番セル
                third = int(txt)
                val = tds[i + 1].get_text(strip=True).replace(",", "")
                try:
                    o = float(val)
                    first = block + 1
                    second = current_second[block]
                    if second and len({first, second, third}) == 3:
                        odds[(first, second, third)] = o
                except ValueError:
                    pass
                i += 2
                block += 1
                continue
            i += 1

    if len(odds) < 100:  # 3連単は120通り。大きく欠けていたら未発売/構造変化とみなす
        print(f"[WARN] odds3t parse: {jcd} {rno}R -> {len(odds)}通りのみ取得")
    return odds


# ---------------------------------------------------------------- 動作テスト
if __name__ == "__main__":
    hd = today_hd()
    print(f"=== {hd} 開催場 ===")
    venues = fetch_active_venues(hd)
    print([f"{c}:{VENUES[c]}" for c in venues])
    if venues:
        jcd = venues[0]
        print(f"\n=== {VENUES[jcd]} 締切時刻 ===")
        print(fetch_deadlines(jcd, hd))
        print(f"\n=== {VENUES[jcd]} 1R 出走表 ===")
        card = fetch_racecard(jcd, 1, hd)
        if card:
            for r in card.racers:
                print(vars(r))
        print(f"\n=== {VENUES[jcd]} 1R オッズ(取得数) ===")
        od = fetch_odds3t(jcd, 1, hd)
        print(len(od), "通り")
        for k in list(od)[:5]:
            print(k, od[k])
