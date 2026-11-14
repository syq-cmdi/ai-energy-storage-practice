"""Chapter 10 scientific figures, regenerated from the executed experiment ledger."""

from pathlib import Path
import argparse, json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle
from visual_style import setup, style, INK, MUTED, GRID

ROOT = Path(__file__).resolve().parents[2]
COLORS = {
    "physical": "#367CB1",
    "direct": "#B8822B",
    "residual": "#168B82",
    "rule": "#7D8795",
    "guarded_residual": "#8D70A8",
}
LABELS = {
    "physical": "已辨识机理",
    "direct": "纯数据模型",
    "residual": "残差模型",
    "rule": "规则基线",
    "guarded_residual": "域保护残差",
}
LIGHT = ["#EDF5FA", "#EAF7F3", "#FFF5E5", "#F3EFF8", "#FBEFF0"]
PALETTE = ["#367CB1", "#168B82", "#C58B31", "#8D70A8", "#C9696E"]


def save(fig, out, name):
    out.mkdir(parents=True, exist_ok=True)
    for ext in ["png", "svg", "pdf"]:
        metadata = (
            {"Date": None}
            if ext == "svg"
            else {"CreationDate": None, "ModDate": None} if ext == "pdf" else None
        )
        fig.savefig(out / (name + "." + ext), dpi=600, metadata=metadata)
    plt.close(fig)


def canvas(title, subtitle, size=(7.6, 4.4)):
    fig, ax = plt.subplots(figsize=size)
    fig.subplots_adjust(left=0.035, right=0.965, top=0.82, bottom=0.06)
    ax.set(xlim=(0, 10), ylim=(0, 6))
    ax.axis("off")
    fig.text(0.04, 0.955, title, weight="bold", size=14, color=INK)
    fig.text(0.04, 0.89, subtitle, size=9.5, color=MUTED)
    return fig, ax


def card(ax, x, y, w, h, title, body, idx=0):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.03,rounding_size=.13",
            lw=0.9,
            edgecolor=PALETTE[idx],
            facecolor=LIGHT[idx],
        )
    )
    ax.plot(
        [x + 0.14, x + 0.14],
        [y + 0.18, y + h - 0.18],
        color=PALETTE[idx],
        lw=3,
        solid_capstyle="round",
    )
    ax.text(x + 0.30, y + h - 0.28, title, va="top", weight="bold", size=11)
    ax.text(
        x + 0.30, y + h - 0.82, body, va="top", linespacing=1.55, size=10, color=MUTED
    )


def arrow(ax, start, end, label="", idx=0):
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle="-|>", mutation_scale=12, lw=1.3, color=PALETTE[idx]
        )
    )
    if label:
        ax.text(
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2 + 0.15,
            label,
            ha="center",
            size=9,
            color=PALETTE[idx],
        )


