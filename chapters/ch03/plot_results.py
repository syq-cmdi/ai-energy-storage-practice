"""Five refined figures drawn only from the frozen evaluation files."""
from pathlib import Path
import argparse,json
import numpy as np
import visual_style as v
ROOT=Path(__file__).resolve().parent
NAMES={'rule':'稳健残差规则','logistic':'逻辑回归','isolation':'孤立森林'}
COLORS={'rule':'#C17D1F','logistic':'#087F8C','isolation':'#7954A1'}
def read_scores(data):
    rows=v.read_csv(data/'test_scores.csv')
    for r in rows:
        r['minute']=int(r['minute']);r['valid']=r['valid']=='True'
        for k in ['voltage_residual_v','channel_difference_v','temperature_residual_c','rule_score','logistic_score','isolation_score']:
            r[k]=float(r[k]) if r[k] else np.nan
    return rows

def draw(data,out,font=None):
    v.setup(font);rows=read_scores(data);m=json.loads((data/'metrics.json').read_text(encoding='utf-8'));c=json.loads((data/'threshold_candidates.json').read_text(encoding='utf-8'));plt=v.plt
    rr=[r for r in rows if r['session_id']=='D16_cooling_loss'];t=np.array([r['minute'] for r in rr]);y=np.array([r['temperature_residual_c'] for r in rr])
    fig,ax=plt.subplots(3,1,figsize=(7.6,4.9),sharex=True,gridspec_kw={'height_ratios':[2,1,1]});fig.subplots_adjust(left=.12,right=.96,top=.87,bottom=.14,hspace=.30)
    ax[0].plot(t,y,lw=1.7,color=COLORS['logistic']);ax[0].set(ylabel='温度残差 / ℃',ylim=(-.4,3.6))
    for a in ax:a.axvspan(60,130,color=COLORS['rule'],alpha=.09);a.axvspan(60,88,color='#9AA8B4',alpha=.25);a.axvspan(88,92,color=COLORS['isolation'],alpha=.12);a.axvline(92,color=COLORS['logistic'],lw=1,ls='--');v.style(a)
    ax[0].annotate('首次有效告警：92 min\n相对起点延迟32 min',xy=(92,y[92]),xytext=(103,2.75),fontsize=9,arrowprops={'arrowstyle':'->','color':v.MUTED})
    ax[1].step(t,[r['valid'] for r in rr],where='post',color=COLORS['isolation'],lw=1.7);ax[1].set(yticks=[0,1],yticklabels=['不可判定','可判定'],ylim=(-.2,1.3));ax[1].text(71,.5,'数据缺失',ha='center',fontsize=9);ax[1].text(90,.5,'重建\n窗口',ha='center',fontsize=8)
    ax[2].step(t,[r['logistic_score'] for r in rr],where='post',color=COLORS['logistic'],lw=1.5);ax[2].axhline(.7,color=COLORS['rule'],ls='--',lw=1);ax[2].set(ylabel='异常分值',yticks=[0,.7,1],ylim=(-.05,1.08),xlim=(45,145),xlabel='会话时刻 / min')
    fig.text(.12,.95,'缺失期保留异常事件，恢复后重新累积历史',weight='bold',fontsize=11.3);v.save(fig,out,'图3.3')
    rr=[r for r in rows if r['session_id']=='D13_resistance_rise'];t=[r['minute'] for r in rr]
    fig,axs=plt.subplots(3,1,figsize=(7.6,5.05),sharex=True);fig.subplots_adjust(left=.12,right=.96,top=.86,bottom=.14,hspace=.48)
    for ax,method in zip(axs,NAMES):
        ax.plot(t,[r[method+'_score'] for r in rr],lw=1.8,color=COLORS[method]);th=m['selected'][method]['threshold'];ax.axhline(th,color=v.RED,ls='--',lw=1);ax.axvspan(60,130,color=COLORS['rule'],alpha=.09);v.style(ax);ax.set_title(f'{NAMES[method]}  阈值={th:g}，连续点数={m["selected"][method]["persistence"]}',loc='left',fontsize=10);ax.set_ylabel('分值');ax.set_xlim(0,179)
    axs[-1].set_xlabel('会话时刻 / min');fig.text(.12,.95,'同一测试会话D13：分值大小须结合各自阈值解释',fontsize=11.2,weight='bold');v.save(fig,out,'图3.4')
    fig,axs=plt.subplots(2,3,figsize=(7.6,4.6));fig.subplots_adjust(left=.10,right=.97,top=.82,bottom=.15,wspace=.48,hspace=.32)
    for j,method in enumerate(NAMES):
        q=m['selected'][method]['persistence'];rr=sorted([x for x in c if x['method']==method and x['persistence']==q],key=lambda x:x['threshold']);x=[r['threshold'] for r in rr]
        for i,key in enumerate(['false_alarms_per_hour','event_recall']):
            ax=axs[i,j];ax.plot(x,[r[key] for r in rr],marker='o',ms=4,lw=1.5,color=COLORS[method]);ax.axvline(m['selected'][method]['threshold'],ls=':',color=v.MUTED,lw=1);v.style(ax)
            if i==0:ax.axhline(.1,ls='--',color=v.RED,lw=.9);ax.set_ylim(bottom=-.02);ax.set_title(f'{NAMES[method]}  q={q}',fontsize=10)
            else:ax.set_ylim(-.05,1.05);ax.set_yticks([0,.5,1]);ax.set_xlabel('检测阈值')
            if j==0:ax.set_ylabel('误报 / (次/h)' if i==0 else '事件召回率')
    fig.text(.10,.95,'仅用D09—D12选择阈值与持续点数',weight='bold',fontsize=11.2);fig.text(.10,.88,'红虚线：0.10次/h预算；竖虚线：最终选定阈值',fontsize=9.6,color=v.MUTED);v.save(fig,out,'图3.5')
    cm=np.array(m['confusion_matrix']);pct=cm/cm.sum(axis=1,keepdims=True)*100;labels=['正常','通道偏移','内阻异常','温升异常']
    fig=plt.figure(figsize=(7.6,4.8));gs=fig.add_gridspec(1,2,left=.13,right=.96,bottom=.27,top=.82,width_ratios=[1.5,1],wspace=.47);a=fig.add_subplot(gs[0]);b=fig.add_subplot(gs[1]);a.imshow(pct,cmap='Blues',vmin=0,vmax=100)
    a.set(xticks=range(4),yticks=range(4),xticklabels=labels,yticklabels=labels,xlabel='分类器输出',ylabel='构造标签');a.tick_params(axis='x',rotation=35,labelsize=9)
    for i in range(4):
        for j in range(4):a.text(j,i,f'{cm[i,j]}\n{pct[i,j]:.1f}%',ha='center',va='center',fontsize=9,color='white' if pct[i,j]>60 else v.INK)
    a.set_title('a  原始样本混淆矩阵',loc='left',fontsize=10.6)
    counts=cm.sum(axis=1);b.barh(range(4),counts,color=[v.MUTED,COLORS['rule'],COLORS['isolation'],COLORS['logistic']],height=.55);b.set(yticks=range(4),yticklabels=labels,xlabel='有效样本数',xlim=(0,3900));b.invert_yaxis();v.style(b,'x');b.set_title('b  逐类评价样本数',loc='left',fontsize=10.6)
    for i,n in enumerate(counts):b.text(n+55,i,str(n),va='center',fontsize=9.5)
    fig.text(.13,.94,'已知场景测试样本：按行归一化并保留原始计数',fontsize=11,weight='bold');fig.text(.13,.025,'排除新组合场景与不可判定时刻；不作事件命中后的样本补齐。',fontsize=9.4,color=v.MUTED);v.save(fig,out,'图3.6')
    fig,axs=plt.subplots(1,3,figsize=(7.6,3.35));fig.subplots_adjust(left=.14,right=.97,top=.75,bottom=.23,wspace=.55)
    yy=np.arange(3);keys=['event_recall','false_alarms_per_hour','delay_mean_min'];titles=['a  事件召回率','b  误报频率','c  命中事件平均延迟'];units=['比例','次 / h','min'];methods=list(NAMES)
    for j,ax in enumerate(axs):
        vals=[m['metrics'][k]['test'][keys[j]] for k in methods];ax.barh(yy,vals,color=[COLORS[k] for k in methods],height=.53);ax.invert_yaxis();v.style(ax,'x');ax.set_yticks(yy);ax.set_yticklabels([NAMES[k] for k in methods] if j==0 else []);ax.set_title(titles[j],loc='left',fontsize=10.4);ax.set_xlabel(units[j]);ax.set_xlim(0,max(vals)*1.4)
        for i,(k,num) in enumerate(zip(methods,vals)):
            label=f'{m["metrics"][k]["test"]["detected"]}/16' if j==0 else f'{num:.3f}' if j==1 else f'{num:.2f}'
            ax.text(num+max(vals)*.04,i,label,va='center',fontsize=9.5)
    fig.text(.14,.94,'冻结方法在D13—D16上的事件级比较',weight='bold',fontsize=11.2);fig.text(.14,.84,f'共同正常有效时长{m["metrics"]["isolation"]["test"]["normal_valid_hours"]:.3f} h；孤立森林漏报{m["metrics"]["isolation"]["test"]["missed"]}个事件',fontsize=9.5,color=v.MUTED);v.save(fig,out,'图3.8')
    print('5 quantitative figures generated')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=ROOT/'reference_results');p.add_argument('--out',type=Path,default=ROOT.parents[1]/'assets/ch03');p.add_argument('--font',type=Path);a=p.parse_args();draw(a.results,a.out,a.font)
