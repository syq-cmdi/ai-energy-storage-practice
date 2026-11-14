"""Editable, geometry-based causal flow and physical projection diagrams."""

from pathlib import Path
import argparse
import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle
from visual_style import setup, style, panel, save, plt, INK, MUTED

ROOT = Path(__file__).resolve().parents[2]
BLUE = "#2471A3"
TEAL = "#15958B"
ORANGE = "#D18429"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "assets/ch07")
    ap.add_argument("--font")
    a = ap.parse_args()
    setup(a.font)
    fig, ax = plt.subplots(figsize=(8, 5.1))
    fig.subplots_adjust(0.03, 0.03, 0.97, 0.97)
    ax.set(xlim=(0, 10), ylim=(0, 6))
    ax.axis("off")

    def box(x, y, w, h, title, sub, col):
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.08,rounding_size=.12",
                fc="white",
                ec=col,
                lw=1.5,
            )
        )
        ax.text(
            x + w / 2,
            y + h * 0.66,
            title,
            ha="center",
            va="center",
            fontweight="bold",
            color=col,
            fontsize=11,
        )
        ax.text(
            x + w / 2,
            y + h * 0.27,
            sub,
            ha="center",
            va="center",
            fontsize=9,
            color=MUTED,
        )

    def arrow(x, y, u, v, col=INK):
        ax.annotate(
            "",
            (u, v),
            (x, y),
            arrowprops=dict(arrowstyle="-|>", lw=1.4, color=col, mutation_scale=13),
        )

    box(0.2, 4.4, 2.3, 1.1, "当前观测", "需求 · 能量 · 上次功率", BLUE)
    box(3.3, 4.4, 2.6, 1.1, "三个候选控制器", "低通 / 优化 / Q学习", BLUE)
    box(6.7, 4.4, 3, 1.1, "共同约束投影", "额定功率 · 库存 · 爬坡", ORANGE)
    arrow(2.6, 4.95, 3.2, 4.95)
    arrow(6, 4.95, 6.6, 4.95)
    box(1, 2.25, 3, 1.15, "电池支路", "较大能量容量 · 平缓输出", BLUE)
    box(6, 2.25, 3, 1.15, "超级电容支路", "电压平方储能 · 快速响应", TEAL)
    arrow(7.5, 4.3, 7.5, 3.5, TEAL)
    ax.plot([6.9, 2.5], [4, 4], c=BLUE, lw=1.4)
    arrow(2.5, 4, 2.5, 3.5, BLUE)
    ax.plot([6.9, 6.9], [4.3, 4], c=BLUE, lw=1.4)
    ax.plot([2.5, 7.5], [1.65, 1.65], c=INK, lw=2)
    arrow(2.5, 2.15, 2.5, 1.65, BLUE)
    arrow(7.5, 2.15, 7.5, 1.65, TEAL)
    ax.text(
        5,
        1.85,
        "共同直流母线：电池功率 + 电容功率 + 残差 = 需求",
        ha="center",
        fontsize=9,
    )
    box(
        2.8,
        0.15,
        4.4,
        1,
        "逐时账本与独立评测",
        "跟踪 · 吞吐量 · 能量端点 · 约束事件",
        INK,
    )
    arrow(5, 1.65, 5, 1.25)
    ax.text(0.25, 5.85, "同一信息边界，同一物理环境", fontsize=13, fontweight="bold")
    save(fig, a.out, "fig7_02_system")
    fig, axs = plt.subplots(1, 2, figsize=(8, 4.3), layout="constrained")
    for ax, d, title in zip(
        axs,
        [70, 180],
        ["(a) 联合可行：沿需求直线投影", "(b) 需求超出边界：显式保留残差"],
    ):
        ax.add_patch(
            Rectangle((-80, -100), 160, 200, fc=BLUE, alpha=0.06, ec=BLUE, lw=1.4)
        )
        ax.add_patch(
            Rectangle((10, -100), 20, 200, fc=TEAL, alpha=0.18, ec=TEAL, lw=1.3)
        )
        x = np.linspace(-90, 90, 200)
        ax.plot(x, d - x, c=ORANGE, lw=1.8, label="功率平衡直线")
        ax.axvline(20, c=TEAL, lw=0.8, ls=":")
        req = 60
        pb = 30
        ps = min(100, d - pb)
        ax.scatter(
            [req], [d - req], marker="x", c=ORANGE, s=55, zorder=5, label="请求点"
        )
        ax.scatter([pb], [ps], c=TEAL, s=45, zorder=5, label="执行点")
        ax.annotate(
            "",
            (pb, ps),
            (req, d - req),
            arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.3),
        )
        if d == 180:
            ax.plot([30, 30], [100, 150], c="#BA4D4D", ls="--", lw=1.5)
            ax.text(33, 130, "50 kW\n残差", fontsize=9, color="#BA4D4D")
        ax.set(
            xlim=(-90, 90),
            ylim=(-120, 190),
            xlabel="电池功率 / kW",
            ylabel="超级电容功率 / kW",
        )
        ax.text(-75, -92, "电池爬坡窗口：10～30 kW", fontsize=8.5, color=TEAL)
        panel(ax, "", title)
        style(ax, "both")
    axs[0].legend(loc="upper left", frameon=False, fontsize=8.5)
    save(fig, a.out, "fig7_04_projection")


if __name__ == "__main__":
    main()