def schematic_reference(out):
    f, a = canvas(
        "W-H1：状态、动作与热量边界",
        "充分混合水体，无进出水；电加热功率是可控输入，环境温度是已知扰动",
    )
    a.add_patch(
        FancyBboxPatch(
            (3.7, 1.15),
            2.6,
            3.9,
            boxstyle="round,pad=.05,rounding_size=.55",
            edgecolor=PALETTE[0],
            facecolor=LIGHT[0],
            lw=1.5,
        )
    )
    a.add_patch(
        Rectangle(
            (3.85, 1.75), 2.3, 2.55, facecolor="#C7E6F0", edgecolor="none", alpha=0.8
        )
    )
    a.text(5, 4.65, "充分混合水罐", ha="center", weight="bold", size=12)
    a.text(5, 3.45, "状态 $T_k$", ha="center", size=15, weight="bold", color=PALETTE[0])
    a.text(5, 2.75, "热容 C / kJ/K", ha="center", size=10.5)
    a.plot(
        [4.25, 4.45, 4.65, 4.85, 5.05, 5.25, 5.45, 5.65, 5.85],
        [1.55, 1.85, 1.55, 1.85, 1.55, 1.85, 1.55, 1.85, 1.55],
        color=PALETTE[2],
        lw=2,
    )
    card(
        a, 0.05, 2.5, 2.45, 2.0, "可控动作", "加热功率 $u_k$ / kW\n保持一个离散步长", 2
    )
    arrow(a, (2.55, 3.45), (3.65, 3.45), "热输入", 2)
    card(a, 7.5, 3.1, 2.45, 1.85, "环境与散热", "环境温度 $T_{a,k}$\n温差驱动热损失", 1)
    arrow(a, (6.35, 3.9), (7.45, 3.9), "热流出", 1)
    card(a, 7.5, 0.35, 2.45, 1.8, "下一步观测", "参考环境推进\n得到 $T_{k+1}$", 3)
    arrow(a, (6.35, 1.8), (7.45, 1.25), idx=3)
    a.text(
        0.2,
        0.55,
        "教学记录：[$T_k$, $T_{a,k}$, $u_k$] → $T_{k+1}$\n完整轨迹保留初值、动作与环境条件",
        size=10,
        color=MUTED,
        linespacing=1.6,
    )
    save(f, out, "fig10_02_reference")


def schematic_models(out):
    f, a = canvas(
        "三类模型：动作条件与预测分解",
        "输入归一化统计量来自训练集；网络宽度由整条验证轨迹的15步终点误差选择",
    )
    card(
        a,
        0.05,
        1.65,
        2.0,
        2.45,
        "共同输入",
        "温度 $T_k$\n环境 $T_{a,k}$\n功率 $u_k$",
        0,
    )
    rows = [
        (4.25, "机理状态推进", r"$F_{phys}(T_k,u_k,T_{a,k})$", 0),
        (2.25, "纯数据增量", r"$T_k+f_{\theta}(T_k,T_{a,k},u_k)$", 2),
        (0.25, "机理 + 残差", r"$F_{phys}+g_{\phi}(T_k,T_{a,k},u_k)$", 1),
    ]
    for y, title, body, col in rows:
        card(a, 3.15, y, 4.5, 1.5, title, body, col)
        arrow(a, (2.1, 2.9), (3.1, y + 0.75), idx=col)
        arrow(a, (7.7, y + 0.75), (8.3, y + 0.75), idx=col)
        a.add_patch(
            Circle(
                (8.9, y + 0.75),
                0.5,
                facecolor=LIGHT[col],
                edgecolor=PALETTE[col],
                lw=1.1,
            )
        )
        a.text(
            8.9,
            y + 0.75,
            "$T_{k+1}$",
            ha="center",
            va="center",
            size=13,
            color=PALETTE[col],
        )
    save(f, out, "fig10_05_models")


def schematic_planning(out):
    f, a = canvas(
        "候选评估与滚动反馈", "统一候选集合与观测信息；只执行首个动作，下一时刻重新规划"
    )
    card(
        a,
        0.05,
        3.8,
        2.7,
        1.75,
        "读取当前状态",
        "温度、环境与参考目标\n登记控制器内部信息",
        0,
    )
    card(
        a,
        3.65,
        3.8,
        2.7,
        1.75,
        "模型预测候选",
        "逐个展开未来轨迹\n累计误差与动作代价",
        1,
    )
    card(
        a,
        7.25,
        3.8,
        2.7,
        1.75,
        "约束与适用域",
        "检查预测状态和动作\n登记筛选及回退原因",
        2,
    )
    arrow(a, (2.8, 4.65), (3.6, 4.65))
    arrow(a, (6.4, 4.65), (7.2, 4.65), idx=1)
    card(
        a,
        5.5,
        0.4,
        4.45,
        1.9,
        "参考环境执行",
        "首个动作进入独立参考环境\n得到下一时刻真实温度",
        3,
    )
    card(
        a,
        0.05,
        0.4,
        4.45,
        1.9,
        "更新状态与运行账本",
        "保存目标误差、能耗与回退事件\n在相同环境中比较各控制器",
        0,
    )
    arrow(a, (8.6, 3.75), (8.6, 2.35), "执行首项", 2)
    arrow(a, (5.45, 1.35), (4.55, 1.35), idx=3)
    arrow(a, (1.4, 2.35), (1.4, 3.75), "反馈", 0)
    save(f, out, "fig10_07_planning")


