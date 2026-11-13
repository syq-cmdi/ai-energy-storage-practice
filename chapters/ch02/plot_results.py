"""Reproduce the chapter's quantitative figures from saved experiment outputs.

No model is fitted here. All curves, scores and empirical intervals are read
from CSV/JSON so that the figures and the experiment use one source of truth.
Run: python chapters/ch02/plot_results.py --out assets/figures
"""

from pathlib import Path
import argparse
import csv
import json
import warnings

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent
COLORS = {
    "persistence": "#6B7C8D",
    "ridge": "#3268B2",
    "forest": "#C17D1F",
    "window_mlp": "#087F8C",
}
INK = "#183448"
MUTED = "#5C7181"
GRID = "#DCE5EC"
PURPLE = "#7954A1"
RED = "#BB4D4D"
NAMES = {
    "persistence": "持久性",
    "ridge": "岭回归",
    "forest": "随机森林",
    "window_mlp": "窗口网络",
}


def setup(font_path=None):
    """Use an installed CJK font; fonts are not redistributed with the code."""
    if font_path:
        font_manager.fontManager.addfont(str(font_path))
        family = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        local = Path("/System/Library/Fonts/STHeiti Light.ttc")
        local_family = None
        if local.exists():
            font_manager.fontManager.addfont(str(local))
            local_family = font_manager.FontProperties(fname=str(local)).get_name()
        available = {f.name for f in font_manager.fontManager.ttflist}
        family = next(
            (
                n
                for n in [
                    "Noto Sans CJK SC",
                    "Source Han Sans SC",
                    "Microsoft YaHei",
                    "PingFang SC",
                    "Heiti SC",
                    "SimHei",
                ]
                if n in available
            ),
            local_family,
        )
        if family is None:
            raise RuntimeError(
                "需要中文字体。Linux可安装fonts-noto-cjk，或通过--font指定合法取得的中文字体文件。"
            )
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [family, "DejaVu Sans"],
            "font.size": 10.2,
            "axes.titlesize": 11.2,
            "axes.titleweight": "bold",
            "axes.labelsize": 10.2,
            "axes.edgecolor": MUTED,
            "axes.linewidth": 0.7,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9.4,
            "ytick.labelsize": 9.4,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "legend.fontsize": 9.3,
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def style(ax, grid="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=grid, color=GRID, lw=0.65)
    ax.set_axisbelow(True)
    ax.tick_params(pad=4)


def panel(ax, label, title):
    ax.set_title(f"{label}  {title}", loc="left", pad=10)


def save(fig, out, stem):
    out.mkdir(parents=True, exist_ok=True)
    for ext in ["svg", "png", "pdf"]:
        fig.savefig(out / f"{stem}.{ext}", dpi=600 if ext == "png" else 150)
    plt.close(fig)


def soc_figure(data, out):
    rows = read_csv(data / "soc.csv")
    t = np.array([float(r["time_s"]) / 60 for r in rows])
    ref = np.array([float(r["reference"]) for r in rows])
    curves = {
        k: np.array([float(r[k]) for r in rows])
        for k in ["current_bias", "nominal_capacity", "initial_bias"]
    }
    labels = ["电流偏高0.02 A", "容量取2 A·h", "初始偏高5个百分点"]
    colors = [COLORS["ridge"], COLORS["forest"], PURPLE]
    dashes = ["--", "-.", ":"]
    fig = plt.figure(figsize=(7.6, 4.65))
    gs = fig.add_gridspec(
        2,
        2,
        left=0.085,
        right=0.97,
        bottom=0.20,
        top=0.86,
        hspace=0.65,
        wspace=0.35,
        height_ratios=[0.55, 2.1],
    )
    current_ax = fig.add_subplot(gs[0, :])
    a = fig.add_subplot(gs[1, 0])
    b = fig.add_subplot(gs[1, 1])
    current = [0.6, 1.2, -0.4, 0, 0]
    current_ax.step(
        [0, 15, 30, 45, 60], current, where="post", color=COLORS["window_mlp"], lw=1.5
    )
    for x0, x1, v, txt, col in [
        (0, 15, 0.6, "放电0.6 A", COLORS["window_mlp"]),
        (15, 30, 1.2, "放电1.2 A", COLORS["window_mlp"]),
        (30, 45, -0.4, "充电0.4 A", COLORS["ridge"]),
        (45, 60, 0, "静置", MUTED),
    ]:
        current_ax.fill_between([x0, x1], 0, v, step="post", color=col, alpha=0.12)
        current_ax.text((x0 + x1) / 2, 1.54, txt, ha="center", fontsize=9.4, color=col)
    current_ax.set(
        xlim=(0, 60),
        ylim=(-0.65, 2),
        yticks=[0, 1.2],
        xticks=[0, 15, 30, 45, 60],
        ylabel="电流 / A",
    )
    style(current_ax)
    current_ax.tick_params(axis="x", labelbottom=False)
    panel(a, "a", "SOC轨迹")
    panel(b, "b", "相对参考轨迹的误差")
    a.plot(t, ref, color=COLORS["window_mlp"], lw=2.1, label="参考SOC")
    for k, lab, col, ls in zip(curves, labels, colors, dashes):
        a.plot(t, curves[k], color=col, ls=ls, lw=1.45, label=lab)
        err = (curves[k] - ref) * 100
        b.plot(t, err, color=col, ls=ls, lw=1.55)
        b.scatter([60], [err[-1]], s=16, color=col, zorder=5)
        b.annotate(
            f"{err[-1]:+.2f}",
            (60, err[-1]),
            xytext=(5, 0),
            textcoords="offset points",
            va="center",
            color=col,
            fontsize=9.4,
        )
    for ax in (a, b):
        style(ax)
        ax.set_xticks([0, 15, 30, 45, 60])
        ax.set_xlabel("时间 / min")
        ax.set_xlim(0, 60)
        for x in [15, 30, 45]:
            ax.axvline(x, color=GRID, lw=0.6, ls="--")
    a.set(ylim=(0.48, 0.88), ylabel="SOC", yticks=[0.5, 0.6, 0.7, 0.8])
    b.set(ylim=(-1.65, 5.6), ylabel="误差 / 百分点", yticks=[-1, 0, 2, 4, 5])
    b.set_xlim(0, 69)
    b.axhline(0, color=MUTED, lw=0.8)
    handles, labels2 = a.get_legend_handles_labels()
    fig.legend(
        handles,
        labels2,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=2,
        frameon=False,
        columnspacing=2,
    )
    fig.text(
        0.085,
        0.96,
        "相同电流工况下，三类参数误差产生不同的时间特征",
        fontsize=11.2,
        weight="bold",
    )
    save(fig, out, "fig02_05_soc")


def comparison_figure(data, out):
    m = json.loads((data / "metrics.json").read_text())
    families = list(NAMES)
    fig, axes = plt.subplots(2, 2, figsize=(7.6, 4.7), sharex=True)
    fig.subplots_adjust(
        left=0.13, right=0.93, bottom=0.15, top=0.83, wspace=0.38, hspace=0.55
    )
    for ax, cell in zip(axes.flat, ["C09", "C10", "C11", "C12"]):
        vals = [m["per_cell_test"][f][cell]["mae_pp"] for f in families]
        for y, (f, v) in enumerate(zip(families, vals)):
            ax.plot(
                [0, v],
                [y, y],
                color=COLORS[f],
                lw=2.4,
                alpha=0.32,
                solid_capstyle="round",
            )
            ax.scatter(
                [v],
                [y],
                s=46,
                color=COLORS[f],
                edgecolor="white",
                linewidth=0.7,
                zorder=4,
                marker=["s", "o", "D", "o"][y],
            )
            ax.text(
                v + 0.012, y, f"{v:.3f}", va="center", fontsize=9.6, color=COLORS[f]
            )
        ax.set_yticks(range(4), [NAMES[f] for f in families])
        ax.invert_yaxis()
        ax.set_ylim(3.6, -0.6)
        ax.set_title(f"{cell}  ·  155个目标", loc="left", pad=8)
        style(ax, "x")
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, 0.36)
        ax.set_xticks([0, 0.1, 0.2, 0.3])
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
    for ax in axes[1]:
        ax.set_xlabel("MAE / 百分点（越小越好）")
    fig.text(
        0.13,
        0.94,
        "同一评价尺度，分别观察四个未参与训练的电芯",
        fontsize=11.2,
        weight="bold",
    )
    fig.text(
        0.13,
        0.035,
        "每个标记汇总一组逐点误差；测试电芯等样本量，总样本数620。",
        fontsize=9.3,
        color=MUTED,
    )
    save(fig, out, "fig02_06_cells")


