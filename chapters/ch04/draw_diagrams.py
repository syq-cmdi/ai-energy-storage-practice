"""Editable engineering schematics; vector text plus 600-dpi export."""

from pathlib import Path
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import (
    FancyBboxPatch,
    Rectangle,
    Ellipse,
    FancyArrowPatch,
    Circle,
)
from visual_style import setup, save, INK, MUTED

ROOT = Path(__file__).resolve().parents[2]
TEAL, BLUE, AMBER, PURPLE, RED = "#087F8C", "#3268B2", "#C17D1F", "#7954A1", "#BB4D4D"


def box(ax, x, y, w, h, title, body, color):
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
        x + 0.025,
        y + h - 0.045,
        title,
        color=color,
        fontsize=11,
        weight="bold",
        va="top",
    )
    ax.text(
        x + 0.025,
        y + h - 0.105,
        body,
        color=INK,
        fontsize=9.4,
        va="top",
        linespacing=1.6,
    )


def arrow(ax, start, end, color=INK, style="-", width=1.4):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=13,
            lw=width,
            color=color,
            linestyle=style,
        )
    )


def draw(out, font=None):
    setup(font)
    fig, ax = plt.subplots(figsize=(8.7, 5.3), layout="constrained")
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    ax.text(
        0.02,
        0.965,
        "W-H1  固定水质量的储热实验边界",
        fontsize=14,
        color=INK,
        weight="bold",
    )
    # Tank and uniform mixed water. No fluid inlet/outlet is drawn.
    ax.add_patch(
        FancyBboxPatch(
            (0.345, 0.17),
            0.30,
            0.64,
            boxstyle="round,pad=0.016,rounding_size=0.065",
            facecolor="#EEF2F5",
            edgecolor=INK,
            lw=1.4,
        )
    )
    ax.add_patch(
        Rectangle(
            (0.363, 0.235), 0.264, 0.48, facecolor="#F8E2AC", edgecolor=AMBER, lw=0.8
        )
    )
    ax.add_patch(
        Ellipse(
            (0.495, 0.715), 0.264, 0.055, facecolor="#F9EBC8", edgecolor=AMBER, lw=0.9
        )
    )
    ax.add_patch(
        Ellipse(
            (0.495, 0.235), 0.264, 0.055, facecolor="#F3CE82", edgecolor=AMBER, lw=0.9
        )
    )
    ax.plot([0.48, 0.48], [0.85, 0.34], color=MUTED, lw=2.5)
    for y in [0.42, 0.59]:
        ax.plot([0.435, 0.525], [y - 0.018, y + 0.018], color=TEAL, lw=3)
    ax.add_patch(Rectangle((0.445, 0.81), 0.07, 0.065, facecolor=INK))
    ax.text(0.49, 0.90, "搅拌", ha="center", fontsize=10, color=MUTED)
    coilx = np.linspace(0.39, 0.60, 150)
    ax.plot(
        coilx, 0.30 + 0.018 * np.sin(np.linspace(0, 10 * np.pi, 150)), color=RED, lw=2.4
    )
    for x, y, lab in [(0.56, 0.63, "上"), (0.585, 0.51, "中"), (0.61, 0.39, "下")]:
        ax.plot([x, x], [0.79, y], color=BLUE, lw=1.3)
        ax.add_patch(Circle((x, y), 0.008, color=BLUE))
        ax.text(x + 0.012, y + 0.025, lab, fontsize=8.7, color=BLUE, va="center")
    ax.add_patch(
        FancyBboxPatch(
            (0.325, 0.14),
            0.34,
            0.70,
            boxstyle="round,pad=0.02",
            fill=False,
            edgecolor=TEAL,
            lw=1.1,
            linestyle="--",
        )
    )
    ax.text(0.49, 0.075, "水体边界  m = 100 kg", ha="center", color=TEAL, fontsize=10)
    arrow(ax, (0.14, 0.30), (0.38, 0.30), RED, width=2)
    ax.text(0.04, 0.34, "有效热输入 u / kW", fontsize=10, color=RED)
    arrow(ax, (0.64, 0.62), (0.81, 0.62), AMBER, width=2)
    ax.text(0.69, 0.66, "散热 UA(T − $T_a$)", fontsize=10, color=AMBER)
    box(
        ax,
        0.035,
        0.54,
        0.23,
        0.21,
        "观测设计",
        "中层探头用于估计\n上下探头检查混合\n环境探头记录 $T_a$",
        BLUE,
    )
    arrow(ax, (0.59, 0.52), (0.73, 0.45), BLUE, style="--")
    box(
        ax,
        0.73,
        0.26,
        0.245,
        0.22,
        "测量链",
        "温度 y / ℃\n时间戳 t / s\n已知输入 u 与 $T_a$",
        BLUE,
    )
    ax.text(
        0.50,
        0.035,
        "C = 418 kJ/K    UA = 0.010 kW/K    无进出水    忽略罐壁热容量",
        ha="center",
        fontsize=9.2,
        color=MUTED,
    )
    save(fig, out, "fig4_2_boundary")

    fig, ax = plt.subplots(figsize=(8.7, 5.8), layout="constrained")
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    ax.text(
        0.025,
        0.97,
        "从校准到独立验证 保持数据用途清晰",
        fontsize=14,
        color=INK,
        weight="bold",
    )
    specs = [
        (0.035, 0.69, "① 机理校准", "2 条 × 24 h\n拟合 C、UA 与各条初温", BLUE),
        (0.365, 0.69, "② 残差训练", "2 条 × 18 h\n固定 C、UA，学习 β", TEAL),
        (0.695, 0.69, "③ 模型选择", "12 h + 18 h\n比较适用工况，选择 Q", PURPLE),
    ]
    for x, y, title, body, col in specs:
        box(ax, x, y, 0.27, 0.20, title, body, col)
    arrow(ax, (0.31, 0.79), (0.35, 0.79))
    arrow(ax, (0.64, 0.79), (0.68, 0.79))
    ax.plot([0.04, 0.96], [0.63, 0.63], ls="--", color=MUTED, lw=1)
    ax.text(0.50, 0.645, "参数与选择结果冻结", ha="center", fontsize=9.5, color=MUTED)
    box(
        ax,
        0.04,
        0.34,
        0.265,
        0.22,
        "④ 独立测试",
        "常规 · 附加散热\n传感器偏移 · 高温外推",
        AMBER,
    )
    box(
        ax,
        0.365,
        0.34,
        0.27,
        0.22,
        "⑤ 同输入对照",
        "开环：机理 / 灰箱\n估计：KF / EKF",
        TEAL,
    )
    box(
        ax,
        0.695,
        0.34,
        0.265,
        0.22,
        "⑥ 双重核验",
        "温度误差与区间覆盖\n开环能量残差",
        BLUE,
    )
    arrow(ax, (0.83, 0.68), (0.83, 0.59), PURPLE)
    arrow(ax, (0.83, 0.59), (0.17, 0.59), PURPLE)
    arrow(ax, (0.17, 0.59), (0.17, 0.565), PURPLE)
    arrow(ax, (0.31, 0.45), (0.35, 0.45))
    arrow(ax, (0.64, 0.45), (0.68, 0.45))
    ax.text(0.045, 0.23, "每个采样步的灰箱预测", fontsize=11, weight="bold", color=INK)
    ax.text(0.045, 0.16, "已知输入与上一状态", fontsize=10, color=BLUE)
    arrow(ax, (0.275, 0.175), (0.33, 0.175), BLUE)
    ax.text(0.345, 0.16, "机理热流 + 学得残差", fontsize=10, color=TEAL)
    arrow(ax, (0.635, 0.175), (0.69, 0.175), TEAL)
    ax.text(0.705, 0.16, "积分 → 预测 → 观测校正", fontsize=10, color=INK)
    ax.text(
        0.50,
        0.055,
        "参考温度与参考热量用于最终评分；拟合和选参只访问允许的观测字段",
        ha="center",
        fontsize=9.4,
        color=MUTED,
    )
    save(fig, out, "fig4_6_protocol")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch04")
    p.add_argument("--font", type=Path)
    a = p.parse_args()
    draw(a.out, a.font)