# Quantitative figures are defined against the experiment ledger below.


def figure_header(fig, title, subtitle):
    fig.suptitle(
        title, x=0.06, y=0.98, ha="left", fontsize=14, fontweight="bold", color=INK
    )
    fig.text(0.06, 0.915, subtitle, fontsize=9.1, color=MUTED)


def coverage(data, out):
    fig, axs = plt.subplots(1, 2, figsize=(7.6, 4.4))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.80, bottom=0.23, wspace=0.29)
    train = [e for e in data["episodes"] if e["split"] == "train"]
    tests = [e for e in data["episodes"] if e["split"] == "test"]
    d = data["bundle"]["domain"]
    samples = lambda es, k: np.concatenate(
        [np.array(e[k][:-1] if k == "temperature" else e[k]) for e in es]
    )
    T = samples(train, "temperature")
    u = samples(train, "power")
    ta = samples(train, "ambient")
    axs[0].add_patch(
        Rectangle(
            (d["temperature"][0], d["power"][0]),
            np.diff(d["temperature"])[0],
            np.diff(d["power"])[0],
            facecolor=LIGHT[0],
            edgecolor=PALETTE[0],
            lw=1,
            linestyle="--",
        )
    )
    axs[1].add_patch(
        Rectangle(
            (d["temperature"][0], d["ambient"][0]),
            np.diff(d["temperature"])[0],
            np.diff(d["ambient"])[0],
            facecolor=LIGHT[0],
            edgecolor=PALETTE[0],
            lw=1,
            linestyle="--",
        )
    )
    for ax, y in zip(axs, [u, ta]):
        ax.scatter(
            T, y, s=7, color=PALETTE[0], alpha=0.2, rasterized=True, label="训练样本"
        )
    markers = ["o", "^", "s", "D"]
    names = ["常规测试", "环境变化", "扩展动作", "高温初值"]
    for i, e in enumerate(tests):
        for ax, y in zip(axs, [e["power"], e["ambient"]]):
            ax.scatter(
                e["temperature"][:-1],
                y,
                s=13,
                color=[INK, PALETTE[1], PALETTE[2], PALETTE[4]][i],
                alpha=0.5,
                marker=markers[i],
                linewidths=0.3,
                label=names[i],
            )
    axs[0].set(ylabel="加热功率 / kW", xlabel="区间起点温度 / °C", ylim=(-0.12, 2.6))
    axs[1].set(ylabel="环境温度 / °C", xlabel="区间起点温度 / °C")
    for ax in axs:
        style(ax)
        ax.set_xlim(27, 85)
    figure_header(
        fig,
        "训练覆盖与独立测试输入",
        "虚线框为训练变量的轴对齐范围；散点保留每个时间区间，联合分布由样本位置呈现",
    )
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(
        h,
        l,
        loc="lower center",
        bbox_to_anchor=(0.53, 0.09),
        ncol=5,
        frameon=False,
        markerscale=1.2,
        fontsize=8.4,
    )
    fig.text(
        0.06,
        0.035,
        f"训练 {len(T)} 个区间；测试 {sum(len(e['power']) for e in tests)} 个区间；每区间120 s。",
        fontsize=9,
        color=MUTED,
    )
    save(fig, out, "fig10_03_coverage")