def interval_figure(data, out):
    m = json.loads((data / "metrics.json").read_text())
    family = m["selected_family"]
    rows = [r for r in read_csv(data / "predictions.csv") if r["cell_id"] == "C09"]
    x = np.array([int(r["target_cycle"]) for r in rows])
    y = np.array([float(r["target_soh"]) for r in rows])
    p = np.array([float(r[family]) for r in rows])
    lo = np.array([float(r["lower_soh"]) for r in rows])
    hi = np.array([float(r["upper_soh"]) for r in rows])
    e = (p - y) * 100
    r = m["empirical_interval"]["radius_pp"]
    fig = plt.figure(figsize=(7.6, 4.8))
    gs = fig.add_gridspec(
        2,
        2,
        left=0.09,
        right=0.97,
        bottom=0.18,
        top=0.87,
        width_ratios=[1.65, 1],
        height_ratios=[1.7, 1],
        wspace=0.35,
        hspace=0.65,
    )
    a = fig.add_subplot(gs[0, 0])
    b = fig.add_subplot(gs[0, 1])
    c = fig.add_subplot(gs[1, :])
    for ax in [a, b]:
        ax.fill_between(x, lo, hi, color=COLORS["window_mlp"], alpha=0.18, linewidth=0)
        ax.plot(x, y, color=COLORS["forest"], lw=1.05, ls="--")
        ax.plot(x, p, color=COLORS["window_mlp"], lw=1.45)
        style(ax)
        ax.set_ylabel("容量型SOH")
    panel(a, "a", "C09完整轨迹")
    a.set(xlim=(6, 160), ylim=(0.76, 1.01), xticks=[6, 40, 80, 120, 160])
    window = x >= 140
    mn = min(lo[window].min(), y[window].min()) - 0.004
    mx = max(hi[window].max(), y[window].max()) + 0.004
    panel(b, "b", "末段局部放大")
    b.set(xlim=(140, 160), ylim=(mn, mx), xticks=[140, 150, 160])
    b.tick_params(axis="y", labelsize=9)
    a.axvspan(140, 160, color=GRID, alpha=0.3)
    a.text(144, 0.992, "放大", fontsize=8.9, color=MUTED)
    panel(c, "c", "残差与经验带宽")
    c.axhspan(-r, r, color=COLORS["window_mlp"], alpha=0.10)
    c.axhline(r, color=COLORS["window_mlp"], ls="--", lw=0.8)
    c.axhline(-r, color=COLORS["window_mlp"], ls="--", lw=0.8)
    c.axhline(0, color=MUTED, lw=0.7)
    outside = np.abs(e) > r
    c.scatter(x[~outside], e[~outside], s=8, color=COLORS["window_mlp"], alpha=0.7)
    c.scatter(
        x[outside],
        e[outside],
        s=20,
        facecolors="white",
        edgecolors=RED,
        linewidths=0.8,
        zorder=3,
    )
    style(c)
    c.set(
        xlim=(6, 160),
        ylim=(-0.85, 0.85),
        xticks=[6, 40, 80, 120, 160],
        yticks=[-0.5, 0, 0.5],
        xlabel="目标循环",
        ylabel="残差 / 百分点",
    )
    fig.text(
        0.09,
        0.96,
        f'C08校准半宽 ±{r:.4f} 个百分点；C09覆盖率 {m["empirical_interval"]["coverage_per_cell"]["C09"]:.2%}',
        fontsize=10.6,
        weight="bold",
    )
    handles = [
        Line2D([], [], color=COLORS["forest"], ls="--", label="容量标签"),
        Line2D([], [], color=COLORS["window_mlp"], label="冻结模型预测"),
        Patch(facecolor=COLORS["window_mlp"], alpha=0.18, label="经验误差带"),
        Line2D([], [], marker="o", mfc="white", mec=RED, ls="", label="带外目标"),
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.52, 0.008),
        ncol=4,
        frameon=False,
        columnspacing=1.1,
    )
    save(fig, out, "fig02_08_interval")


def build_all(data, out, font=None):
    setup(font)
    soc_figure(data, out)
    comparison_figure(data, out)
    interval_figure(data, out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "reference_results")
    parser.add_argument("--out", type=Path, default=ROOT.parents[1] / "assets/figures")
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    build_all(args.results.resolve(), args.out.resolve(), args.font)
    print(f"Figures saved to {args.out.resolve()}")
