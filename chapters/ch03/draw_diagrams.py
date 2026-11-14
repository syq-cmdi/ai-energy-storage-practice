"""Editable conceptual diagrams; precise numeric results live in plot_results.py."""
from pathlib import Path
from html import escape
import argparse
INK='#183448';TEAL='#087F8C';BLUE='#3466B0';AMBER='#C17D1F';PURPLE='#7954A1';MUTED='#526A7A';GRAY='#D9E4EB'
def txt(x,y,s,size=26,color=INK,anchor='start',weight=400):return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{escape(str(s))}</text>'
def rect(x,y,w,h,fill='white',stroke=GRAY,r=10):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
def line(x,y,a,b,c=MUTED,arrow=False):return f'<path d="M{x},{y} L{a},{b}" fill="none" stroke="{c}" stroke-width="2.5"'+(' marker-end="url(#a)"' if arrow else '')+'/>'
def card(x,y,w,title,lines,c):
 s=rect(x,y,w,150,'white',c)+rect(x,y,w,10,c,c,2)+txt(x+22,y+49,title,29,c,weight=600)
 for i,t in enumerate(lines):s+=txt(x+22,y+91+i*34,t,25)
 return s

def save(out,n,h,s):
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="{h}" viewBox="0 0 1440 {h}"><defs><marker id="a" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="8" markerHeight="8" orient="auto"><path d="M1 1 L11 6 L1 11" fill="none" stroke="{MUTED}" stroke-width="1.5"/></marker></defs><rect width="1440" height="{h}" fill="white"/><g font-family="PingFang SC, Microsoft YaHei, Noto Sans CJK SC, Noto Sans CJK JP, sans-serif">{s}</g></svg>'
 (out/f'图{n}.svg').write_text(svg,encoding='utf-8')
def draw(out):
 out.mkdir(parents=True,exist_ok=True)
 s=txt(38,48,'按设备留出，再沿时间生成可用证据',34,TEAL,weight=600)
 for x,title,ls,c in [(38,'连续传感器记录',['电压A/B · 电流 · 温度','统一时标与单位'],BLUE),(393,'数据有效性门控',['缺失 → 不可判定','恢复 → 重建5点窗口'],PURPLE),(748,'因果特征与分值',['仅用当前及此前样本','规则 / 分类 / 孤立森林'],TEAL),(1103,'告警与待核查假设',['阈值 + 连续点数','证据冲突时保留未知'],AMBER)]:s+=card(x,98,298,title,ls,c)
 for x in [336,691,1046]:s+=line(x+4,173,x+48,173,arrow=True)
 s+=txt(38,315,'学习与评价协议',30,INK,weight=600)
 for x,title,ls,c in [(38,'D01—D08 训练',['8设备 × 6会话','拟合缩放、分类器和正常分布'],BLUE),(518,'D09—D12 选择',['4设备 × 6会话','按事件召回与误报预算选阈值'],TEAL),(998,'D13—D16 测试',['4设备 × 7会话','冻结后加入新组合与缺失压力'],AMBER)]:s+=card(x,350,403,title,ls,c)
 s+=line(443,424,505,424,arrow=True)+line(923,424,986,424,arrow=True)
 s+=rect(38,555,1363,104,'#F5F8FA')+txt(65,599,'会话内部窗口不跨设备、不跨会话；测试事件目录只用于评分。',29)+txt(65,636,'训练和阈值选择结束后冻结配置，再报告测试误报、漏报、延迟及不可判定时长。',25,MUTED)
 save(out,'3.2',700,s)
 s=txt(38,48,'从异常线索到待核查假设',34,TEAL,weight=600)
 for x,title,ls,c in [(38,'电压通道一致性',['A与B是否共同变化','单通道偏移提供传感器线索'],BLUE),(518,'负载与模型残差',['共同压降是否随电流增大','检查标称参数及接触条件'],AMBER),(998,'热响应与环境条件',['温度残差与散热条件','复测温度并核对环境输入'],PURPLE)]:s+=card(x,93,403,title,ls,c)
 for x in [240,720,1200]:s+=line(x,247,x,292)+line(x,292,720,292)
 s+=line(720,292,720,328,arrow=True)+rect(340,341,760,120,'#EAF6F5',TEAL)+txt(720,378,'证据条件 + 分类器输出的一致性检查',30,TEAL,'middle',600)+txt(720,414,'完整数据 · 当前告警 · 单一特征签名',25,INK,'middle')+txt(720,448,'输出相符 · 最大类别分值≥0.80',25,INK,'middle')
 s+=line(540,465,540,497)+line(540,497,316,497)+line(316,497,316,535,arrow=True)
 s+=line(900,465,900,497)+line(900,497,1104,497)+line(1104,497,1104,535,arrow=True)
 s+=txt(390,484,'满足',24,TEAL)+txt(980,484,'冲突或不足',24,PURPLE)
 s+=card(38,550,560,'形成待核查假设',['标记支持证据、时刻与建议复测项','现场原因仍由独立测量和检查确认'],TEAL)
 s+=card(842,550,560,'保留未知或数据不可用',['原因解释由独立证据支持','安排独立电压、温度及连接状态核查'],PURPLE)
 save(out,'3.7',740,s)
 print('2 conceptual diagrams generated')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[2]/'assets/ch03');a=p.parse_args();draw(a.out)