def split_figure(data, out):
    f, a = canvas(
        "按完整轨迹划分数据",
        "初始状态、随机种子、动作序列随轨迹整体分配；窗口只在所属轨迹内部展开",
    )
    specs = [
        ("calibration", "机理标定", 0),
        ("train", "网络训练", 1),
        ("validation", "开发验证", 2),
        ("test", "冻结测试", 3),
    ]
    for i, (key, label, col) in enumerate(specs):
        es = [e for e in data["episodes"] if e["split"] == key]
        hours = sum(e["hours"] for e in es)
        n = sum(len(e["power"]) for e in es)
        y = 4.65 - i * 1.15
        a.add_patch(
            FancyBboxPatch(
                (0.1, y),
                4.45,
                0.9,
                boxstyle="round,pad=.02,rounding_size=.12",
                facecolor=LIGHT[col],
                edgecolor=PALETTE[col],
                lw=0.8,
            )
        )
        a.text(0.3, y + 0.61, label, weight="bold", fontsize=11)
        a.text(
            1.85, y + 0.61, f"{len(es)}条 / {hours} h", fontsize=10, color=PALETTE[col]
        )
        a.text(0.3, y + 0.20, f"{n}个区间；整条轨迹归属固定", fontsize=9.2, color=MUTED)
    a.text(5.2, 5.45, "以一条6 h轨迹为例", fontsize=11, weight="bold")
    for j, (lab, col) in enumerate(
        [("原始轨迹", 0), ("15步窗口 A", 1), ("15步窗口 B", 2)]
    ):
        yy = 4.55 - j * 0.85
        a.text(5.2, yy + 0.15, lab, fontsize=9.2, color=MUTED)
        a.plot([6.9, 9.7], [yy + 0.22] * 2, color=GRID, lw=8, solid_capstyle="round")
        x1 = 6.9 if j == 0 else 7.15 + 0.6 * (j - 1)
        x2 = 9.7 if j == 0 else x1 + 2.8 * 15 / 180
        a.plot(
            [x1, x2], [yy + 0.22] * 2, color=PALETTE[col], lw=8, solid_capstyle="butt"
        )
    a.text(6.9, 1.95, "0", ha="center", fontsize=9)
    a.text(9.7, 1.95, "6 h", ha="center", fontsize=9)
    a.text(
        5.2,
        1.25,
        "180个区间 → 181个温度状态\n15步终点误差：每条166个窗口\n30步终点误差：每条151个窗口",
        linespacing=1.6,
        fontsize=10,
        color=MUTED,
    )
    save(f, out, "fig10_04_split")


def errors_figure(data, out):
    fig, axs = plt.subplots(2, 2, figsize=(7.6, 4.8))
    fig.subplots_adjust(
        left=0.1, right=0.98, top=0.79, bottom=0.25, wspace=0.28, hspace=0.65
    )
    names = {
        "test_nominal": "a  常规测试",
        "test_ambient": "b  环境变化",
        "test_actions": "c  扩展动作",
        "test_hot": "d  高温初值",
    }
    for ax, (ep, title) in zip(axs.flat, names.items()):
        for m in ["physical", "direct", "residual"]:
            rows = sorted(
                [
                    x
                    for x in data["prediction_metrics"]
                    if x["episode"] == ep and x["model"] == m
                ],
                key=lambda x: x["horizon_steps"],
            )
            ax.plot(
                [x["horizon_steps"] for x in rows],
                [x["rmse"] for x in rows],
                color=COLORS[m],
                marker={"physical": "o", "direct": "s", "residual": "^"}[m],
                ms=4,
                lw=1.7,
                label=LABELS[m],
            )
        ax.set_title(title, loc="left", fontsize=10.5, pad=5)
        ax.set_yscale("log")
        ax.set_xticks([1, 5, 15, 30])
        ax.set(xlabel="预测跨度 / 步", ylabel="终点RMSE / K")
        style(ax)
    figure_header(
        fig,
        "从单步到多步：终点误差随跨度变化",
        "每个窗口以参考温度初始化；后续状态完全递推，使用该窗口的相同未来动作与环境",
    )
    handles, labels = axs[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.53, 0.057),
        ncol=3,
        frameon=False,
        fontsize=9,
    )
    fig.text(
        0.06,
        0.02,
        "纵轴为对数尺度。每轨迹各跨度的窗口数依次为180、176、166、151；步长120 s。",
        fontsize=8.8,
        color=MUTED,
    )
    save(fig, out, "fig10_06_errors")


