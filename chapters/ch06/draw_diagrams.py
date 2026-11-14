"""Editable functional diagrams for Chapter 6; all geometry authored in code."""

from pathlib import Path
import argparse
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch, Circle
from visual_style import setup, save, INK, MUTED

ROOT = Path(__file__).resolve().parents[2]
BLUE = "#3268B2"
TEAL = "#087F8C"
AMBER = "#C17D1F"
PURPLE = "#7954A1"


def box(ax, x, y, w, h, title, body="", color=TEAL):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=.008,rounding_size=.025",
            fc="white",
            ec=color,
            lw=1.5,
        )
    )
    ax.text(
        x + w / 2,
        y + h * 0.76,
        title,
        ha="center",
        va="center",
        color=color,
        fontsize=11,
        weight="bold",
    )
    ax.text(
        x + w / 2,
        y + h * 0.34,
        body,
        ha="center",
        va="center",
        fontsize=9.3,
        linespacing=1.6,
    )


def arrow(ax, a, b, color=INK, rad=0, style="-|>"):
    ax.add_patch(
        FancyArrowPatch(
            a,
            b,
            arrowstyle=style,
            mutation_scale=13,
            lw=1.4,
            color=color,
            connectionstyle=f"arc3,rad={rad}",
        )
    )


def canvas(size=(7.5, 4.5)):
    fig, ax = plt.subplots(figsize=size)
    ax.set(xlim=(0, 1), ylim=(0, 1))
    ax.axis("off")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
    return fig, ax


