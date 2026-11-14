"""Nine original vector diagrams and quantitative figures, with 600 dpi PNG exports."""

from pathlib import Path
import argparse, json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle
from visual_style import setup, style, INK, MUTED, GRID

ROOT = Path(__file__).resolve().parents[2]
C = ["#237CA3", "#15998D", "#E5A23B", "#9770B7", "#CB6268"]
LIGHT = ["#EAF4FA", "#EAF7F3", "#FCF4E4", "#F2EDF7", "#FBEFF0"]


def save(fig, out, name):
    out.mkdir(parents=True, exist_ok=True)
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(
            out / (name + "." + ext),
            dpi=600,
            metadata=(
                {"Date": None}
                if ext == "svg"
                else {"CreationDate": None, "ModDate": None} if ext == "pdf" else None
            ),
        )
    plt.close(fig)


def canvas(title, subtitle, size=(8.5, 4.8)):
    fig, ax = plt.subplots(figsize=size)
    fig.subplots_adjust(left=0.035, right=0.965, top=0.86, bottom=0.06)
    ax.set(xlim=(0, 10), ylim=(0, 6))
    ax.axis("off")
    fig.text(0.04, 0.955, title, weight="bold", size=14, color=INK)
    fig.text(0.04, 0.90, subtitle, size=9, color=MUTED)
    return fig, ax


def card(ax, x, y, w, h, title, body, idx=0):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.03,rounding_size=.12",
            lw=0.8,
            edgecolor=C[idx],
            facecolor=LIGHT[idx],
        )
    )
    ax.plot(
        [x + 0.15, x + 0.15],
        [y + 0.18, y + h - 0.18],
        c=C[idx],
        lw=3,
        solid_capstyle="round",
    )
    ax.text(x + 0.32, y + h - 0.32, title, va="top", weight="bold", size=10.2)
    ax.text(
        x + 0.32, y + h - 0.85, body, va="top", linespacing=1.65, size=9.2, color=MUTED
    )


def arrow(ax, a, b, label=None, idx=0):
    ax.add_patch(
        FancyArrowPatch(
            a,
            b,
            arrowstyle="-|>",
            mutation_scale=12,
            lw=1.2,
            color=C[idx],
            connectionstyle="arc3,rad=0",
        )
    )
    if label:
        ax.text(
            (a[0] + b[0]) / 2,
            (a[1] + b[1]) / 2 + 0.13,
            label,
            ha="center",
            size=8.3,
            color=C[idx],
        )


