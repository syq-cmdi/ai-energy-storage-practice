"""Precise original system and receding-horizon diagrams."""

from pathlib import Path
import argparse
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from visual_style import setup, save, INK, MUTED

ROOT = Path(__file__).resolve().parents[2]
BLUE = "#4676B5"
TEAL = "#148B89"
ORANGE = "#CF893B"
PURPLE = "#8F75AE"


def box(ax, x, y, w, h, title, body, color):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=.02,rounding_size=.12",
            ec=color,
            fc=color + "12",
            lw=1.4,
        )
    )
    ax.text(
        x + w / 2,
        y + h * 0.68,
        title,
        ha="center",
        va="center",
        color=color,
        weight="bold",
        fontsize=12,
    )
    ax.text(
        x + w / 2,
        y + h * 0.28,
        body,
        ha="center",
        va="center",
        color=INK,
        fontsize=10.5,
        linespacing=1.5,
    )


def arrow(ax, x1, y1, x2, y2, c=TEAL):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, color=c, lw=1.6
        )
    )


def main(out, font=None):
    setup(font)
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.set(xlim=(0, 10), ylim=(0, 6))
    ax.axis("off")
    fig.subplots_adjust(0.02, 0.02, 0.98, 0.98)
    box(ax, 0.25, 4.5, 3.05, 1.05, "可再生电源", "已知/预测输入 R，单位 kW", BLUE)
    box(ax, 6.7, 4.5, 3.05, 1.05, "电网接入", "购电 g 与接入上限", BLUE)
    ax.plot([1.8, 1.8, 8.2, 8.2], [4.5, 4, 4, 4.5], color=BLUE, lw=1.6)
    ax.text(
        5, 4.12, "电功率母线：电解 + 压缩 + 辅助", ha="center", color=BLUE, fontsize=11
    )
    for x in [1.35, 3.8]:
        arrow(ax, x, 4, x, 3.25, BLUE)
    box(ax, 0.2, 1.9, 2.3, 1.35, "电解单元", "P → q = P / 55", BLUE)
    box(ax, 2.9, 1.9, 1.8, 1.35, "压缩机", "3q kW", ORANGE)
    box(ax, 5.1, 1.9, 2.3, 1.35, "质量库存", "20 ≤ m ≤ 80 kg", TEAL)
    box(ax, 7.8, 1.9, 2, 1.35, "用氢需求", "已供 + 缺供", PURPLE)
    for a, b in [(2.5, 2.9), (4.7, 5.1), (7.4, 7.8)]:
        arrow(ax, a, 2.55, b, 2.55)
    box(
        ax,
        0.8,
        0.25,
        8.4,
        0.95,
        "两条账本，逐步核对",
        "电能：kW × h → kWh       氢质量：kg/h × h → kg",
        MUTED,
    )
    save(fig, out, "fig08_02_system_boundary")
    fig, ax = plt.subplots(figsize=(7.6, 3.9))
    ax.set(xlim=(0, 10), ylim=(0, 5))
    ax.axis("off")
    fig.subplots_adjust(0.02, 0.02, 0.98, 0.98)
    for y, title in [(3.7, "当前求解"), (2.4, "1 h后更新"), (1.1, "继续滚动")]:
        ax.text(0.1, y + 0.32, title, fontsize=11, color=INK)
    for j, y in enumerate([3.7, 2.4, 1.1]):
        start = 2 + j * 0.85
        ax.add_patch(
            FancyBboxPatch(
                (start, y),
                5.1,
                0.65,
                boxstyle="round,pad=.02",
                ec=BLUE,
                fc="#EDF3FA",
                lw=1,
            )
        )
        ax.add_patch(
            FancyBboxPatch(
                (start, y),
                0.85,
                0.65,
                boxstyle="round,pad=.02",
                ec=TEAL,
                fc="#C5E4DC",
                lw=1,
            )
        )
        ax.text(
            start + 0.425,
            y + 0.32,
            "执行",
            ha="center",
            va="center",
            fontsize=10,
            color=TEAL,
        )
        ax.text(
            start + 2.9,
            y + 0.32,
            "6 h 预测窗口 · 24个步长",
            ha="center",
            va="center",
            fontsize=10,
            color=BLUE,
        )
        if j < 2:
            arrow(ax, start + 0.85, y - 0.03, start + 0.85, y - 0.6, ORANGE)
    ax.text(
        5,
        0.45,
        "每1 h重算；每15 min执行；未来输入采用当前可得预测",
        ha="center",
        fontsize=11,
        color=INK,
    )
    ax.text(
        5,
        4.75,
        "可见信息：当前观测 + 既定日历预测 + 当前库存",
        ha="center",
        fontsize=12,
        weight="bold",
        color=INK,
    )
    save(fig, out, "fig08_07_rolling_timeline")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch08")
    p.add_argument("--font")
    a = p.parse_args()
    main(a.out, a.font)