def fallback_figure(data, out):
    fig, axs = plt.subplots(
        1, 2, figsize=(7.6, 4.4), gridspec_kw={"width_ratios": [1, 1.12]}
    )
    fig.subplots_adjust(left=0.09, right=0.98, top=0.79, bottom=0.24, wspace=0.4)
    run = next(
        c
        for c in data["control"]
        if c["scenario"] == "extended_power" and c["policy"] == "guarded_residual"
    )
    row = run["rows"][30]
    cs = row["candidates"]
    ax = axs[0]
    for c in cs:
        ax.scatter(
            c["action"],
            c["cost"],
            s=50,
            marker="o" if c["feasible"] else "x",
            color=PALETTE[1] if c["feasible"] else PALETTE[4],
            zorder=3,
        )
    ax.plot(
        [c["action"] for c in cs], [c["cost"] for c in cs], color=GRID, lw=1, zorder=1
    )
    selected = next(c for c in cs if abs(c["action"] - row["requested_action"]) < 1e-9)
    ax.annotate(
        f"采用 {row['action']:.1f} kW",
        (selected["action"], selected["cost"]),
        xytext=(-45, 27),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "color": PALETTE[1]},
        fontsize=9,
        color=PALETTE[1],
    )
    ax.axvspan(1.5, 2.5, color=LIGHT[4], alpha=0.8, zorder=0)
    ax.set(xlabel="恒定候选功率 / kW", ylabel="候选综合代价 J / K²", xlim=(-0.1, 2.5))
    ax.set_title("a  扩展动作工况：1.00 h", loc="left", fontsize=10.5)
    style(ax)
    hot = next(
        c
        for c in data["control"]
        if c["scenario"] == "hot_start" and c["policy"] == "guarded_residual"
    )
    ax = axs[1]
    labels = ["公共温度联锁", "机理反馈实际执行", "模型规划执行"]
    cols = [PALETTE[4], PALETTE[2], PALETTE[1]]
    for j, fn in enumerate(
        [
            lambda r: r["interlock"],
            lambda r: r["fallback_executed"],
            lambda r: not r["interlock"] and not r["fallback"],
        ]
    ):
        mask = [r["step"] for r in hot["rows"] if fn(r)]
        for k in mask:
            ax.broken_barh(
                [(k / 30, 1 / 30)],
                (j - 0.25, 0.5),
                facecolors=cols[j],
                edgecolors="none",
            )
        ax.text(4.04, j, f"{len(mask)}次", va="center", fontsize=9, color=cols[j])
    ax.set(
        yticks=[0, 1, 2],
        yticklabels=labels,
        xlim=(-0.04, 4.7),
        ylim=(2.6, -0.7),
        xlabel="实际执行时刻 / h",
    )
    ax.set_xticks([0, 1, 2, 3, 4])
    ax.set_title("b  高温初值：120次执行", loc="left", fontsize=10.5)
    style(ax, grid="x")
    ax.tick_params(axis="y", labelsize=8.9)
    figure_header(
        fig,
        "候选筛选、回退请求与最终执行",
        "域保护使用训练轴对齐范围；执行层统一检查观测温度≥80 °C时的零功率联锁",
    )
    fig.text(0.07, 0.12, "● 满足当前筛选条件    × 域外候选", fontsize=9, color=MUTED)
    m = hot["metrics"]
    fig.text(
        0.07,
        0.055,
        f"高温：回退请求 {m['fallback_requested_count']}次 = 机理反馈实际执行 {m['fallback_executed_count']}次 + 联锁接管 {m['fallback_overridden_count']}次。",
        fontsize=9,
        color=MUTED,
    )
    save(fig, out, "fig10_08_fallback")


