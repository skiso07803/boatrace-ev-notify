# -*- coding: utf-8 -*-
"""朝8時バッチ: 全開催場の全レースを走査し、暫定EV TOP10をDiscordへ

前売オッズはまだ薄く、締切までに大きく変動する前提の「参考情報」。
オッズ未発売のレースはスキップする。
実行: python -m src.morning_batch
"""
from .config import VENUES, EV_RECOMMEND, TOP_N
from .scraper import today_hd, fetch_active_venues, fetch_racecard, fetch_odds3t
from .model import evaluate
from .notify import send, ev_embed


def main() -> None:
    hd = today_hd()
    venues = fetch_active_venues(hd)
    if not venues:
        send(f"📭 {hd}: 開催場を取得できませんでした(サイト構造変化の可能性)")
        return

    all_hits = []  # (venue, rno, EVResult)
    scanned = skipped = 0
    for jcd in venues:
        for rno in range(1, 13):
            card = fetch_racecard(jcd, rno, hd)
            if card is None:
                skipped += 1
                continue
            odds = fetch_odds3t(jcd, rno, hd)
            if len(odds) < 100:  # 未発売 or 取得失敗
                skipped += 1
                continue
            scanned += 1
            for res in evaluate(card, odds):
                if res.ev >= EV_RECOMMEND:
                    all_hits.append((VENUES[jcd], rno, res))

    all_hits.sort(key=lambda x: x[2].ev, reverse=True)
    top = all_hits[:TOP_N]

    header = (
        f"🌅 **{hd[:4]}/{hd[4:6]}/{hd[6:]} 朝の暫定EVレポート**\n"
        f"開催{len(venues)}場 / 解析{scanned}R / オッズ未発売等スキップ{skipped}R\n"
        f"⚠️ 前売オッズ基準の暫定値です。締切直前に確定版を再通知します。"
    )
    if not top:
        send(header + f"\n\nEV≥{EV_RECOMMEND}の買い目は現時点でありません。")
        return

    send(header, embeds=[ev_embed(v, r, res, provisional=True) for v, r, res in top])


if __name__ == "__main__":
    main()
