import json, os, datetime as dt, numpy as np
from strategies import run_all, stats, CFG
HERE=os.path.dirname(os.path.abspath(__file__)); START="2026-09-25"
def build_dashboard():
    days,res=run_all(); D=[]
    for d in sorted(days):
        g=days[d]; o0=float(g.Open.iloc[0])
        mins=(g.index.hour*60+g.index.minute).values-570
        full=np.full(390,np.nan)
        b={"d":str(d),"o":o0,"m":mins.tolist(),
           "b":[[round((x-o0)*10) for x in row] for row in g[["Open","High","Low","Close"]].values.tolist()]}
        D.append(b)
    meta={"generated":dt.datetime.now().strftime("%Y-%m-%d %H:%M"),"start":START,
          "cfg":{k:CFG[k]["name"] for k in CFG},
          "stats":{k:{"all":stats(res,k),"fwd":stats(res,k,START),"last90":stats(res,k,sorted(days)[-90].isoformat() if len(days)>90 else None)} for k in CFG}}
    def clean(o):
        if isinstance(o,dict): return {k:clean(v) for k,v in o.items()}
        if isinstance(o,list): return [clean(v) for v in o]
        if isinstance(o,(np.floating,float)): return None if np.isnan(o) else round(float(o),2)
        if isinstance(o,np.integer): return int(o)
        return o
    payload=json.dumps(clean({"meta":meta,"days":D,"trades":res}),separators=(",",":"))
    html=open(os.path.join(HERE,"dashboard_template.html"),encoding="utf-8").read().replace("__DATA__",payload)
    out=os.path.join(HERE,"dashboard.html"); open(out,"w",encoding="utf-8").write(html)
    return out,res
if __name__=="__main__":
    p,_=build_dashboard(); print(p,os.path.getsize(p)//1024,"KB")