def closedloop_figure(data, out):
    fig = plt.figure(figsize=(7.6, 4.9))
    gs = fig.add_gridspec(
        2,
        2,
        left=0.09,
        right=0.98,
        top=0.79,
        bottom=0.18,
        wspace=0.28,
        hspace=0.5,
        height_ratios=[1.35, 1],
    )
    axs = [
        fig.add_subplot(gs[0, 0]),
        fig.add_subplot(gs[1, 0]),
        fig.add_subplot(gs[:, 1]),
    ]
    sc = next(s for s in data["control_scenarios"] if s["id"] == "nominal")
    t = np.arange(121) / 30
    for p in ["rule", "physical", "direct", "residual", "guarded_residual"]:
        run = next(
            c
            for c in data["control"]
            if c["scenario"] == "nominal" and c["policy"] == p
        )
        ls = "--" if p == "guarded_residual" else "-"
        axs[0].plot(
            t,
            [sc["initial"]] + [x["T_after"] for x in run["rows"]],
            label=LABELS[p],
            lw=1.5,
            color=COLORS[p],
            ls=ls,
        )
        if p in ["rule", "residual"]:
            axs[1].step(
                t,
                [x["action"] for x in run["rows"]] + [run["rows"][-1]["action"]],
                where="post",
                lw=1,
                color=COLORS[p],
                label=LABELS[p],
            )
    axs[0].plot(t, sc["target"], color=INK, ls=":", lw=1.4, label="目标")
    axs[0].set(ylabel="温度 / °C", xlim=(0, 4))
    axs[0].set_title("a  常规工况的实际闭环", loc="left", fontsize=10.5)
    axs[1].set(
        xlabel="实际执行时间 / h", ylabel="动作 / kW", xlim=(0, 4), ylim=(-0.1, 1.65)
    )
    axs[1].legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    policies = ["rule", "physical", "direct", "residual", "guarded_residual"]
    xx = np.arange(3)
    for j, p in enumerate(policies):
        vals = [
            next(c for c in data["control"] if c["scenario"] == s and c["policy"] == p)[
                "metrics"
            ]["rmse_K"]
            for s in ["nominal", "extended_power", "hot_start"]
        ]
        axs[2].bar(
            xx + (j - 2) * 0.14, vals, width=0.13, color=COLORS[p], label=LABELS[p]
        )
    axs[2].set(
        xticks=xx,
        xticklabels=["常规", "扩展动作", "高温初值"],
        ylabel="实际跟踪RMSE / K",
        ylim=(0, 10.6),
    )
    axs[2].set_title("b  相同场景的任务指标", loc="left", fontsize=10.5)
    for ax in axs:
        style(ax)
    figure_header(
        fig,
        "预测器进入控制闭环：同时查看轨迹与任务结果",
        "每种方法均在独立参考环境执行120次动作；模型评价与闭环评价分别登记",
    )
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(
        h,
        l,
        loc="lower center",
        bbox_to_anchor=(0.54, 0.055),
        ncol=6,
        frameon=False,
        fontsize=8,
    )
    fig.text(
        0.06,
        0.018,
        "跟踪RMSE以120个动作终点相对目标计算；常规工况三个神经控制轨迹接近重合，按线型区分。",
        fontsize=8.7,
        color=MUTED,
    )
    save(fig, out, "fig10_09_closedloop")


