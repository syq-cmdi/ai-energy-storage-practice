"""Five quantitative figure plates, generated from saved Chapter 6 trajectories."""

from pathlib import Path
import argparse, json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from visual_style import setup, style, panel, save, INK, MUTED, RED, GRID
from run import Config, head, potential, efficiency, transition

ROOT = Path(__file__).resolve().parents[2]
COLORS = {"rule": "#C17D1F", "fixed": "#7954A1", "head": "#3268B2", "full": "#087F8C"}
LABELS = {
    "rule": "阈值规则",
    "fixed": "定参数规划",
    "head": "变水头定效率",
    "full": "变水头变效率",
}


def pick(data, scenario="typical", policy="full", group="scenario"):
    return next(
        r
        for r in data["runs"]
        if r["scenario"] == scenario and r["policy"] == policy and r["group"] == group
    )


def draw(data, out, font=None):
    out = Path(out)
    setup(font)
    plt.rcParams.update({"font.size": 10, "legend.fontsize": 9})
    cfg = Config(**data["config"])
    h = np.arange(24)
    fig, axs = plt.subplots(2, 1, figsize=(7.5, 5.3), layout="constrained")
    v = np.linspace(0, cfg.volume_max, 200)
    axs[0].plot(v / 1e6, head(v, cfg), color=COLORS["full"], lw=2)
    axs[0].set(xlabel="上库有效水量 / 百万 m³", ylabel="毛水头 / m")
    ax = axs[0].twinx()
    ax.plot(v / 1e6, potential(v, cfg), color=COLORS["head"], ls="--", lw=1.8)
    ax.set_ylabel("相对空有效库容的势能 / MWh", color=COLORS["head"])
    ax.spines["top"].set_visible(False)
    axs[0].scatter([0.576], [220], s=30, color=COLORS["full"])
    axs[0].annotate(
        "初态 0.576 百万 m³\n水头 220 m，势能 329.616 MWh",
        (0.576, 220),
        xytext=(0.06, 235),
        arrowprops={"arrowstyle": "-", "color": MUTED},
        fontsize=9,
    )
    panel(axs[0], "(a)", "水位变化同时改变水头与势能")
    for s, col in [
        ("typical", COLORS["head"]),
        ("solar", COLORS["rule"]),
        ("flat", MUTED),
    ]:
        axs[1].step(
            h,
            pick(data, s)["price"],
            where="post",
            color=col,
            lw=1.7,
            label=data["names"][s],
        )
    axs[1].axhline(0, color=MUTED, lw=0.7)
    axs[1].set(xlabel="时刻 / h", ylabel="电价 / (元/MWh)", xlim=(0, 24))
    axs[1].legend(ncol=3, frameon=False, loc="upper left")
    panel(axs[1], "(b)", "预先给定的三类教学电价")
    for a in axs:
        style(a)
    save(fig, out, "fig6_3_head_price")

    fig, axs = plt.subplots(1, 2, figsize=(7.5, 3.8), layout="constrained")
    Q, H = np.meshgrid(np.linspace(10, 60, 121), np.linspace(200, 240, 121))
    ep, eg = efficiency(Q, H, cfg)
    for a, eta, sign, title in [
        (axs[0], ep, 1, "抽水工况"),
        (axs[1], eg, -1, "发电工况"),
    ]:
        im = a.contourf(
            Q, H, eta, levels=np.linspace(0.82, 0.94, 13), cmap="YlGnBu", extend="both"
        )
        power = (
            0.00981
            * Q
            * (H + sign * cfg.loss_coeff * Q**2)
            / (eta if sign == 1 else 1 / eta)
        )
        limit = cfg.pump_max if sign == 1 else cfg.gen_max
        cs = a.contour(Q, H, power, levels=[limit], colors=[RED], linewidths=1.8)
        a.clabel(cs, fmt={limit: f"{limit:g} MW上限"}, fontsize=8)
        for q in [20, 40, 60]:
            a.axvline(q, color="white", alpha=0.65, ls=":", lw=0.8)
        a.set(xlabel="流量幅值 / (m³/s)", ylabel="时段平均毛水头 / m")
        panel(a, "(a)" if sign == 1 else "(b)", title)
    cb = fig.colorbar(im, ax=axs, shrink=0.85, pad=0.02)
    cb.set_label("构造效率")
    save(fig, out, "fig6_4_efficiency")

    fig, axs = plt.subplots(
        2, 3, figsize=(8.4, 5.0), layout="constrained", sharex="col"
    )
    for j, p in enumerate(["rule", "fixed", "full"]):
        r = pick(data, "solar", p)
        power = np.array(r["power"])
        axs[0, j].bar(
            h,
            power,
            width=0.86,
            color=np.where(power >= 0, "#53A8A6", "#A9C0DF"),
            alpha=0.9,
        )
        axs[0, j].step(
            h,
            r["predicted_power"],
            where="mid",
            color=COLORS[p],
            ls="--",
            lw=1.3,
            label="计划电功率",
        )
        axs[0, j].axhline(0, color=MUTED, lw=0.7)
        for v0 in r["violations"]:
            axs[0, j].scatter(
                v0["hour"],
                power[v0["hour"]],
                s=70,
                facecolors="none",
                edgecolors=RED,
                lw=1.8,
                zorder=5,
            )
        axs[0, j].set(ylim=(-175, 140), ylabel="并网电功率 / MW" if j == 0 else "")
        panel(axs[0, j], f"({chr(97+j)})", LABELS[p])
        axs[0, j].legend(frameon=False, fontsize=8, loc="lower left")
        axs[1, j].plot(
            np.arange(25), np.array(r["volume"]) / 1e6, color=COLORS[p], lw=1.8
        )
        axs[1, j].axhline(0.576, color=MUTED, ls=":", lw=0.9)
        axs[1, j].set(
            ylim=(0, 1.22),
            xlim=(-0.6, 24.3),
            xticks=[0, 6, 12, 18, 24],
            xlabel="时刻 / h",
            ylabel="上库有效水量 / 百万 m³" if j == 0 else "",
        )
        axs[1, j].text(
            0.03,
            0.95,
            f"回放净收益 {r['metrics']['profit_cny']/10000:.2f} 万元\n越限记录 {r['metrics']['violation_count']} 条",
            transform=axs[1, j].transAxes,
            va="top",
            fontsize=8.5,
            color=INK,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.88, pad=2),
        )
        for a in axs[:, j]:
            a.axvspan(10, 16, color="#FFF2D6", alpha=0.5)
            style(a)
    save(fig, out, "fig6_5_dispatch")

    fig, axs = plt.subplots(
        1,
        2,
        figsize=(7.5, 4.0),
        layout="constrained",
        gridspec_kw={"width_ratios": [1.6, 1]},
    )
    sc = list(data["names"])
    ps = list(COLORS)
    M = np.array(
        [[pick(data, s, p)["metrics"]["profit_cny"] / 10000 for s in sc] for p in ps]
    )
    im = axs[0].imshow(M, cmap="Blues", aspect="auto", vmin=0, vmax=45)
    for i, p in enumerate(ps):
        for j, s in enumerate(sc):
            r = pick(data, s, p)
            n = r["metrics"]["violation_count"]
            axs[0].text(
                j,
                i,
                f"{M[i,j]:.2f}" + (" *" if n else ""),
                ha="center",
                va="center",
                fontsize=9,
                color="white" if M[i, j] > 25 else INK,
            )
            if n:
                axs[0].add_patch(
                    Rectangle(
                        (j - 0.48, i - 0.48),
                        0.96,
                        0.96,
                        fill=False,
                        edgecolor=RED,
                        lw=2,
                    )
                )
    axs[0].set(
        xticks=range(5),
        xticklabels=["峰谷", "平价", "午间低价", "低水位", "降额"],
        yticks=range(4),
        yticklabels=list(LABELS.values()),
    )
    axs[0].tick_params(axis="x", labelsize=8.5)
    panel(axs[0], "(a)", "回放净收益 / 万元")
    axs[0].text(
        0,
        -0.17,
        "* 红框：保留了物理回放越限记录",
        transform=axs[0].transAxes,
        color=RED,
        fontsize=9,
    )
    hs = [180, 200, 220]
    ramps = [40, 65, 100]
    Z = []
    for hh in hs:
        row = []
        for rr in ramps:
            row.append(
                next(
                    r
                    for r in data["runs"]
                    if r["policy"] == "full"
                    and r["scenario"] == "typical"
                    and r["config"]["head_base"] == hh
                    and r["config"]["ramp"] == rr
                    and r["config"]["flow_step"] == 20
                    and r["group"] != "free_terminal"
                )["metrics"]["profit_cny"]
                / 10000
            )
        Z.append(row)
    axs[1].imshow(Z, cmap="YlGnBu", aspect="auto", vmin=0, vmax=30)
    for i in range(3):
        for j in range(3):
            axs[1].text(
                j,
                i,
                f"{Z[i][j]:.2f}",
                ha="center",
                va="center",
                color="white" if Z[i][j] > 18 else INK,
                fontsize=10,
            )
    axs[1].set(
        xticks=range(3),
        xticklabels=ramps,
        yticks=range(3),
        yticklabels=hs,
        xlabel="相邻小时变化上限 / MW",
        ylabel="零有效库容毛水头 / m",
    )
    panel(axs[1], "(b)", "水头与爬坡共同作用")
    save(fig, out, "fig6_7_comparison")

    fig, axs = plt.subplots(1, 2, figsize=(7.5, 4.1), layout="constrained")
    r = pick(data)
    m = r["metrics"]
    vals = [
        m["generation_energy_mwh"],
        m["hydraulic_loss_mwh"],
        m["conversion_loss_mwh"],
    ]
    bottom = 0
    for value, col, label in zip(
        vals, ["#53A8A6", "#C17D1F", "#7954A1"], ["输出电能", "水力损失", "转换损失"]
    ):
        axs[0].bar(
            "闭合能量账",
            value,
            bottom=bottom,
            color=col,
            width=0.5,
            label=f"{label} {value:.2f}",
        )
        bottom += value
    axs[0].bar("抽水输入", m["pump_energy_mwh"], color="#A9C0DF", width=0.5)
    axs[0].set(ylabel="能量 / MWh", ylim=(0, 820))
    axs[0].legend(frameon=False, fontsize=8.5, loc="upper left")
    panel(axs[0], "(a)", "同一初末库存下的守恒")
    for ramp, col in [(40, COLORS["rule"]), (65, COLORS["full"])]:
        vals = []
        for q in [20, 10, 5]:
            vals.append(
                next(
                    r
                    for r in data["runs"]
                    if r["policy"] == "full"
                    and r["scenario"] == "typical"
                    and r["config"]["head_base"] == 200
                    and r["config"]["ramp"] == ramp
                    and r["config"]["flow_step"] == q
                    and r["group"] != "free_terminal"
                )["metrics"]["profit_cny"]
                / 10000
            )
        axs[1].plot(
            [0, 1, 2], vals, "o-", color=col, lw=1.8, label=f"变化上限 {ramp} MW"
        )
        for xx, yy in enumerate(vals):
            axs[1].annotate(
                f"{yy:.2f}",
                (xx, yy),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                fontsize=9,
            )
    axs[1].set(
        xticks=[0, 1, 2],
        xticklabels=["20", "10", "5"],
        xlabel="流量网格间隔 / (m³/s)",
        ylabel="可行净收益 / 万元",
        ylim=(-2, 33),
    )
    axs[1].legend(frameon=False, fontsize=8.5, loc="lower right")
    panel(axs[1], "(b)", "网格细化扩大动作选择")
    for a in axs:
        style(a)
    save(fig, out, "fig6_8_energy_grid")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT / "results/ch06/experiment.json")
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch06")
    p.add_argument("--font", type=Path)
    a = p.parse_args()
    draw(json.loads(a.source.read_text(encoding="utf-8")), a.out, a.font)
