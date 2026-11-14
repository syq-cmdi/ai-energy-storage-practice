"""Five publication figures from saved results; PNG 600 dpi, editable SVG, PDF."""

from pathlib import Path
import argparse
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from visual_style import setup, style, panel, save, INK, MUTED, GRID

ROOT = Path(__file__).resolve().parents[2]
TEAL, BLUE, AMBER, PURPLE, RED = "#087F8C", "#3268B2", "#C17D1F", "#7954A1", "#BB4D4D"


def plot(source, out, font=None):
    setup(font)
    d = json.loads(source.read_text(encoding="utf-8"))
    s = d["summary"]
    e = {x["id"]: x for x in d["episodes"]}
    res = d["results"]
    fig, axs = plt.subplots(
        2,
        1,
        figsize=(8.7, 5.6),
        layout="constrained",
        sharex=True,
        height_ratios=[1, 1.5],
    )
    x = np.array(e["cal_pulse"]["t_s"]) / 3600
    for key, col, label in [
        ("cal_pulse", TEAL, "脉冲校准"),
        ("cal_cool", AMBER, "加热—冷却校准"),
    ]:
        axs[0].step(
            x[:-1], e[key]["power"], where="post", color=col, lw=1.4, label=label
        )
        axs[1].plot(x, e[key]["truth"], color=col, lw=1.9)
        axs[1].scatter(
            x[::8],
            np.array(e[key]["observed"])[::8],
            s=8,
            c=col,
            alpha=0.35,
            edgecolors="none",
        )
    panel(axs[0], "(a)", "保持足够长的阶跃与冷却段")
    panel(axs[1], "(b)", "同一水罐 不同初温与输入历史")
    axs[0].set(ylabel="有效热输入 / kW", ylim=(-0.1, 1.85))
    axs[0].legend(ncol=2, loc="upper right", frameon=False)
    axs[1].set(xlabel="时间 / h", ylabel="水温 / ℃", xlim=(0, 24))
    for ax in axs:
        style(ax)
    save(fig, out, "fig4_3_excitation")

    fig, axs = plt.subplots(1, 2, figsize=(8.7, 3.7), layout="constrained")
    for ax, key, title in zip(
        axs,
        ["steady", "pulse"],
        ["单一稳态：热容量不可辨识", "脉冲输入：两列灵敏度可区分"],
    ):
        v = s["sensitivity"][key]
        t = np.arange(len(v["C_sensitivity"])) * 120 / 3600
        ax.plot(t, v["C_sensitivity"], color=BLUE, lw=1.8, label="相对热容量灵敏度")
        ax.plot(t, v["UA_sensitivity"], color=AMBER, lw=1.8, label="相对散热系数灵敏度")
        panel(ax, "(a)" if key == "steady" else "(b)", title)
        ax.set(xlabel="时间 / h", ylabel="温度灵敏度 / K", xlim=(0, 24))
        style(ax)
        ax.text(
            0.04,
            0.08,
            f'矩阵秩 = {v["rank"]}',
            transform=ax.transAxes,
            color=INK,
            fontsize=11,
        )
    axs[0].legend(frameon=False, fontsize=9, loc="lower left", bbox_to_anchor=(0, 0.16))
    save(fig, out, "fig4_4_identifiability")

    fig = plt.figure(figsize=(8.7, 5.5), layout="constrained")
    gs = fig.add_gridspec(2, 2, width_ratios=[1.45, 1])
    ax = fig.add_subplot(gs[0, 0])
    ar = fig.add_subplot(gs[1, 0], sharex=ax)
    ae = fig.add_subplot(gs[:, 1])
    v = e["cal_cool"]
    t = np.array(v["t_s"]) / 3600
    from run import simulate

    p = s["physical_fit"]
    fit = simulate(v["power"], v["ambient"], p["initials"][1], p["capacity"], p["ua"])
    ax.scatter(
        t[::5],
        np.array(v["observed"])[::5],
        s=8,
        color=AMBER,
        alpha=0.5,
        label="带噪观测",
    )
    ax.plot(t, fit, color=TEAL, lw=1.8, label="全轨迹拟合")
    ax.legend(frameon=False, ncol=2, fontsize=9)
    panel(ax, "(a)", "校准轨迹与联合拟合")
    ax.set(ylabel="温度 / ℃", xlim=(0, 24))
    style(ax)
    error = np.array(v["observed"]) - fit
    ar.scatter(t, error, s=5, color=BLUE, alpha=0.45)
    ar.axhline(0, color=MUTED, lw=0.8)
    ar.axhspan(-0.5, 0.5, color=TEAL, alpha=0.07)
    panel(ar, "(b)", "残差保留测量噪声")
    ar.set(xlabel="时间 / h", ylabel="观测−拟合 / K")
    style(ar)
    cov = np.array(p["covariance"])[:2, :2]
    scale = np.diag([1, 1000])
    cov = scale @ cov @ scale
    val, vec = np.linalg.eigh(cov)
    order = val.argsort()[::-1]
    val = val[order]
    vec = vec[:, order]
    angle = np.degrees(np.arctan2(*vec[:, 0][::-1]))
    center = (p["capacity"], 1000 * p["ua"])
    ae.add_patch(
        Ellipse(
            center,
            2 * np.sqrt(5.991 * val[0]),
            2 * np.sqrt(5.991 * val[1]),
            angle=angle,
            facecolor=TEAL,
            alpha=0.16,
            edgecolor=TEAL,
            lw=1.5,
        )
    )
    ae.scatter(*center, s=38, color=TEAL, label="估计值", zorder=5)
    ae.scatter(
        418, 10, s=65, color=AMBER, marker="+", linewidth=2, label="生成参数", zorder=5
    )
    ae.set(
        xlim=(center[0] - 1.4, center[0] + 1.4),
        ylim=(center[1] - 0.06, center[1] + 0.06),
        xlabel="热容量 / (kJ/K)",
        ylabel="散热系数 / (W/K)",
    )
    panel(ae, "(c)", "局部参数不确定性")
    ae.legend(frameon=False, loc="upper right")
    style(ae, "both")
    ae.text(
        0.04,
        0.04,
        "95% 渐近联合椭圆\n条件：模型正确、独立同方差噪声",
        transform=ae.transAxes,
        fontsize=8.8,
        color=MUTED,
    )
    save(fig, out, "fig4_5_parameter_fit")

    fig, axs = plt.subplots(2, 2, figsize=(8.7, 6.0), layout="constrained")
    for col, key, title in [
        (0, "test_nominal", "常规工况：机理滤波"),
        (1, "test_bias", "偏移工况：灰箱滤波"),
    ]:
        ep = e[key]
        rr = res[key]
        t = np.array(ep["t_s"]) / 3600
        fl = rr["kf" if col == 0 else "ekf"]
        mean = np.array(fl["temperature"])
        std = np.sqrt(fl["variance"])
        ref = np.array(ep["truth"])
        axs[0, col].scatter(
            t[::3],
            np.array(ep["observed"])[::3],
            s=7,
            color=AMBER,
            alpha=0.45,
            label="观测",
        )
        axs[0, col].plot(t, ref, color=INK, lw=1.5, label="参考温度")
        axs[0, col].plot(t, mean, color=TEAL, lw=1.6, label="状态估计")
        axs[1, col].fill_between(
            t, -1.96 * std, 1.96 * std, color=TEAL, alpha=0.17, label="模型内 ±1.96σ"
        )
        axs[1, col].plot(t, mean - ref, color=TEAL, lw=1.5, label="估计误差")
        axs[1, col].axhline(0, color=MUTED, lw=0.7)
        axs[1, col].set(ylim=(-0.35, 0.4), xlabel="时间 / h", ylabel="误差 / K")
        axs[0, col].set(ylabel="温度 / ℃", xlim=(0, ep["hours"]))
        panel(axs[0, col], "(a)" if col == 0 else "(b)", title)
        panel(axs[1, col], "(c)" if col == 0 else "(d)", "误差与滤波内部区间")
        for row in [0, 1]:
            style(axs[row, col])
            axs[row, col].axvspan(0, 1 / 3, color=GRID, alpha=0.6)
            if col:
                axs[row, col].axvline(6, color=RED, lw=1.1, ls="--")
    axs[0, 0].legend(frameon=False, ncol=3, fontsize=8.4)
    axs[1, 0].legend(frameon=False, fontsize=8.4, loc="lower right")
    axs[0, 1].text(
        0.54,
        0.9,
        "6 h 后观测 +1.2 K",
        transform=axs[0, 1].transAxes,
        color=RED,
        fontsize=9,
    )
    save(fig, out, "fig4_7_state_estimation")

    fig, axs = plt.subplots(
        1, 2, figsize=(8.7, 4.6), layout="constrained", width_ratios=[1.4, 1]
    )
    keys = ["test_nominal", "test_loss", "test_bias", "test_hot"]
    names = ["常规", "附加散热", "传感器偏移", "高温外推"]
    methods = ["measurement", "physical", "gray", "kf", "ekf"]
    values = np.array([[s["metrics"][k][m]["rmse_C"] for m in methods] for k in keys])
    from matplotlib.colors import LogNorm

    im = axs[0].imshow(
        values, cmap="YlGnBu", norm=LogNorm(vmin=0.01, vmax=13), aspect="auto"
    )
    axs[0].set(
        xticks=range(5),
        xticklabels=["观测", "机理\n开环", "灰箱\n开环", "KF", "EKF"],
        yticks=range(4),
        yticklabels=names,
    )
    for i in range(4):
        for j in range(5):
            axs[0].text(
                j,
                i,
                f"{values[i,j]:.3f}",
                ha="center",
                va="center",
                fontsize=9.3,
                color="white" if values[i, j] > 1 else INK,
            )
    axs[0].tick_params(length=0)
    fig.colorbar(im, ax=axs[0], label="温度 RMSE / K", shrink=0.75)
    panel(axs[0], "(a)", "所有独立工况 均保留失败结果")
    y = np.arange(4)
    for offset, m, col, label in [
        (-0.16, "physical", BLUE, "机理开环"),
        (0.16, "gray", TEAL, "灰箱开环"),
    ]:
        ev = [s["metrics"][k][m]["cumulative_energy_kJ"] / 1000 for k in keys]
        axs[1].barh(y + offset, ev, height=0.27, color=col, label=label)
    axs[1].set(yticks=y, yticklabels=names, xlabel="末端累计能量偏差 / MJ")
    axs[1].invert_yaxis()
    axs[1].axvline(0, color=MUTED, lw=0.8)
    panel(axs[1], "(b)", "参考热流与开环储能核对")
    style(axs[1], "x")
    axs[1].legend(frameon=False, loc="lower right", fontsize=9)
    save(fig, out, "fig4_8_validation")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=ROOT / "results/ch04/experiment.json")
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch04")
    p.add_argument("--font", type=Path)
    a = p.parse_args()
    plot(a.source, a.out, a.font)
