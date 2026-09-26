import numpy as np, pandas as pd
from paper_trader import build, PKL
COST=1.0
CFG={"1m":dict(tf="1min",orb=15,early=630,body=None,ext=0.1,rng=0.35,stop="mid",rr=1.0,name="1-min strong early breakout"),
     "5m":dict(tf="5min",orb=15,early=None,body=0.7,ext=0.1,rng=0.35,stop="opp",rr=1.5,name="5-min strong breakout")}
def bars_for(g,tf):
    if tf=="1min": return g
    return g.resample("5min",label="left",closed="left").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
def evaluate(g,atr,key):
    c=CFG[key]; b=bars_for(g,c["tf"]); mins=(b.index.hour*60+b.index.minute).values
    O=b.Open.values;H=b.High.values;L=b.Low.values;C=b.Close.values
    n0=(mins<570+c["orb"]).sum(); ex=(mins<945).sum(); hi=H[:n0].max(); lo=L[:n0].min()
    out=dict(strat=key,range_hi=float(hi),range_lo=float(lo),status="no breakout")
    if np.isnan(atr): out["status"]="no ATR yet"; return out
    ratio=(hi-lo)/atr
    for i in range(n0,ex):
        cl=C[i]
        if cl>hi: pos=1
        elif cl<lo: pos=-1
        else: continue
        lvl=hi if pos==1 else lo; ext=pos*(cl-lvl)/(hi-lo); body=abs(C[i]-O[i])/max(H[i]-L[i],1e-9); t=int(mins[i])
        out.update(dir="LONG" if pos==1 else "SHORT",entry_i=t-570,entry=float(cl),ext=float(ext),body=float(body),range_atr=float(ratio))
        why=[]
        if c["early"] is not None and t>c["early"]: why.append("entry after 10:30")
        if c["body"] is not None and body<c["body"]: why.append("weak candle (body %.0f%%)"%(body*100))
        if ext<c["ext"]: why.append("close too near level")
        if ratio<c["rng"]: why.append("range too small (%.2f ATR)"%ratio)
        if why: out["status"]="SKIPPED"; out["why"]=", ".join(why); out["pnl"]=0.0; return out
        st=(hi+lo)/2 if c["stop"]=="mid" else (lo if pos==1 else hi); rk=abs(cl-st)
        if rk<0.5: out["status"]="SKIPPED"; out["why"]="risk too small"; out["pnl"]=0.0; return out
        tg=cl+pos*c["rr"]*rk; out.update(stop=float(st),target=float(tg),risk=float(rk))
        for j in range(i+1,ex):
            hit=None
            if pos==1:
                if L[j]<=st: hit=("LOSS",st)
                elif H[j]>=tg: hit=("WIN",tg)
            else:
                if H[j]>=st: hit=("LOSS",st)
                elif L[j]<=tg: hit=("WIN",tg)
            if hit:
                out.update(status=hit[0],exit=float(hit[1]),exit_i=int(mins[j])-570,pnl=float(pos*(hit[1]-cl)-COST)); return out
        p=pos*(C[ex-1]-cl)-COST
        out.update(status="TIMEOUT "+("WIN" if p>0 else "LOSS"),exit=float(C[ex-1]),exit_i=int(mins[ex-1])-570,pnl=float(p)); return out
    return out
def run_all():
    df=pd.read_pickle(PKL); days,atr=build(df); res=[]
    for d in sorted(days):
        for k in CFG:
            r=evaluate(days[d],atr.get(d,np.nan),k); r["date"]=str(d); res.append(r)
    return days,res
def stats(res,key,frm=None):
    p=np.array([r["pnl"] for r in res if r["strat"]==key and r["status"] in("WIN","LOSS","TIMEOUT WIN","TIMEOUT LOSS") and (frm is None or r["date"]>=frm)])
    if len(p)==0: return dict(n=0)
    w=p[p>0].sum(); l=-p[p<0].sum(); return dict(n=len(p),win=100*(p>0).mean(),pf=(w/l if l else 99),net=p.sum())
if __name__=="__main__":
    days,res=run_all()
    for k in CFG: print(k,CFG[k]["name"],stats(res,k))