def draw(out, font=None):
    setup(font)
    out = Path(out)
    fig, ax = canvas()
    ax.text(
        0.04,
        0.94,
        "水量守恒连接两个水库  电能转换经过同一台机组",
        fontsize=12,
        weight="bold",
    )
    # Water surfaces and levels are functional, not scaled construction geometry.
    for x, y, w, h, label, col in [
        (0.06, 0.59, 0.29, 0.25, "上水库", BLUE),
        (0.67, 0.13, 0.28, 0.25, "下水库", TEAL),
    ]:
        ax.add_patch(Rectangle((x, y), w, h, fc="#F0F5F8", ec=MUTED, lw=1.2))
        ax.add_patch(
            Rectangle(
                (x + 0.006, y + 0.006), w - 0.012, h * 0.62, fc="#B5DCEB", ec="none"
            )
        )
        ax.plot([x, x + w], [y + h * 0.64] * 2, color=col, lw=1.6)
        ax.text(x + w / 2, y + h * 0.85, label, ha="center", weight="bold", color=col)
        ax.text(
            x + w / 2,
            y + 0.05,
            "有效水量 v" if label == "上水库" else "有效水量 V总 − v",
            ha="center",
            fontsize=9,
        )
    ax.text(0.205, 0.865, "z上 = 280 + v/A上", ha="center", fontsize=9, color=BLUE)
    ax.text(0.64, 0.075, "z下 = 64 + (V总−v)/A下", fontsize=9, color=TEAL)
    box(ax, 0.36, 0.27, 0.25, 0.23, "可逆机组", "抽水  P < 0\n发电  P > 0", PURPLE)
    arrow(ax, (0.28, 0.59), (0.40, 0.50), BLUE)
    arrow(ax, (0.60, 0.34), (0.67, 0.27), BLUE)
    ax.text(0.16, 0.43, "发电水流", color=BLUE, fontsize=9)
    arrow(ax, (0.68, 0.17), (0.59, 0.28), TEAL, rad=-0.15)
    arrow(ax, (0.36, 0.45), (0.16, 0.59), TEAL, rad=-0.18)
    ax.text(0.13, 0.34, "抽水水流", color=TEAL, fontsize=9)
    arrow(ax, (0.93, 0.77), (0.93, 0.40), MUTED, style="<->")
    ax.text(0.91, 0.58, "毛水头\nH = z上−z下", ha="right", fontsize=10, color=MUTED)
    box(ax, 0.40, 0.67, 0.20, 0.15, "电网", "价格 × 并网功率", AMBER)
    arrow(ax, (0.50, 0.67), (0.50, 0.51), AMBER, style="<->")
    ax.text(
        0.04,
        0.015,
        "流量 q > 0 表示抽水入上库；P > 0 表示向电网送电。图示表达功能边界。",
        fontsize=9,
        color=MUTED,
    )
    save(fig, out, "fig6_2_system")

    fig, ax = canvas((7.5, 4.6))
    ax.text(
        0.04, 0.95, "模式决定可选动作  状态保存跨时段约束", fontsize=12, weight="bold"
    )
    for x, title, body, col in [
        (0.06, "抽水", "q > 0，P < 0", BLUE),
        (0.39, "停机", "q = 0，P = 0", MUTED),
        (0.72, "发电", "q < 0，P > 0", TEAL),
    ]:
        box(ax, x, 0.66, 0.22, 0.18, title, body, col)
    arrow(ax, (0.28, 0.73), (0.39, 0.73), BLUE, style="<->")
    arrow(ax, (0.61, 0.73), (0.72, 0.73), TEAL, style="<->")
    ax.text(
        0.5,
        0.59,
        "抽发切换经过一个停机时段；相邻小时满足 |P新−P旧| ≤ R",
        ha="center",
        fontsize=10,
        color=PURPLE,
    )
    xs = [0.12, 0.37, 0.62, 0.87]
    ys = [0.17, 0.30, 0.43]
    for j, x in enumerate(xs):
        for i, y in enumerate(ys):
            ax.add_patch(
                Circle((x, y), 0.025, fc="#D9EBEC" if i != 1 else TEAL, ec=TEAL, lw=1)
            )
        ax.text(x, 0.08, ["时刻 k", "k+1", "k+2", "k+3"][j], ha="center", fontsize=9)
    for j in range(3):
        for i in range(3):
            for l in range(3):
                if abs(i - l) <= 1:
                    arrow(
                        ax, (xs[j] + 0.03, ys[i]), (xs[j + 1] - 0.03, ys[l]), "#BDD0D8"
                    )
        arrow(ax, (xs[j] + 0.03, ys[1]), (xs[j + 1] - 0.03, ys[1]), TEAL)
    ax.text(
        0.5,
        0.505,
        "示意状态 s =（水量网格，上一时段流量档位）",
        ha="center",
        fontsize=9.5,
    )
    ax.text(
        0.5,
        0.015,
        "自末端条件向前递推收益  再沿所选动作回放逐时轨迹",
        ha="center",
        fontsize=9,
        color=MUTED,
    )
    save(fig, out, "fig6_6_dp_modes")

    fig, ax = canvas((7.5, 4.4))
    ax.text(
        0.04,
        0.94,
        "压缩空气扩展需要同时保存质量 温度与储热状态",
        fontsize=12,
        weight="bold",
    )
    box(ax, 0.035, 0.43, 0.20, 0.25, "压缩机", "电能 → 压力与热\n质量流入", BLUE)
    box(ax, 0.40, 0.39, 0.21, 0.31, "储气容器", "状态 m、T、p\npV = mRT", TEAL)
    box(ax, 0.78, 0.43, 0.19, 0.25, "膨胀机", "高压气体做功\n质量流出", PURPLE)
    arrow(ax, (0.235, 0.55), (0.40, 0.55), BLUE)
    arrow(ax, (0.61, 0.55), (0.78, 0.55), TEAL)
    ax.text(0.32, 0.59, "入口焓流", ha="center", fontsize=9)
    ax.text(0.695, 0.59, "出口焓流", ha="center", fontsize=9)
    box(ax, 0.40, 0.10, 0.21, 0.16, "储热单元", "状态 E热 或温度", AMBER)
    arrow(ax, (0.14, 0.43), (0.40, 0.18), AMBER, rad=0.12)
    arrow(ax, (0.61, 0.18), (0.87, 0.43), AMBER, rad=0.12)
    ax.text(0.20, 0.23, "压缩热回收", fontsize=9, color=AMBER)
    ax.text(0.68, 0.23, "膨胀前补热", fontsize=9, color=AMBER)
    ax.text(
        0.505, 0.78, "外界换热与容器边界条件", ha="center", color=MUTED, fontsize=9.5
    )
    arrow(ax, (0.505, 0.75), (0.505, 0.70), MUTED, style="<->")
    ax.text(
        0.5,
        0.025,
        "迁移内容：状态定义、流量约束、设备功率和末端条件；按热力学模型重新建立转换关系。",
        ha="center",
        fontsize=8.8,
        color=MUTED,
    )
    save(fig, out, "fig6_9_caes")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch06")
    p.add_argument("--font", type=Path)
    a = p.parse_args()
    draw(a.out, a.font)
