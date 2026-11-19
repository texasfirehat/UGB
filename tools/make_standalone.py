#!/usr/bin/env python3
"""Turn the built tide page (tide.html) into a self-hosted index.html that refreshes
itself from NOAA in the browser. Usage: make_standalone.py tide.html index.html"""
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src).read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


rep("Observed (as of last refresh) · shaded gap = difference", "Observed · shaded gap = difference")
rep("stale=age>13*60;", "stale=age>30;")
rep("Gauge data refreshed ${fmtStamp.format(t2ms(D.built))} · updates 0600 and 1800",
    "Gauge data updated ${fmtStamp.format(t2ms(D.built))} · refreshes every 6 min")

LIVE = r"""
<script>
// Live refresh straight from NOAA CO-OPS (the API allows browser requests).
// The embedded data above is the fallback if the network is down.
(function(){
  const API="https://api.tidesandcurrents.noaa.gov/api/prod/datagetter";
  const BASE="station=8770613&units=english&time_zone=gmt&format=json&application=baytown_fd_marine_board";
  const em=t=>Math.round(Date.parse(t.replace(" ","T")+":00Z")/60000);
  const ymd=d=>d.toISOString().slice(0,10).replace(/-/g,"");
  async function q(params){
    const r=await fetch(`${API}?${BASE}&${params}`,{cache:"no-store"});
    if(!r.ok) throw new Error("HTTP "+r.status);
    const x=await r.json(); if(x.error) throw new Error(x.error.message||"NOAA error");
    return x;
  }
  async function refreshGauge(){
    const [wl,wind,wt,at]=await Promise.allSettled([
      q("product=water_level&datum=MLLW&range=48"),
      q("product=wind&date=latest"),
      q("product=water_temperature&date=latest"),
      q("product=air_temperature&date=latest")]);
    let ok=false;
    if(wl.status==="fulfilled"&&wl.value.data){
      const o=wl.value.data.filter(d=>d.v!=="").map(d=>[em(d.t),Math.round(parseFloat(d.v)*100)/100]);
      if(o.length){D.obs=o; ok=true;}
    }
    if(wind.status==="fulfilled"&&wind.value.data&&wind.value.data.length){
      const d=wind.value.data[wind.value.data.length-1];
      if(d.s!=="") D.wind={t:em(d.t),s:+d.s,g:+d.g,d:+d.d,dr:d.dr};
    }
    for(const [k,r] of [["wt",wt],["at",at]]){
      if(r.status==="fulfilled"&&r.value.data&&r.value.data.length){
        const d=r.value.data[r.value.data.length-1]; if(d.v!=="") D[k]={t:em(d.t),v:+d.v};
      }
    }
    if(ok) D.built=Date.now()/60000;
    render();
  }
  async function refreshPredictions(){
    const b=new Date(Date.now()-2*86400000), e=new Date(Date.now()+60*86400000);
    const range=`&datum=MLLW&begin_date=${ymd(b)}&end_date=${ymd(e)}`;
    const [h,hl]=await Promise.all([q("product=predictions&interval=h"+range),q("product=predictions&interval=hilo"+range)]);
    if(h.predictions&&h.predictions.length&&hl.predictions&&hl.predictions.length){
      D.h0=em(h.predictions[0].t); D.h=h.predictions.map(p=>Math.round(parseFloat(p.v)*100));
      D.hl=hl.predictions.map(p=>[em(p.t),Math.round(parseFloat(p.v)*100)/100,p.type]);
      render();
    }
  }
  async function refreshAlerts(){
    const r=await fetch("https://api.weather.gov/alerts/active?zone=GMZ335,TXZ313,TXZ214&status=actual",{cache:"no-store",headers:{Accept:"application/geo+json"}});
    if(!r.ok) throw new Error("NWS HTTP "+r.status);
    const x=await r.json();
    D.alerts=(x.features||[]).map(f=>{const p=f.properties;return {id:p.id,event:p.event,severity:p.severity,headline:p.headline,areaDesc:p.areaDesc,onset:p.onset,ends:p.ends,expires:p.expires,messageType:p.messageType};});
    D.alertsAt=Date.now()/60000;
    render();
  }
  const safe=f=>()=>f().catch(err=>console.warn("NOAA refresh failed:",err));
  safe(refreshGauge)(); safe(refreshPredictions)(); safe(refreshAlerts)();
  setInterval(safe(refreshAlerts), 5*60000);
  setInterval(safe(refreshGauge), 6*60000);
  setInterval(safe(refreshPredictions), 6*3600000);
  // Screens that sleep or lose network catch up as soon as they're visible again.
  document.addEventListener("visibilitychange",()=>{ if(!document.hidden){ safe(refreshGauge)(); safe(refreshAlerts)(); } });
  window.addEventListener("online", safe(refreshGauge));
})();
</script>
"""

doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
       '<style>html{color-scheme:light}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
       '</head>\n<body>\n' + s + LIVE + '</body>\n</html>\n')
open(out, "w").write(doc)
print("wrote", out)
