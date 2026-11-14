"""Editable W-C1 functional boundary and receding-horizon teaching diagrams."""

from pathlib import Path
import argparse
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Ellipse
from visual_style import setup, save, INK, MUTED

ROOT = Path(__file__).resolve().parents[2]
BLUE, TEAL, AMBER, RED = "#3268B2", "#087F8C", "#C17D1F", "#BB4D4D"


def arrow(ax, a, b, color=BLUE, style="-", width=1.7):
    ax.add_patch(
        FancyArrowPatch(
            a,
            b,
            arrowstyle="-|>",
            mutation_scale=13,
            color=color,
            lw=width,
            linestyle=style,
        )
    )


def box(ax, x, y, w, h, title, body, color=BLUE):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            facecolor="white",
            edgecolor=color,
            lw=1.2,
        )
    )
    ax.text(
        x + w / 2,
        y + h - 0.055,
        title,
        ha="center",
        va="top",
        fontsize=11,
        color=color,
        weight="bold",
    )
    ax.text(
        x + w / 2,
        y + h - 0.12,
        body,
        ha="center",
        va="top",
        fontsize=9.2,
        color=INK,
        linespacing=1.7,
    )


def draw(out, font=None):
    setup(font)
    fig, ax = plt.subplots(figsize=(8.7, 5.3), layout="constrained")
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    ax.text(0.025, 0.96, "W-C1  供冷回路的功能边界", fontsize=14, weight="bold")
    box(
        ax,
        0.03,
        0.37,
        0.20,
        0.30,
        "冷水机组",
        "供冷能力 55 kW\n出口 6 ℃\nCOP 随气温变化",
        BLUE,
    )
    box(
        ax,
        0.77,
        0.37,
        0.20,
        0.30,
        "末端用冷",
        "供水上限 7 ℃\n回水基准 12 ℃\n未满足部分单独记录",
        TEAL,
    )
    # Tank: functional drawing, with explicit charge/discharge power arrows.
    ax.add_patch(
        FancyBboxPatch(
            (0.40, 0.28),
            0.20,
            0.43,
            boxstyle="round,pad=.006,rounding_size=.035",
            facecolor="#EDF2F5",
            edgecolor=INK,
            lw=1.2,
        )
    )
    ax.add_patch(
        Rectangle((0.415, 0.31), 0.17, 0.20, facecolor="#B8DCEB", edgecolor="none")
    )
    ax.add_patch(
        Rectangle((0.415, 0.51), 0.17, 0.16, facecolor="#D8E8DD", edgecolor="none")
    )
    ax.add_patch(
        Rectangle((0.415, 0.49), 0.17, 0.05, facecolor="#B9D8CE", edgecolor="none")
    )
    ax.text(0.50, 0.635, "分层储冷罐", ha="center", fontsize=11, weight="bold")
    ax.text(0.50, 0.56, "暖水区", ha="center", fontsize=9, color=MUTED)
    ax.text(0.50, 0.405, "冷水区", ha="center", fontsize=10, color=BLUE)
    ax.text(0.50, 0.34, "库存 E / kWh", ha="center", fontsize=9, color=INK)
    arrow(ax, (0.235, 0.49), (0.395, 0.49), BLUE)
    ax.text(0.315, 0.535, "充冷 c", ha="center", fontsize=10, color=BLUE)
    arrow(ax, (0.605, 0.49), (0.765, 0.49), TEAL)
    ax.text(0.685, 0.535, "放冷 d", ha="center", fontsize=10, color=TEAL)
    ax.plot([0.13, 0.13, 0.87], [0.675, 0.81, 0.81], color=BLUE, lw=1.7)
    arrow(ax, (0.87, 0.81), (0.87, 0.675), BLUE)
    ax.text(0.50, 0.835, "直接供冷 g", ha="center", fontsize=10, color=BLUE)
    # Common warm return represented as a dashed functional return route.
    ax.plot([0.87, 0.87, 0.13], [0.36, 0.17, 0.17], color=AMBER, lw=1.3, ls="--")
    arrow(ax, (0.13, 0.17), (0.13, 0.36), AMBER, style="--")
    ax.plot([0.5, 0.5], [0.275, 0.17], color=AMBER, lw=1.1, ls="--")
    ax.text(
        0.50,
        0.115,
        "回水侧基准 12 ℃；阀组与换热细节在扩展模型中展开",
        ha="center",
        fontsize=9,
        color=AMBER,
    )
    ax.text(
        0.5,
        0.035,
        "功率分配：g + d + u = L    ·    冷机约束：g + c ≤ 55 kW    ·    充放互斥",
        ha="center",
        fontsize=9.4,
        color=MUTED,
    )
    save(fig, out, "fig5_2_system")
    fig, ax = plt.subplots(figsize=(8.7, 5.4), layout="constrained")
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    ax.text(
        0.025, 0.96, "每小时更新状态与预测  只执行当前一步", fontsize=14, weight="bold"
    )
    specs = [
        (0.03, "① 读取当前信息", "负荷请求、天气\n冷量库存与出口温度", BLUE),
        (0.275, "② 更新未来预测", "训练模型保持冻结\n过去残差逐步衰减", TEAL),
        (0.52, "③ 求解规划", "设备、品质、库存\n末端条件与服务不足", AMBER),
        (0.765, "④ 执行与反馈", "执行第一个时段\n记录新状态与费用", BLUE),
    ]
    for x, t, b, c in specs:
        box(ax, x, 0.60, 0.205, 0.23, t, b, c)
    for x in [0.242, 0.488, 0.733]:
        arrow(ax, (x, 0.715), (x + 0.028, 0.715), INK)
    ax.plot([0.868, 0.868, 0.13, 0.13], [0.585, 0.53, 0.53, 0.585], color=MUTED, lw=1.1)
    arrow(ax, (0.13, 0.56), (0.13, 0.585), MUTED)
    ax.text(
        0.50,
        0.485,
        "下一时刻：用实际状态重新求解",
        ha="center",
        fontsize=10,
        color=MUTED,
    )
    x0 = 0.24
    step = 0.075
    for row, label, start in [(0, "k 时刻", 0), (1, "k+1 时刻", 1), (2, "k+2 时刻", 2)]:
        y = 0.35 - row * 0.095
        ax.text(0.06, y + 0.027, label, va="center", fontsize=10)
        for j in range(8):
            col = "#DDE5EC" if j < start else ("#087F8C" if j == start else "#D5E9E8")
            ax.add_patch(
                Rectangle(
                    (x0 + j * step, y),
                    step - 0.006,
                    0.058,
                    facecolor=col,
                    edgecolor="white",
                    lw=0.6,
                )
            )
        ax.text(
            x0 + start * step + 0.034,
            y + 0.028,
            "执行",
            ha="center",
            va="center",
            fontsize=8,
            color="white",
        )
        if row == 0:
            ax.text(
                0.62,
                y + 0.029,
                "未来计划",
                ha="center",
                va="center",
                fontsize=9,
                color=TEAL,
            )
    ax.text(
        0.50,
        0.035,
        "当前请求已知；未来实测负荷留待评分；缩短时域会改变预充冷机会",
        ha="center",
        fontsize=9.4,
        color=MUTED,
    )
    save(fig, out, "fig5_7_rolling")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch05")
    p.add_argument("--font", type=Path)
    a = p.parse_args()
    draw(a.out, a.font)