def main(source, out, font=None):
    setup(font)
    plt.rcParams["svg.hashsalt"] = "storage-ch09-v1"
    data = json.loads(source.read_text(encoding="utf-8"))
    f, a = canvas(
        "证据驱动的运维知识工作流", "任务字段、语料权限与只读计算各有明确入口"
    )
    card(
        a,
        0.1,
        3.45,
        2.65,
        2.0,
        "01  确定问题",
        "对象 · 日期 · 目标属性\n班组授权由系统提供",
        0,
    )
    card(
        a,
        3.55,
        3.45,
        2.65,
        2.0,
        "02  检索资料",
        "先检查生效与授权范围\n再对候选证据排序",
        1,
    )
    card(
        a,
        7.0,
        3.45,
        2.65,
        2.0,
        "03  校核回答",
        "原文定位 · 属性一致\n同属性冲突复核",
        2,
    )
    arrow(a, (2.8, 4.45), (3.5, 4.45))
    arrow(a, (6.25, 4.45), (6.95, 4.45), idx=1)
    card(
        a,
        0.1,
        0.35,
        4.2,
        1.9,
        "审阅记录",
        "文档版本、哈希、行号、参数、结果\n证据不足时记录所需补充资料",
        3,
    )
    card(
        a,
        5.4,
        0.35,
        4.25,
        1.9,
        "只读计算",
        "单位 → 参数范围 → 独立复算\n返回量值与状态，交由人员使用",
        1,
    )
    arrow(a, (8.3, 3.4), (8.3, 2.3), "计算请求", 2)
    arrow(a, (5.35, 1.3), (4.35, 1.3), idx=3)
    save(f, out, "fig09_02_workflow")
    f, axs = plt.subplots(
        2, 1, figsize=(8.5, 4.8), gridspec_kw={"height_ratios": [1.5, 1]}
    )
    f.subplots_adjust(left=0.18, right=0.96, top=0.85, bottom=0.13, hspace=0.7)
    f.text(0.04, 0.955, "版本与授权共同限定证据范围", size=14, weight="bold")
    f.text(
        0.04,
        0.90,
        "同一对象的历史值、当前值、未来值分别按查询日期解释",
        size=9,
        color=MUTED,
    )
    a = axs[0]
    a.barh(
        [2, 1, 0],
        [9, 15, 12],
        left=[0, 9, 12],
        height=0.5,
        color=[C[3], C[0], C[2]],
        alpha=0.8,
    )
    a.set(
        yticks=[0, 1, 2],
        yticklabels=["D11  未来版", "D02  现行版", "D01  历史版"],
        xticks=[0, 6, 9, 12, 18, 24],
        xticklabels=["2026-01", "07", "10", "2027-01", "07", "2028-01"],
        xlim=(0, 24),
    )
    a.axvline(10.45, color=C[4], ls="--", lw=1.3)
    a.text(10.8, 2.5, "查询：2026-11-14", size=9, color=C[4])
    style(a, "x")
    a = axs[1]
    a.axis("off")
    a.set(xlim=(-0.2, 10.2), ylim=(0, 1))
    for x, t, b, c in [
        (0, "D02：1000 kWh", "对象、授权与日期匹配", 1),
        (3.5, "D10：BAT-B", "class_b 班组资料", 3),
        (7, "D12：草稿", "授权未开放", 2),
    ]:
        a.add_patch(
            FancyBboxPatch(
                (x, 0.05),
                2.9,
                0.9,
                boxstyle="round,pad=.03",
                fc=LIGHT[c],
                ec=C[c],
                lw=0.8,
            )
        )
        a.text(x + 0.12, 0.65, t, size=9, weight="bold")
        a.text(x + 0.12, 0.25, b, size=8, color=MUTED)
    save(f, out, "fig09_03_scope")
    f, a = canvas(
        "从原文到可定位的证据卡片",
        "字符偏移采用 Unicode 字符计数；SHA-256 校验原始 UTF-8 字节",
    )
    card(
        a,
        0.1,
        0.6,
        4.45,
        4.7,
        "原始文件  D02.md",
        "第4行  ## D02-C01 额定储能量…\n第5行  BAT-A：额定储能量用于容量账本。\n第6行  事实|energy|1000|kWh\n\n分块边界：相邻二级标题之间\n保留原文字段与定位信息",
        0,
    )
    card(
        a,
        5.4,
        2.8,
        4.2,
        2.5,
        "出处卡片",
        "D02-C01 · 版本2.0 · 第4—6行\n属性 energy / 数值1000 / 单位kWh\n文件哈希与语料清单逐项对应",
        1,
    )
    card(
        a,
        5.4,
        0.6,
        4.2,
        1.55,
        "支持关系",
        "引用存在 + 属性吻合 + 数值及单位吻合\n核验范围还包括权限、生效日期和冲突",
        2,
    )
    arrow(a, (4.6, 3.8), (5.35, 3.8))
    save(f, out, "fig09_04_chunk")
    f, axs = plt.subplots(1, 2, figsize=(8.5, 4.3))
    f.subplots_adjust(left=0.09, right=0.96, bottom=0.24, top=0.80, wspace=0.4)
    methods = ["bm25", "tfidf", "lsa"]
    names = ["BM25", "TF–IDF", "LSA / r=12"]
    f.text(0.04, 0.955, "检索结果与回答覆盖率", size=14, weight="bold")
    f.text(
        0.04,
        0.90,
        "36道冻结测试题；30道有参考证据，6道参考状态为证据不足",
        size=9,
        color=MUTED,
    )
    for a, keys, title in [
        (axs[0], ["recall_at_3", "mrr_at_3"], "(a)  检索质量 / 有证据题"),
        (axs[1], ["answer_coverage", "status_accuracy"], "(b)  回答行为 / 全部题"),
    ]:
        for j, key in enumerate(keys):
            vals = [data["metrics"]["test"][m][key] * 100 for m in methods]
            x = np.arange(3) + (j - 0.5) * 0.32
            a.bar(x, vals, 0.29, color=C[j])
            for xx, v in zip(x, vals):
                a.text(xx, v + 2, f"{v:.1f}", ha="center", size=8.2)
        a.set(
            xticks=np.arange(3),
            xticklabels=names,
            ylim=(0, 110),
            yticks=[0, 25, 50, 75, 100],
            ylabel="%",
        )
        a.set_title(title, loc="left", pad=12)
        style(a)
        a.legend(
            ["Recall@3", "MRR@3"] if a is axs[0] else ["有据回答覆盖率", "状态正确率"],
            loc="upper center",
            bbox_to_anchor=(0.5, -0.18),
            ncol=2,
            frameon=False,
        )
    save(f, out, "fig09_05_metrics")
    f, a = plt.subplots(figsize=(8.5, 4.2))
    f.subplots_adjust(left=0.15, right=0.96, bottom=0.22, top=0.78)
    test = [q for q in data["questions"] if q["split"] == "test"]
    rows = {(r["id"], r["method"]): r for r in data["rows"]}
    mat = np.array(
        [[int(rows[(q["id"], m)]["status_correct"]) for q in test] for m in methods]
    )
    from matplotlib.colors import ListedColormap

    a.imshow(mat, cmap=ListedColormap([C[2], C[1]]), aspect="auto", vmin=0, vmax=1)
    a.set(
        yticks=range(3),
        yticklabels=names,
        xticks=range(0, 36, 3),
        xticklabels=[test[i]["id"].replace("TEST", "T") for i in range(0, 36, 3)],
        xlabel="冻结测试题编号",
    )
    a.set_xticks(np.arange(-0.5, 36, 1), minor=True)
    a.set_yticks(np.arange(-0.5, 3, 1), minor=True)
    a.grid(which="minor", color="white", lw=1.1)
    a.tick_params(which="minor", bottom=False, left=False)
    f.text(0.04, 0.955, "逐题查看状态判断的成功与缺口", size=14, weight="bold")
    f.text(
        0.04,
        0.90,
        "绿色：与参考状态一致；橙色：检索证据不足导致的漏答。所有题目保留在结果账本中。",
        size=9,
        color=MUTED,
    )
    save(f, out, "fig09_06_matrix")
    f, a = canvas("引用核验与冲突处理", "模板回答、可选生成接口共用同一份证据检查规则")
    card(
        a, 0.1, 3.9, 3.0, 1.65, "候选回答", "量值、单位、属性、块号\n原文与文件哈希", 0
    )
    card(a, 3.6, 3.9, 2.8, 1.65, "逐项核验", "范围与出处一致\n主张与事实一致", 1)
    card(a, 7, 3.9, 2.65, 1.65, "补充属性审计", "遍历有效范围\n检查同属性冲突", 2)
    arrow(a, (3.15, 4.7), (3.55, 4.7))
    arrow(a, (6.45, 4.7), (6.95, 4.7))
    for x, t, b, c in [
        (0.1, "有据回答", "给出量值与原文位置\n供人员理解和复算", 1),
        (3.6, "资料冲突", "展示45与47 °C及各自出处\n记录采用版本的待决事项", 2),
        (7, "证据待补", "说明范围与目标属性\n记录检索缺口或资料缺口", 3),
    ]:
        card(a, x, 0.6, 2.65, 2.15, t, b, c)
    a.plot([8.3, 8.3, 1.45], [3.85, 3.2, 3.2], color=MUTED, lw=1)
    arrow(a, (1.45, 3.2), (1.45, 2.8), idx=1)
    arrow(a, (4.95, 3.2), (4.95, 2.8), idx=2)
    arrow(a, (8.3, 3.2), (8.3, 2.8), idx=3)
    save(f, out, "fig09_07_claims")
    f, axs = plt.subplots(1, 2, figsize=(8.5, 4.5))
    f.subplots_adjust(left=0.10, right=0.97, bottom=0.2, top=0.77, wspace=0.4)
    f.text(0.04, 0.955, "单位一致的只读计算", size=14, weight="bold")
    f.text(
        0.04,
        0.90,
        "电量折算到交流负荷端；水体蓄热量采用恒定比热的显热近似",
        size=9,
        color=MUTED,
    )
    soc = np.linspace(0.2, 1, 100)
    axs[0].plot(soc * 100, 1000 * (soc - 0.2) * 0.95 / 300, c=C[0], lw=2)
    axs[0].fill_between(soc * 100, 1000 * (soc - 0.2) * 0.95 / 300, color=LIGHT[0])
    axs[0].scatter([80], [1.9], c=C[2], s=50, zorder=3)
    axs[0].annotate(
        "80% → 1.90 h",
        (80, 1.9),
        xytext=(45, 2.45),
        arrowprops={"arrowstyle": "-", "color": MUTED},
        size=9,
    )
    axs[0].set(xlabel="初始SOC / %", ylabel="可供能时间 / h", ylim=(0, 2.8))
    style(axs[0])
    axs[0].set_title("(a)  1000 kWh / 300 kW", loc="left")
    dt = np.linspace(0, 10, 100)
    axs[1].plot(dt, 20 * 1000 * 4.18 * dt / 3600, c=C[1], lw=2)
    axs[1].fill_between(dt, 20 * 1000 * 4.18 * dt / 3600, color=LIGHT[1])
    axs[1].scatter([6], [139.333], c=C[2], s=50, zorder=3)
    axs[1].annotate(
        "6 K → 139.33 kWh",
        (6, 139.333),
        xytext=(0.4, 205),
        arrowprops={"arrowstyle": "-", "color": MUTED},
        size=9,
    )
    axs[1].set(xlabel="水体温差 / K", ylabel="显热储能量 / kWh", ylim=(0, 250))
    style(axs[1])
    axs[1].set_title("(b)  20 m³ / 4.18 kJ/(kg·K)", loc="left")
    save(f, out, "fig09_08_units")
    f, a = canvas(
        "有限重试与结果复核",
        "注入0.35 s延迟，首轮期限0.10 s；恢复轮期限5 s。横向布局表示事件顺序。",
    )
    card(a, 0.1, 3.6, 2.6, 1.8, "请求校验", "白名单工具\n单位与物理范围", 0)
    card(a, 3.7, 3.6, 2.6, 1.8, "第1次尝试", "延迟故障触发超时\n终止子进程并登记", 2)
    card(a, 7.2, 3.6, 2.6, 1.8, "第2次尝试", "按原参数再次计算\n独立复算后返回", 1)
    arrow(a, (2.75, 4.5), (3.65, 4.5))
    arrow(a, (6.35, 4.5), (7.15, 4.5), idx=2)
    card(
        a,
        0.1,
        0.4,
        4.45,
        1.85,
        "连续超时",
        "达到2次上限 → 返回timeout状态\n保留尝试次数、实测耗时与参数哈希",
        3,
    )
    card(
        a,
        5.35,
        0.4,
        4.45,
        1.85,
        "错误返回",
        "单位、量值或附加动作字段不符合协议\n返回invalid_result，供上层记录处理",
        4,
    )
    arrow(a, (5, 3.55), (2.35, 2.3), idx=3)
    arrow(a, (8.5, 3.55), (7.55, 2.3), idx=4)
    save(f, out, "fig09_09_retry")
    f, a = plt.subplots(figsize=(8.5, 4.8))
    f.subplots_adjust(left=0.28, right=0.95, top=0.80, bottom=0.15)
    f.text(0.04, 0.955, "工具协议与故障注入结果", size=14, weight="bold")
    f.text(
        0.04,
        0.90,
        "13个预先定义情景：4个成功、4个请求被拒、4个返回被拒、1个连续超时。",
        size=9,
        color=MUTED,
    )
    names = [
        "正常电量 / 换算 / 显热 / 恢复",
        "输入单位 / 工具 / 字段 / 布尔值",
        "返回单位 / 量值 / 字段 / 类型",
        "连续两次超时",
    ]
    vals = [4, 4, 4, 1]
    a.barh(range(4), vals, color=[C[1], C[3], C[4], C[2]], height=0.55)
    a.set(
        yticks=range(4),
        yticklabels=names,
        xticks=range(6),
        xlim=(0, 5),
        xlabel="情景数量 / 个",
    )
    a.invert_yaxis()
    style(a, "x")
    for i, v in enumerate(vals):
        a.text(v + 0.12, i, str(v), va="center", weight="bold")
    save(f, out, "fig09_10_faults")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=ROOT / "results/ch09/experiment.json")
    p.add_argument("--out", type=Path, default=ROOT / "assets/ch09")
    p.add_argument("--font", type=Path)
    a = p.parse_args()
    main(a.source, a.out, a.font)
