"""
NQ 'Strong Early Breakout' forward paper-trader.
RULES (frozen 2026-09-25 - do NOT tweak after seeing forward results):
  * 1-minute bars, RTH 09:30-15:59 New York time. Data: Dukascopy USATECH (Nasdaq-100 CFD, UTC).
  * Range = high/low of 09:30-09:44 bars.
  * Take the FIRST 1-min close beyond the range after 09:45 (until 15:45).
  * Trade it ONLY if: entry bar starts <= 10:30, close is >=10% of range beyond the level,
    range >= 0.35 x ATR14 (avg daily RTH range of prior 14 days).
  * Entry = that close. Stop = range midpoint. Target = 1R (distance entry->stop). Flat 15:45.
  * If a bar touches both stop and target, stop counts first. Cost = 1 pt round trip.
Usage:  python paper_trader.py            -> update data + log any new completed days
        python paper_trader.py --backtest -> replay history (2023->) to prove the code matches
"""
import sys, os, struct, lzma, datetime as dt, requests, numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
HERE=os.path.dirname(os.path.abspath(__file__)); PKL=os.path.join(HERE,"nq_1m.pkl"); LOG=os.path.join(HERE,"paper_log.csv")
START=dt.date(2026,9,25)   # forward test starts here
COST=1.0

