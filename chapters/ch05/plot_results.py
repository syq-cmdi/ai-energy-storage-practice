"""Six fine quantitative figures from the same frozen Chapter 5 experiment."""

from pathlib import Path
import argparse, json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Patch
from visual_style import setup, style, panel, save, INK, MUTED

ROOT = Path(__file__).resolve().parents[2]
COLORS = {"rule": "#C17D1F", "perfect": "#3268B2", "mpc": "#087F8C"}
LABELS = {"rule": "固定规则", "perfect": "完美预测", "mpc": "实际预测 MPC"}
DAYCOL = ["#7A98AC", "#3268B2", "#087F8C", "#BB4D4D"]


def select(data, scenario="hot", volume=20, policy="mpc", horizon=24, bias=0):
    return next(
        r
        for r in data["runs"]
        if r["scenario"] == scenario
        and r["volume"] == volume
        and r["policy"] == policy
        and r["horizon"] == horizon
        and abs(r["bias"] - bias) < 1e-6
    )


def draw(data, out, font=None):
    setup(font)
    days = data["days"][:4]
    h = np.arange(24)
    fig, axes = plt.subplots(
        3, 1, figsize=(8.7, 6.1), sharex=True, layout="constrained"
    )
    for day, col in zip(days, DAYCOL):
        axes[0].plot(h, day["load"], lw=1.9, color=col, label=day["name"])
        axes[1].plot(h, day["temp"], lw=1.6, color=col)
    axes[0].axhline(55, color=MUTED, ls="--", lw=1)
    axes[0].text(0.2, 56.5, "冷机 55 kW", fontsize=8.5, color=MUTED)
    axes[0].axhline(80.256, color="#BB4D4D", ls=":", lw=1)
    axes[0].text(0.2, 82, "管路 80.256 kW", fontsize=8.5, color="#BB4D4D")
    axes[0].legend(
        ncol=4, loc="upper left", bbox_to_anchor=(0, 1.36), frameon=False, fontsize=8.8
    )
    axes[2].step(
        np.arange(25),
        np.r_[days[0]["price"], days[0]["price"][-1]],
        where="post",
        color=COLORS["rule"],
        lw=2,
    )
    axes[2].fill_between(
        np.arange(25),
        np.r_[days[0]["price"], days[0]["price"][-1]],
        step="post",
        alpha=0.12,
        color=COLORS["rule"],
    )
    for ax, label in zip(axes, ["冷负荷 / kW", "室外温度 / ℃", "电价 / (元/kWh)"]):
        style(ax)
        ax.set_ylabel(label)
        ax.set_xlim(0, 24)
    axes[2].set(xticks=np.arange(0, 25, 3), xlabel="时刻 / h")
    save(fig, out, "fig5_3_profiles")
    # Thermodynamic capacity versus service qualification.
    fig, axs = plt.subplots(1, 2, figsize=(8.7, 3.8), layout="constrained")
    v = np.arange(0, 61)
    nom = v * 1000 * 4.18 * 6 / 3600
    axs[0].plot(v, nom, color=MUTED, ls="--", label="几何理论容量")
    axs[0].plot(v, 0.85 * nom, color=COLORS["mpc"], lw=2.4, label="有效容量 α=0.85")
    axs[0].fill_between(v, 0.85 * nom, nom, color="#DAE4EC", alpha=0.65)
    axs[0].scatter([20], [118.433333], s=45, color=COLORS["mpc"], zorder=4)
    axs[0].annotate(
        "20 m³ → 118.43 kWh",
        (20, 118.43),
        xytext=(8, 220),
        arrowprops={"arrowstyle": "-", "color": MUTED},
        fontsize=9,
    )
    axs[0].set(xlabel="罐体容积 / m³", ylabel="冷量 / kWh")
    axs[0].legend(frameon=False, loc="upper left", fontsize=9)
    panel(axs[0], "(a)", "体积到有效冷量")
    t = np.linspace(5, 10, 251)
    therm = 0.85 * 20 * 1000 * 4.18 * (12 - t) / 3600
    qualified = np.where(t <= 7, therm, 0)
    axs[1].plot(t, therm, color=MUTED, ls="--", label="相对 12 ℃ 的冷量")
    axs[1].plot(
        t, qualified, color=COLORS["perfect"], lw=2.3, label="温度资格内可供冷量"
    )
    axs[1].axvspan(7, 10, color="#F7E5E3", alpha=0.65)
    axs[1].axvline(7, color="#BB4D4D", ls=":", lw=1)
    axs[1].text(
        8.15, 60, "出口高于 7 ℃\n放冷受限", ha="center", color="#BB4D4D", fontsize=9
    )
    axs[1].set(xlabel="储冷出口温度 / ℃", ylabel="20 m³ 对应冷量 / kWh", ylim=(-8, 160))
    axs[1].legend(frameon=False, loc="upper right", fontsize=8.2)
    panel(axs[1], "(b)", "品质条件独立核验")
    for ax in axs:
        style(ax)
    save(fig, out, "fig5_4_capacity_quality")
    # Same day and capacity across all three strategies.
    fig, axs = plt.subplots(2, 3, figsize=(8.7, 5.8), sharex=True, layout="constrained")
    for j, policy in enumerate(COLORS):
        r = select(data, policy=policy)
        ax = axs[0, j]
        ax.stackplot(h, r["g"], r["d"], colors=["#A9C0DF", "#67B7B7"], alpha=0.9)
        ax.plot(h, r["load"], color=INK, lw=1.4)
        ax.plot(h, -np.asarray(r["c"]), color="#C17D1F", lw=1.5)
        ax.fill_between(
            h, np.asarray(r["g"]) + r["d"], r["load"], color="#BB4D4D", alpha=0.55
        )
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.set_ylim(-35, 73)
        panel(ax, f"({chr(97+j)})", LABELS[policy])
        style(ax)
        ax = axs[1, j]
        ax.plot(np.arange(25), r["energy"], color=COLORS[policy], lw=2.1)
        ax.axhline(r["capacity_kwh"], ls=":", color=MUTED, lw=0.9)
        ax.set(ylim=(-5, 128), xticks=[0, 6, 12, 18, 24], xlabel="时刻 / h")
        ax.axvspan(12, 20, color="#F6E8D3", alpha=0.5)
        style(ax)
        ax.text(
            0.04,
            0.93,
            f"电费 {r['metrics']['electricity_cost_cny']:.2f} 元\n缺冷 {r['metrics']['unmet_kwh']:.2f} kWh",
            transform=ax.transAxes,
            va="top",
            fontsize=8.5,
            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 2},
        )
    axs[0, 0].set_ylabel("冷功率 / kW")
    axs[1, 0].set_ylabel("冷量库存 / kWh")
    fig.legend(
        handles=[
            Patch(color="#A9C0DF", label="直接供冷"),
            Patch(color="#67B7B7", label="储罐放冷"),
            Patch(color="#BB4D4D", label="未满足负荷"),
            Patch(color="#C17D1F", label="负值线为充冷"),
        ],
        loc="outside lower center",
        ncol=4,
        frameon=False,
        fontsize=8.8,
    )
    save(fig, out, "fig5_5_dispatch")
    fig, axs = plt.subplots(1, 2, figsize=(8.7, 4.0), layout="constrained")
    for p, col in COLORS.items():
        rows = [r for r in data["annual"]["rows"] if r["policy"] == p]
        axs[0].plot(
            [r["volume"] for r in rows],
            [r["weighted_total_cost_cny"] / 10000 for r in rows],
            "-o",
            ms=4,
            lw=1.8,
            color=col,
            label=LABELS[p],
        )
        axs[1].plot(
            [r["volume"] for r in rows],
            [r["weighted_unmet_kwh"] for r in rows],
            "-o",
            ms=4,
            lw=1.8,
            color=col,
        )
    axs[0].set(ylabel="加权电费＋年化投资 / 万元", xlabel="罐体容积 / m³")
    axs[1].set(ylabel="加权未满足冷量 / kWh", xlabel="罐体容积 / m³")
    axs[0].legend(frameon=False, fontsize=8.7)
    panel(axs[0], "(a)", "同列费用与服务")
    panel(axs[1], "(b)", "服务缺口随容量变化")
    axs[1].annotate(
        "功率与流量约束留下缺口",
        xy=(50, 171.0606),
        xytext=(22, 1250),
        fontsize=9,
        arrowprops={"arrowstyle": "->", "color": MUTED},
    )
    for ax in axs:
        style(ax)
        ax.set_xticks(np.arange(0, 61, 10))
    save(fig, out, "fig5_6_sizing")
    fig, axs = plt.subplots(1, 2, figsize=(8.7, 4.0), layout="constrained")
    r = select(data, "heatwave")
    axs[0].plot(h, r["load"], lw=2, color=INK, label="已发生负荷")
    for k, col in [(6, COLORS["perfect"]), (14, COLORS["mpc"])]:
        p = r["plans"][k]
        axs[0].plot(
            np.arange(k, k + len(p["forecast"])),
            p["forecast"],
            "--",
            lw=1.7,
            color=col,
            label=f"{k}:00 发布预测",
        )
        axs[0].scatter([k], [p["forecast"][0]], color=col, s=25)
    axs[0].set(xlabel="时刻 / h", ylabel="冷负荷 / kW", xticks=[0, 6, 12, 18, 24])
    axs[0].legend(frameon=False, fontsize=8.5)
    style(axs[0])
    panel(axs[0], "(a)", "观测更新后的预测轨迹")
    mat = np.array(
        [
            [
                select(data, "heatwave", 20, "mpc", H, b)["metrics"]["unmet_kwh"]
                for b in [-0.15, 0, 0.15]
            ]
            for H in [6, 12, 24]
        ]
    )
    im = axs[1].imshow(mat, cmap="YlOrRd", vmin=60, vmax=90, aspect="auto")
    for i in range(3):
        for j in range(3):
            axs[1].text(
                j,
                i,
                f"{mat[i,j]:.2f}",
                ha="center",
                va="center",
                color="white" if mat[i, j] > 80 else INK,
                fontsize=11,
            )
    axs[1].set(
        xticks=[0, 1, 2],
        xticklabels=["−15%", "0", "＋15%"],
        yticks=[0, 1, 2],
        yticklabels=["6 h", "12 h", "24 h"],
        xlabel="未来预测乘法偏差",
        ylabel="规划时域",
    )
    panel(axs[1], "(b)", "实际未满足冷量 / kWh")
    fig.colorbar(im, ax=axs[1], shrink=0.78, label="未满足冷量 / kWh")
    save(fig, out, "fig5_8_forecast")
    fig, axs = plt.subplots(2, 2, figsize=(8.7, 6.2), layout="constrained")
    r = select(data, "heatwave", 60, "perfect")
    axs[0, 0].plot(h, r["load"], color=INK, lw=1.8, label="负荷请求")
    axs[0, 0].plot(
        h,
        np.asarray(r["g"]) + r["d"],
        color=COLORS["perfect"],
        lw=1.8,
        label="可提供冷量",
    )
    axs[0, 0].fill_between(
        h, np.asarray(r["g"]) + r["d"], r["load"], color="#BB4D4D", alpha=0.3
    )
    axs[0, 0].axhline(80.256, color=MUTED, ls=":", lw=1)
    axs[0, 0].set(ylabel="冷功率 / kW", xlabel="时刻 / h")
    axs[0, 0].legend(frameon=False, fontsize=8)
    panel(axs[0, 0], "(a)", "管路与补冷共同约束")
    vals = [select(data, "hot", 20, p)["metrics"]["unmet_kwh"] for p in COLORS]
    q = [select(data, "quality", 20, p)["metrics"]["unmet_kwh"] for p in COLORS]
    xx = np.arange(3)
    axs[0, 1].bar(xx - 0.18, vals, 0.34, color="#67B7B7", label="6 ℃ 合格出口")
    axs[0, 1].bar(xx + 0.18, q, 0.34, color="#BB4D4D", label="8 ℃ 资格失效")
    axs[0, 1].set(
        xticks=xx,
        xticklabels=["规则", "完美预测", "MPC"],
        ylabel="未满足冷量 / kWh",
        ylim=(0, 43),
    )
    axs[0, 1].legend(frameon=False, fontsize=8)
    panel(axs[0, 1], "(b)", "品质失效后的服务变化")
    for sc, col in zip(
        data["investment_sensitivity"], ["#AAB7C5", "#3268B2", "#087F8C"]
    ):
        rows = [r for r in sc["rows"] if r["policy"] == "mpc"]
        axs[1, 0].plot(
            [r["volume"] for r in rows],
            [r["weighted_total_cost_cny"] / 10000 for r in rows],
            "-o",
            color=col,
            ms=3,
            label=f"投资 ×{sc['investment_scale']:g}",
        )
    axs[1, 0].set(xlabel="罐体容积 / m³", ylabel="加权费用 / 万元")
    axs[1, 0].legend(frameon=False, fontsize=8)
    panel(axs[1, 0], "(c)", "投资假设的敏感性")
    rs = [select(data, "hot", 20, p) for p in COLORS]
    cc = [r["metrics"]["electricity_cost_cny"] for r in rs]
    uu = [r["metrics"]["unmet_kwh"] for r in rs]
    for p, x, y in zip(COLORS, cc, uu):
        axs[1, 1].scatter(x, y, color=COLORS[p], s=60)
        axs[1, 1].annotate(
            LABELS[p], (x, y), xytext=(4, 6), textcoords="offset points", fontsize=8.5
        )
    axs[1, 1].set(
        xlabel="单日电费 / 元",
        ylabel="未满足冷量 / kWh",
        xlim=(150, 154),
        ylim=(-1, 9.5),
    )
    panel(axs[1, 1], "(d)", "费用与服务一起判断")
    for ax in axs.flat:
        style(ax)
    save(fig, out, "fig5_9_failures")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT / "results/ch05/experiment.json")
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch05")
    p.add_argument("--font", type=Path)
    a = p.parse_args()
    draw(json.loads(a.source.read_text(encoding="utf-8")), a.out, a.font)
