"""Fine vector/600 dpi color figures, generated solely from computed results."""

from pathlib import Path
import argparse, json
import numpy as np
import matplotlib.pyplot as plt
from visual_style import setup, style, panel, save, INK, MUTED, GRID
from model import config, pressure

ROOT = Path(__file__).resolve().parents[2]
COL = ["#4676B5", "#CF893B", "#148B89"]
NAMES = ["按需运行", "日前计划", "滚动协调"]
POL = ["on_demand", "day_ahead", "rolling"]


def main(out, font=None):
    setup(font)
    plt.rcParams.update(
        {
            "font.size": 11.3,
            "axes.labelsize": 11.3,
            "axes.titlesize": 12,
            "legend.fontsize": 10.2,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )
    data = json.loads(
        (ROOT / "results/ch08/experiment.json").read_text(encoding="utf-8")
    )

    def case(s="nominal", cap=80, p="day_ahead"):
        return next(
            c
            for c in data["cases"]
            if (c["scenario"], c["capacity"], c["policy"]) == (s, cap, p)
        )

    def series(c, k):
        return np.array([r[k] for r in c["rows"]])

    fig, axs = plt.subplots(
        1,
        2,
        figsize=(7.6, 3.7),
        layout="constrained",
        gridspec_kw={"width_ratios": [1.05, 1]},
    )
    ax = axs[0]
    vals = [275, 15, 5]
    labels = ["电解", "压缩", "辅助"]
    colors = [COL[0], COL[1], COL[2]]
    bars = ax.barh(np.arange(3), vals, color=colors, height=0.52)
    for b, v in zip(bars, vals):
        ax.text(
            v + 5, b.get_y() + b.get_height() / 2, f"{v} kW", va="center", fontsize=10.5
        )
    ax.set_yticks(range(3), labels)
    ax.invert_yaxis()
    ax.set_xlim(0, 355)
    ax.set_xlabel("电功率 / kW")
    panel(ax, "a", "5 kg/h 的功率账本")
    style(ax, "x")
    ax = axs[1]
    values = [33.33 * 5 / 295 * 100, 39.4 * 5 / 295 * 100]
    ax.bar(["LHV口径", "HHV口径"], values, color=[COL[2], "#8F75AE"], width=0.48)
    for i, v in enumerate(values):
        ax.text(i, v + 2, f"{v:.2f}%", ha="center", fontsize=12)
    ax.set_ylim(0, 85)
    ax.set_ylabel("电制氢转换效率 / %")
    panel(ax, "b", "同一输入，热值口径不同")
    style(ax)
    fig.suptitle("总输入 295 kW · 产氢 5 kg/h · 辅机均计入", color=INK, fontsize=12)
    save(fig, out, "fig08_03_energy_boundary")
    fig, axs = plt.subplots(1, 2, figsize=(7.6, 3.7), layout="constrained")
    m = np.linspace(20, 80, 100)
    c = config()
    for temp, color in zip([288.15, 298.15, 328.15], [COL[0], COL[2], COL[1]]):
        axs[0].plot(
            m, pressure(m, c, temp), color=color, label=f"{temp-273.15:.0f} ℃", lw=2
        )
    axs[0].set(xlabel="库存 / kg", ylabel="估算压力 / bar", xlim=(20, 80))
    axs[0].legend(frameon=False, loc="upper left")
    style(axs[0])
    panel(axs[0], "a", "固定容积 5 m³，Z=1")
    z = np.linspace(1, 1.15, 80)
    for mass, color in zip([50, 80], [COL[2], COL[1]]):
        axs[1].plot(z, pressure(mass, c, z=z), color=color, lw=2, label=f"{mass} kg")
    axs[1].set(xlabel="假设压缩因子 Z", ylabel="估算压力 / bar", xlim=(1, 1.15))
    axs[1].legend(frameon=False)
    style(axs[1])
    panel(axs[1], "b", "25 ℃下的换算敏感性")
    fig.suptitle("压力为诊断换算；容器设计需采用适用物性与设备参数", fontsize=11.5)
    save(fig, out, "fig08_04_pressure")
    fig, axs = plt.subplots(3, 1, figsize=(7.6, 5.5), sharex=True, layout="constrained")
    c0 = case()
    t = series(c0, "time")
    axs[0].fill_between(
        t, series(c0, "renewable"), color="#BBDDD6", alpha=0.8, label="可再生供电"
    )
    axs[0].plot(
        t, series(c0, "demand") * 55, color=COL[0], lw=1.4, label="需求 × 55 kWh/kg"
    )
    axs[0].set_ylabel("功率 / kW")
    axs[0].legend(ncol=2, frameon=False, loc="upper right")
    panel(axs[0], "a", "48 h 输入与运行")
    for pol, color, name in zip(POL, COL, NAMES):
        c0 = case(p=pol)
        axs[1].step(t, series(c0, "p"), where="post", color=color, lw=1.3, label=name)
        axs[2].plot(
            np.r_[t, 48],
            np.r_[50, series(c0, "m_after")],
            color=color,
            lw=1.6,
            label=name,
        )
    axs[1].set_ylabel("电解功率 / kW")
    axs[1].legend(ncol=3, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01))
    axs[2].axhline(20, color=MUTED, ls="--", lw=0.8)
    axs[2].axhline(80, color=MUTED, ls="--", lw=0.8)
    axs[2].set(xlabel="时间 / h", ylabel="库存 / kg", ylim=(15, 85), xlim=(0, 48))
    for ax in axs:
        style(ax)
    save(fig, out, "fig08_05_nominal_dispatch")
    fig, axs = plt.subplots(1, 3, figsize=(7.6, 3.8), layout="constrained")
    for ax, key, title, unit in zip(
        axs,
        ["electricity_cost", "curtailed_kwh", "end_kg"],
        ["购电费用", "弃能", "期末库存"],
        ["元", "kWh", "kg"],
    ):
        vals = [case(p=p)["summary"][key] for p in POL]
        bars = ax.bar(range(3), vals, color=COL, width=0.58)
        for i, v in enumerate(vals):
            ax.text(
                i,
                v + max(vals) * 0.04,
                f"{v:.0f}" if key != "end_kg" else f"{v:.1f}",
                ha="center",
                fontsize=10,
            )
        ax.set_xticks(range(3), ["按需", "日前", "滚动"])
        ax.set_ylabel(unit)
        ax.set_ylim(0, max(vals) * 1.25)
        panel(ax, chr(97 + list(axs).index(ax)), title)
        style(ax)
    fig.suptitle("基准情景 · 库存上限 80 kg · 三策略均无缺供", fontsize=12)
    save(fig, out, "fig08_06_metrics")
    fig, axs = plt.subplots(
        2, 2, figsize=(7.6, 5.1), sharex="col", layout="constrained"
    )
    for j, sc, title in [(0, "surge", "需求突增"), (1, "supply_cap", "突发供能受限")]:
        for pol, color, name in zip(POL, COL, NAMES):
            ca = case(sc, p=pol)
            axs[0, j].plot(t, series(ca, "m_after"), color=color, lw=1.5, label=name)
            axs[1, j].plot(t, series(ca, "shortage"), color=color, lw=1.4)
        for ax in axs[:, j]:
            ax.axvspan(28, 44 if sc == "surge" else 38, color="#F5E9D9", zorder=-1)
            style(ax)
            ax.set_xlim(20, 48)
        panel(axs[0, j], chr(97 + j), title)
        axs[0, j].set_ylim(15, 85)
        axs[0, j].axhline(20, color=MUTED, ls=":", lw=0.8)
        axs[1, j].set_xlabel("时间 / h")
        axs[1, j].set_ylim(-0.3, 9)
    axs[0, 0].set_ylabel("库存 / kg")
    axs[1, 0].set_ylabel("缺供速率 / (kg/h)")
    axs[0, 0].legend(frameon=False, fontsize=9, loc="upper left")
    save(fig, out, "fig08_08_stress")
    fig, axs = plt.subplots(1, 3, figsize=(7.6, 3.9), layout="constrained")
    for p, col, name in zip(POL, COL, NAMES):
        for ax, sc, key in [
            (axs[0], "nominal", "electricity_cost"),
            (axs[1], "supply_cap", "shortage_kg"),
        ]:
            ax.plot(
                [40, 80, 120],
                [case(sc, cap, p)["summary"][key] for cap in [40, 80, 120]],
                "o-",
                color=col,
                lw=1.6,
                ms=4,
                label=name,
            )
    for ax in axs[:2]:
        ax.set_xlabel("库存上限 / kg")
        ax.set_xticks([40, 80, 120])
        style(ax)
    axs[0].set_ylabel("购电费用 / 元")
    axs[1].set_ylabel("累计缺供 / kg")
    panel(axs[0], "a", "基准费用")
    panel(axs[1], "b", "受限情景")
    axs[1].legend(fontsize=8.8, frameon=False)
    choices = [case(), *data["ablations"]]
    vals = [x["summary"]["electricity_cost"] for x in choices]
    axs[2].barh(
        range(4), vals, color=[COL[1], "#7F96AD", "#B69AC8", "#5DABA3"], height=0.55
    )
    axs[2].set_yticks(range(4), ["完整模型", "省略辅机*", "放开期末", "1 h计划"])
    axs[2].invert_yaxis()
    axs[2].set_xlabel("复放购电费用 / 元")
    axs[2].set_xlim(0, 3800)
    style(axs[2], "x")
    panel(axs[2], "c", "模型条件敏感性")
    for i, v in enumerate(vals):
        axs[2].text(v + 55, i, f"{v:.0f}", va="center", fontsize=9)
    fig.supxlabel(
        "*仅计划阶段省略；执行阶段统一计入全部用电。放开期末消耗30 kg库存。",
        fontsize=9.6,
    )
    save(fig, out, "fig08_09_sensitivity")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch08")
    p.add_argument("--font")
    a = p.parse_args()
    main(a.out, a.font)