STATS={}
def fetch_day(day):
    import time
    u=f"https://datafeed.dukascopy.com/datafeed/USATECHIDXUSD/{day.year}/{day.month-1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    for attempt in range(6):
        try:
            r=requests.get(u,timeout=30,headers={"User-Agent":"Mozilla/5.0"})
            STATS[r.status_code]=STATS.get(r.status_code,0)+1
            if r.status_code==404 or (r.status_code==200 and not r.content): return []
            if r.status_code==200:
                d=lzma.decompress(r.content); base=dt.datetime(day.year,day.month,day.day,tzinfo=dt.timezone.utc); out=[]
                for i in range(len(d)//24):
                    t,o,c,l,h,v=struct.unpack(">IIIIIf",d[i*24:(i+1)*24])
                    out.append((base+dt.timedelta(seconds=t),o/1000,h/1000,l/1000,c/1000,v))
                return out
            time.sleep(5*(attempt+1))          # 429 / 5xx -> back off and retry
        except Exception as e:
            STATS[type(e).__name__]=STATS.get(type(e).__name__,0)+1; time.sleep(3)
    return []

HISTORY=os.path.join(HERE,"history","nq_1m.pkl.xz")
def update_data():
    if not os.path.exists(PKL) and os.path.exists(HISTORY):
        pd.read_pickle(HISTORY).to_pickle(PKL)                      # seed from the history saved in the repo
    df=pd.read_pickle(PKL) if os.path.exists(PKL) else None
    last=(df.index[-1].date()-dt.timedelta(days=3)) if df is not None else dt.date(2023,1,1)   # re-fetch last 3 days so no gaps
    days=[last+dt.timedelta(n) for n in range(0,(dt.datetime.now(dt.timezone.utc).date()-last).days+1)]
    days=[d for d in days if d.weekday()<5 or d.weekday()==6]
    rows=[]
    with ThreadPoolExecutor(2) as ex:                               # gentle: Dukascopy rate-limits shared IPs
        for out in ex.map(fetch_day,days): rows+=out
    print('download stats:',STATS,'rows:',len(rows),'days requested:',len(days))
    if rows:
        new=pd.DataFrame(rows,columns=["time","Open","High","Low","Close","Volume"]).set_index("time")
        df=new if df is None else pd.concat([df,new]); df=df[~df.index.duplicated(keep="last")].sort_index(); df.to_pickle(PKL)
    return df

def evaluate(rth_days, daily_atr, day):
    g=rth_days[day]; mins=(g.index.hour*60+g.index.minute).values
    H=g.High.values;L=g.Low.values;C=g.Close.values
    n0=(mins<585).sum(); ex=(mins<945).sum(); hi=H[:n0].max(); lo=L[:n0].min(); atr=daily_atr.get(day,np.nan)
    if np.isnan(atr): return dict(date=day,status="no ATR yet")
    for i in range(n0,ex):
        c=C[i]
        if c>hi: pos=1
        elif c<lo: pos=-1
        else: continue
        lvl=hi if pos==1 else lo; ext=pos*(c-lvl)/(hi-lo); ratio=(hi-lo)/atr; t=int(mins[i])
        info=dict(date=day,entry_time=f"{t//60:02d}:{t%60:02d}",dir="LONG" if pos==1 else "SHORT",entry=round(c,2),range_hi=round(hi,2),range_lo=round(lo,2),
                  ext=round(ext,3),range_atr=round(ratio,3))
        if not (t<=630 and ext>=0.1 and ratio>=0.35):
            info["status"]="SKIPPED (filters not met)"; info["pnl_pts"]=0.0; return info
        st=(hi+lo)/2; rk=abs(c-st)
        if rk<0.5: info["status"]="SKIPPED (risk too small)"; info["pnl_pts"]=0.0; return info
        tg=c+pos*rk; info["stop"]=round(st,2); info["target"]=round(tg,2)
        for j in range(i+1,ex):
            if pos==1:
                if L[j]<=st: info["status"]="LOSS"; info["pnl_pts"]=round(-rk-COST,2); return info
                if H[j]>=tg: info["status"]="WIN"; info["pnl_pts"]=round(rk-COST,2); return info
            else:
                if H[j]>=st: info["status"]="LOSS"; info["pnl_pts"]=round(-rk-COST,2); return info
                if L[j]<=tg: info["status"]="WIN"; info["pnl_pts"]=round(rk-COST,2); return info
        p=pos*(C[ex-1]-c)-COST; info["status"]="TIMEOUT "+("WIN" if p>0 else "LOSS"); info["pnl_pts"]=round(p,2); return info
    return dict(date=day,status="no breakout")

def build(df):
    df=df.copy(); df.index=df.index.tz_convert("America/New_York"); rth=df.between_time("09:30","15:59")
    days={}
    for k,g in rth.groupby(rth.index.date):
        if len(g)>=380 and k.weekday()<5 and (g.High.max()-g.Low.min())>0 and g.Volume.sum()>0 and g.index[-1].hour*60+g.index[-1].minute>=945+14: days[k]=g   # real, complete weekday sessions only (Dukascopy pads weekends with flat bars)
    daily=pd.DataFrame({k:dict(rng=g.High.max()-g.Low.min()) for k,g in days.items()}).T
    atr=daily.rng.rolling(14).mean().shift(1).to_dict()
    return days,atr

def summary(T):
    t=T[T.status.isin(["WIN","LOSS","TIMEOUT WIN","TIMEOUT LOSS"])]
    if len(t)==0: print("No trades yet."); return
    p=t.pnl_pts.values; w=p[p>0].sum(); l=-p[p<0].sum()
    print(f"TRADES {len(t)} | WIN RATE {100*(p>0).mean():.0f}% | PF {w/l if l else float('inf'):.2f} | NET {p.sum():.0f} pts (${p.sum()*2:,.0f} on 1 MNQ) | backtest expectation: win 61%, PF 1.74")

if __name__=="__main__":
    if "--backtest" in sys.argv:
        df=pd.read_pickle(PKL); days,atr=build(df); rows=[evaluate(days,atr,d) for d in sorted(days) if d>=dt.date(2023,1,20)]
        T=pd.DataFrame(rows); print(T.status.value_counts().to_string()); summary(T); sys.exit()
    update_data()
    from dashboard import build_dashboard
    out,res=build_dashboard()
    F=pd.DataFrame([r for r in res if r["date"]>=str(START)])
    if len(F): F.to_csv(os.path.join(HERE,"paper_log_both.csv"),index=False); print(F[["date","strat","status","dir","entry_i","entry","pnl"]].to_string(index=False))
    else: print("No completed forward sessions yet (first one closes 2026-09-25 16:00 New York).")
    for k in ("1m","5m"):
        t=[r for r in res if r["strat"]==k and r["date"]>=str(START) and r["status"] in ("WIN","LOSS","TIMEOUT WIN","TIMEOUT LOSS")]
        p=np.array([r["pnl"] for r in t]); print(k, "forward trades:",len(t), "net pts:",round(p.sum(),1) if len(t) else 0)
    print("Dashboard:",out)