def ood_figure(data, out):
    from model import predict

    fig, axs = plt.subplots(1, 2, figsize=(7.6, 4.4))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.79, bottom=0.25, wspace=0.3)
    ep = next(e for e in data["episodes"] if e["id"] == "test_hot")
    h = 30
    for m in ["direct", "residual"]:
        errors = []
        for k in range(len(ep["power"]) - h + 1):
            state = ep["temperature"][k]
            for j in range(h):
                state = predict(
                    data["bundle"]["models"][m],
                    state,
                    ep["power"][k + j],
                    ep["ambient"][k + j],
                )
            errors.append(state - ep["temperature"][k + h])
        axs[0].plot(
            np.arange(len(errors)) / 30,
            errors,
            lw=1.9,
            color=COLORS[m],
            label=LABELS[m],
        )
    axs[0].axhline(0, color=MUTED, lw=0.8, ls="--")
    axs[0].set(xlabel="预测窗口起点 / h", ylabel="30步终点有符号误差 / K")
    axs[0].set_title("a  高温测试：151个窗口", loc="left", fontsize=10.5)
    axs[0].legend(frameon=False, fontsize=9)
    ids = ["test_nominal", "test_ambient", "test_actions", "test_hot"]
    xx = np.arange(4)
    for j, m in enumerate(["direct", "residual"]):
        vals = [
            100
            * next(
                x
                for x in data["prediction_metrics"]
                if x["episode"] == eid and x["model"] == m and x["horizon_steps"] == 30
            )["empirical_coverage"]
            for eid in ids
        ]
        bars = axs[1].bar(xx + (j - 0.5) * 0.35, vals, width=0.32, color=COLORS[m])
        for bar, v in zip(bars, vals):
            axs[1].text(
                bar.get_x() + bar.get_width() / 2,
                v + 2,
                f"{v:.0f}",
                ha="center",
                fontsize=8.5,
                color=COLORS[m],
            )
    axs[1].set(
        xticks=xx,
        xticklabels=["常规", "环境", "动作", "高温"],
        ylabel="测试窗口落入经验包络的比例 / %",
        ylim=(0, 115),
    )
    axs[1].set_title("b  固定验证包络的外推表现", loc="left", fontsize=10.5)
    for ax in axs:
        style(ax)
    figure_header(
        fig,
        "保留域外反例：误差与经验包络的适用范围",
        "包络半宽固定为验证集30步绝对误差的95%经验分位数，随后在独立测试窗口统计覆盖",
    )
    bands = data["bundle"]["empirical_bands"]
    fig.text(
        0.06,
        0.13,
        f"30步包络半宽：纯数据 {bands['direct']['30']:.5f} K；残差 {bands['residual']['30']:.5f} K。",
        fontsize=9,
        color=MUTED,
    )
    hot = {
        x["model"]: x["rmse"]
        for x in data["prediction_metrics"]
        if x["episode"] == "test_hot" and x["horizon_steps"] == 30
    }
    fig.text(
        0.06,
        0.065,
        f"高温30步RMSE：纯数据{hot['direct']:.3f} K、残差{hot['residual']:.3f} K；此工况保留方法排序改变的证据。",
        fontsize=9,
        color=MUTED,
    )
    fig.text(
        0.06,
        0.025,
        "经验包络描述本次验证误差分布；测试覆盖分母为每个工况的151个窗口。",
        fontsize=8.7,
        color=MUTED,
    )
    save(fig, out, "fig10_10_ood")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results", type=Path, default=ROOT / "results/ch10/experiment.json"
    )
    parser.add_argument("--out", type=Path, default=ROOT / "assets/ch10")
    args = parser.parse_args()
    setup()
    plt.rcParams["svg.hashsalt"] = "chapter10-v1"
    data = json.loads(args.results.read_text(encoding="utf-8"))
    schematic_reference(args.out)
    coverage(data, args.out)
    split_figure(data, args.out)
    schematic_models(args.out)
    errors_figure(data, args.out)
    schematic_planning(args.out)
    fallback_figure(data, args.out)
    closedloop_figure(data, args.out)
    ood_figure(data, args.out)
    print(
        json.dumps(
            {
                "code_figures": 9,
                "formats": ["png600dpi", "svg", "pdf"],
                "output": str(args.out),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
