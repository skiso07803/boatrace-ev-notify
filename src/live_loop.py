# -*- coding: utf-8 -*-
"""直前確定版ループ: 各レース締切N分前に最新オッズでEVを再計算して通知

GitHub Actionsの1ジョブとして起動し、MAX_HOURS経過で自然終了する。
午前ジョブ・午後ジョブの2本で1日をカバーする想定。
実行: python -m src.live_loop
"""
import os
import time
import datetime as dt

from .config import VENUES, EV_RECOMMEND, TOP_N
from .scraper import (today_hd, fetch_active_venues, fetch_deadlines,
                      fetch_racecard, fetch_odds3t)
from .model import evaluate
from .notify import send, ev_embed

LEAD_MIN = int(os.environ.get("LEAD_MIN", "8"))       # 締切何分前に判定するか
MAX_HOURS = float(os.environ.get("MAX_HOURS", "5.5"))  # ジョブ最大稼働時間
POLL_SEC = 60

JST = dt.timezone(dt.timedelta(hours=9))


def main() -> None:
    hd = today_hd()
    start = time.time()

    # 本日の全レースの締切時刻を収集
    schedule: list[tuple[str, int, dt.datetime]] = []
    for jcd in fetch_active_venues(hd):
        for rno, deadline in fetch_deadlines(jcd, hd).items():
            schedule.append((jcd, rno, deadline))
    schedule.sort(key=lambda x: x[2])
    print(f"[INFO] {len(schedule)}レースを監視対象に登録")

    notified: set[tuple[str, int]] = set()

    while time.time() - start < MAX_HOURS * 3600:
        now = dt.datetime.now(JST)
        remaining = [s for s in schedule if (s[0], s[1]) not in notified
                     and s[2] > now]
        if not remaining:
            print("[INFO] 監視対象なし。終了")
            break

        for jcd, rno, deadline in remaining:
            lead = (deadline - now).total_seconds() / 60
            if lead > LEAD_MIN:
                continue  # まだ早い
            notified.add((jcd, rno))
            if lead < 1:
                continue  # 締切ギリギリすぎ→スキップ

            card = fetch_racecard(jcd, rno, hd)
            odds = fetch_odds3t(jcd, rno, hd) if card else {}
            if not card or len(odds) < 100:
                continue
            hits = [r for r in evaluate(card, odds) if r.ev >= EV_RECOMMEND][:3]
            if not hits:
                continue  # EV不足のレースは静かにスルー(通知疲れ防止)
            send(
                f"⏰ **{VENUES[jcd]} {rno}R** 締切 {deadline:%H:%M}(あと約{lead:.0f}分)",
                embeds=[ev_embed(VENUES[jcd], rno, h, provisional=False) for h in hits],
            )
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
