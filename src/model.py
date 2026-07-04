# -*- coding: utf-8 -*-
"""確率モデル + EV計算 + 理由の自動生成

1着確率: コース別基礎勝率 × 選手勝率補正 × モーター補正 × ST補正 → 正規化
3連単確率: Plackett-Luce (逐次抽出) で近似
EV = 予測確率 × オッズ
"""
from dataclasses import dataclass
from itertools import permutations

from .config import COURSE_BASE_WIN, TAKEOUT
from .scraper import RaceCard, Racer


def _strength(r: Racer, mean_win: float, mean_motor: float) -> float:
    """艇の強さスコア(コース基礎 × 選手 × モーター × ST)"""
    base = COURSE_BASE_WIN[r.lane]
    # 選手勝率補正: 全国平均~5.0を基準に ±30% 程度で効かせる
    win_adj = 1.0 + 0.30 * ((r.win_rate - mean_win) / max(mean_win, 1e-6))
    # モーター補正: 出走メンバー平均比 ±20%
    motor_adj = 1.0 + 0.20 * ((r.motor_rate - mean_motor) / max(mean_motor, 1e-6))
    # ST補正: 平均0.17基準。0.01速いごとに+4%
    st_adj = 1.0 + 4.0 * (0.17 - r.st_avg)
    return max(base * win_adj * motor_adj * st_adj, 1e-4)


def win_probs(card: RaceCard) -> dict[int, float]:
    mean_win = sum(r.win_rate for r in card.racers) / 6
    mean_motor = sum(r.motor_rate for r in card.racers) / 6 or 1.0
    s = {r.lane: _strength(r, mean_win, mean_motor) for r in card.racers}
    total = sum(s.values())
    return {k: v / total for k, v in s.items()}


def trifecta_probs(card: RaceCard) -> dict[tuple[int, int, int], float]:
    """Plackett-Luce: P(a,b,c) = pa * pb/(1-pa) * pc/(1-pa-pb)"""
    p = win_probs(card)
    out = {}
    for a, b, c in permutations(range(1, 7), 3):
        pa, pb, pc = p[a], p[b], p[c]
        out[(a, b, c)] = pa * (pb / (1 - pa)) * (pc / (1 - pa - pb))
    return out


@dataclass
class EVResult:
    combo: tuple[int, int, int]
    ev: float
    p_model: float
    odds: float
    reasons: list[str]

    @property
    def label(self) -> str:
        return "-".join(map(str, self.combo))


def _reasons(card: RaceCard, combo: tuple[int, int, int],
             p_model: float, odds: float, probs: dict[int, float]) -> list[str]:
    rs: list[str] = []
    p_implied = (1.0 / odds) * (1 - TAKEOUT)  # 控除率調整後の市場想定確率
    if p_implied > 0:
        gap = p_model / p_implied
        rs.append(f"モデル確率{p_model*100:.1f}% vs 市場想定{p_implied*100:.1f}%(乖離{gap:.1f}倍)")

    head = next(r for r in card.racers if r.lane == combo[0])
    mean_motor = sum(r.motor_rate for r in card.racers) / 6 or 1.0

    if head.motor_rate >= mean_motor * 1.15 and head.motor_rate >= 40:
        rs.append(f"頭{head.lane}号艇のモーター2連率{head.motor_rate:.0f}%はメンバー中上位")
    if head.st_avg <= 0.15:
        rs.append(f"頭{head.lane}号艇の平均ST{head.st_avg:.2f}は速く先手を取りやすい")

    # 1号艇過剰人気の逆張り(既知バイアス)
    one = next(r for r in card.racers if r.lane == 1)
    if combo[0] != 1 and probs[1] < 0.45:
        note = f"1号艇の信頼度がモデル上{probs[1]*100:.0f}%と低め"
        if one.grade == "A1":
            note += "(A1ブランドで売れすぎの可能性)"
        rs.append(note + "で妙味は他艇に")
    if combo[0] == 1 and probs[1] > 0.60:
        rs.append(f"1号艇の実力が市場評価以上(モデル{probs[1]*100:.0f}%)")

    return rs[:3]


def evaluate(card: RaceCard,
             odds: dict[tuple[int, int, int], float]) -> list[EVResult]:
    """EV降順の全買い目評価(閾値フィルタは呼び出し側で)"""
    tri = trifecta_probs(card)
    probs = win_probs(card)
    results = []
    for combo, p in tri.items():
        o = odds.get(combo)
        if not o or o <= 1.0:
            continue
        ev = p * o
        results.append(EVResult(
            combo=combo, ev=round(ev, 2), p_model=p, odds=o,
            reasons=_reasons(card, combo, p, o, probs),
        ))
    results.sort(key=lambda x: x.ev, reverse=True)
    return results
