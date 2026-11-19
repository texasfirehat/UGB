#!/usr/bin/env python3
"""Build the Morgans Point fireboat tide page from NOAA CO-OPS data.

Usage: python3 build_tide_page.py OUTPUT.html
Needs network access to api.tidesandcurrents.noaa.gov.
Embeds ~13 months of hourly + high/low predictions (so the live clock keeps
working even if refreshes stop) and the last 48 h of observed water level + wind.
"""
import datetime as dt
import json
import sys

import requests

STATION = "8770613"
API = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


def get(**params):
    base = dict(station=STATION, units="english", time_zone="gmt", format="json",
                application="fireboat_tide_board")
    base.update(params)
    for attempt in range(4):
        try:
            r = requests.get(API, params=base, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 3:
                raise


def epoch_min(t):
    d = dt.datetime.strptime(t, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp() // 60)


NWS_ZONES = "GMZ335,TXZ313,TXZ214"  # Galveston Bay (marine), Coastal Harris, Chambers


def slim_alert(p):
    return {k: p.get(k) for k in ("id", "event", "severity", "headline", "areaDesc", "onset", "ends", "expires", "messageType")}


def main(out):
    now = dt.datetime.now(dt.timezone.utc)
    begin = (now - dt.timedelta(days=2)).strftime("%Y%m%d")
    end = (now + dt.timedelta(days=400)).strftime("%Y%m%d")

    hourly = get(product="predictions", datum="MLLW", interval="h",
                 begin_date=begin, end_date=end)["predictions"]
    hilo = get(product="predictions", datum="MLLW", interval="hilo",
               begin_date=begin, end_date=end)["predictions"]

    obs, wind = [], None
    try:
        wl = get(product="water_level", datum="MLLW", range=48).get("data", [])
        obs = [[epoch_min(d["t"]), round(float(d["v"]), 2)] for d in wl if d.get("v")]
    except Exception as e:
        print("water level unavailable:", e, file=sys.stderr)
    try:
        w = get(product="wind", date="latest").get("data", [])
        if w:
            d = w[-1]
            wind = dict(t=epoch_min(d["t"]), s=float(d["s"]), g=float(d["g"]),
                        d=float(d["d"]), dr=d["dr"])
    except Exception as e:
        print("wind unavailable:", e, file=sys.stderr)

    temps = {}
    for key, product in (("wt", "water_temperature"), ("at", "air_temperature")):
        try:
            d = get(product=product, date="latest").get("data", [])
            if d and d[-1].get("v"):
                temps[key] = dict(t=epoch_min(d[-1]["t"]), v=float(d[-1]["v"]))
        except Exception as e:
            print(product, "unavailable:", e, file=sys.stderr)

    alerts, alerts_at = [], None
    try:
        r = requests.get("https://api.weather.gov/alerts/active",
                         params={"zone": NWS_ZONES, "status": "actual"},
                         headers={"User-Agent": "fireboat-tide-board", "Accept": "application/geo+json"}, timeout=30)
        r.raise_for_status()
        alerts = [slim_alert(f["properties"]) for f in r.json().get("features", [])]
        alerts_at = int(now.timestamp() // 60)
    except Exception as e:
        print("NWS alerts unavailable:", e, file=sys.stderr)

    data = dict(
        built=int(now.timestamp() // 60),
        h0=epoch_min(hourly[0]["t"]),
        h=[round(float(p["v"]) * 100) for p in hourly],  # hundredths of a foot, one per hour
        hl=[[epoch_min(p["t"]), round(float(p["v"]), 2), p["type"]] for p in hilo],
        obs=obs,
        wind=wind,
        wt=temps.get("wt"),
        at=temps.get("at"),
        alerts=alerts,
        alertsAt=alerts_at,
    )
    html = TEMPLATE.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
    with open(out, "w") as f:
        f.write(html)
    print(f"wrote {out}: {len(hourly)} hourly, {len(hilo)} hi/lo, {len(obs)} obs, wind={'yes' if wind else 'no'}, alerts={len(alerts) if alerts_at else 'unavailable'}, water temp={temps.get('wt',{}).get('v')}, air temp={temps.get('at',{}).get('v')}")


TEMPLATE = r"""<title>Upper Galveston Bay</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: a station wall board. Big "now" readout left, next-tide + conditions right, 48-hour curve full width, 3-day table below. */
:root{
  --bg:#eef2f4; --panel:#ffffff; --ink:#0f1c24; --muted:#556670; --rule:#cfd9de;
  --water:#0e6f8a; --water-fill:rgba(14,111,138,.14); --obs:#b35a00; --now:#c4211b;
  --night:rgba(15,28,36,.06); --ok:#1d7a3e; --warn:#a15c00; --rise:#1d7a3e; --fall:#1f5fae; --lowsoon:#c25e00; --slack:#0e6f8a; --on-dir:#ffffff;
  --r1:#1d7a3e; --r2:#8a6f00; --r3:#c25e00; --r4:#c4211b;
  --display:"Barlow Condensed","Arial Narrow",Arial,sans-serif;
  --body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0a1419; --panel:#112028; --ink:#e4edf1; --muted:#8fa3ad; --rule:#22363f;
  --water:#4cc3e0; --water-fill:rgba(76,195,224,.16); --obs:#f0a24a; --now:#ff5a4f;
  --night:rgba(0,0,0,.28); --ok:#5fd18a; --warn:#f0b04a; --rise:#23874a; --fall:#2a6cc0; --lowsoon:#d0680a; --slack:#16788f; --on-dir:#ffffff; --r1:#5fd18a; --r2:#e8c44a; --r3:#f08a3a; --r4:#ff5a4f; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0a1419; --panel:#112028; --ink:#e4edf1; --muted:#8fa3ad; --rule:#22363f;
  --water:#4cc3e0; --water-fill:rgba(76,195,224,.16); --obs:#f0a24a; --now:#ff5a4f;
  --night:rgba(0,0,0,.28); --ok:#5fd18a; --warn:#f0b04a; --rise:#23874a; --fall:#2a6cc0; --lowsoon:#d0680a; --slack:#16788f; --on-dir:#ffffff; --r1:#5fd18a; --r2:#e8c44a; --r3:#f08a3a; --r4:#ff5a4f; color-scheme:dark}
html,body{height:100%}
body{background:var(--bg);color:var(--ink);font-family:var(--body);font-size:clamp(14px,1.05vw,18px);line-height:1.4}
.wrap{max-width:1600px;margin:0 auto;padding-block:clamp(12px,2vw,28px);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:clamp(12px,1.4vw,20px)}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 24px;border-bottom:2px solid var(--ink);padding-bottom:8px}
h1{font-family:var(--display);font-weight:700;font-size:clamp(28px,3.2vw,56px);letter-spacing:.01em;margin:0;line-height:1;text-wrap:balance}
.sub{color:var(--muted);font-size:.95em}
.clock{font-family:var(--display);font-weight:600;font-size:clamp(28px,3.2vw,56px);font-variant-numeric:tabular-nums;line-height:1}
.clock small{font-size:.45em;color:var(--muted);font-weight:500;margin-left:6px}
.hright{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px clamp(16px,2.4vw,40px)}
.sun{display:flex;flex-wrap:wrap;gap:4px clamp(12px,1.6vw,24px);font-family:var(--display);font-weight:600;font-size:clamp(20px,1.9vw,34px);font-variant-numeric:tabular-nums;line-height:1}
.sun .sl{font-family:var(--body);font-size:.5em;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin-right:4px}
.top{display:grid;grid-template-columns:1fr 1fr;gap:clamp(12px,1.4vw,20px)}
.wx{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid var(--rule);background:var(--panel);border-radius:8px;overflow:hidden}
.wx>div{padding:clamp(12px,1.4vw,22px);min-width:0;border-right:1px solid var(--rule)}
.wx>div:last-child{border-right:0}
.wx>div{container-type:inline-size}
.wx .v{font-family:var(--display);font-weight:700;font-size:clamp(48px,6.4vw,124px);font-size:clamp(48px,19cqi,124px);white-space:nowrap;line-height:1;font-variant-numeric:tabular-nums;display:flex;align-items:center;gap:.15em}
.wx .v small{font-size:.42em;color:var(--muted);font-weight:600}
.wx .v svg{width:.6em;height:.6em;flex:none}
.wx .s{color:var(--muted);font-variant-numeric:tabular-nums;margin-top:6px;font-size:1.1em}
.wx .wtemp{--band:var(--ink)}
.wx .wtemp[data-band="2"],.wx .wtemp[data-band="3"],.wx .wtemp[data-band="4"]{background:color-mix(in srgb,var(--band) 16%,var(--panel));box-shadow:inset 0 0 0 2px var(--band)}
.wx .wtemp[data-band="2"]{--band:var(--r2)} .wx .wtemp[data-band="3"]{--band:var(--r3)} .wx .wtemp[data-band="4"]{--band:var(--r4)}
.wx .wtemp .v{color:var(--band)}
@media (max-width:600px){.wx{grid-template-columns:1fr}.wx>div{border-right:0;border-bottom:1px solid var(--rule)}}
.obsband{display:grid;grid-template-columns:1fr auto 1fr;gap:clamp(12px,2vw,32px);align-items:center}
@media (max-width:900px){.top,.obsband{grid-template-columns:1fr}}
.obs-side dl{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;margin:0 0 8px;font-variant-numeric:tabular-nums}
.obs-side dt{color:var(--muted)} .obs-side dd{margin:0;font-weight:600;text-align:right}
.delta{--sev:var(--ok);border:2px solid var(--sev);background:color-mix(in srgb,var(--sev) 14%,var(--panel));border-radius:8px;padding:clamp(12px,1.4vw,22px) clamp(16px,2.4vw,40px);text-align:center;min-width:0}
.delta[data-sev="warn"]{--sev:var(--warn)} .delta[data-sev="high"]{--sev:var(--now)}
.delta .label{color:var(--ink)}
.delta .dv{font-family:var(--display);font-weight:700;font-size:clamp(64px,7vw,130px);line-height:.95;color:var(--sev);font-variant-numeric:tabular-nums}
.delta .dl{font-family:var(--display);font-weight:700;font-size:clamp(20px,1.9vw,34px);letter-spacing:.06em;text-transform:uppercase;color:var(--sev)}
.delta .de{margin-top:6px;font-variant-numeric:tabular-nums}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:clamp(12px,1.4vw,22px);min-width:0}
.label{font-size:.78em;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:600}
.big{font-family:var(--display);font-weight:700;font-size:clamp(64px,8vw,150px);line-height:.9;font-variant-numeric:tabular-nums;display:flex;align-items:baseline;gap:.15em}
.big .u{font-size:.32em;color:var(--muted);font-weight:600}
.state{--dir:var(--slack);display:inline-flex;align-items:center;gap:.4em;font-family:var(--display);font-weight:700;font-size:clamp(22px,2.2vw,40px);letter-spacing:.04em;text-transform:uppercase;padding:.1em .5em;border-radius:4px;background:var(--dir);color:var(--on-dir);margin-top:6px}
.tidebar{--dir:var(--slack);display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 32px;background:var(--dir);color:var(--on-dir);border-radius:8px;padding:clamp(12px,1.4vw,22px) clamp(16px,2vw,32px)}
.tidebar .state{margin:0;background:transparent;padding:0;font-size:clamp(48px,6vw,110px);line-height:.95}
.tidebar .tb-next{display:grid;justify-items:end;text-align:right;font-variant-numeric:tabular-nums}
.tidebar .tb-label{font-size:.85em;letter-spacing:.09em;text-transform:uppercase;font-weight:600}
.tidebar .tb-in{font-family:var(--display);font-weight:700;font-size:clamp(44px,5vw,96px);line-height:.95}
.tidebar .tb-at{font-size:1.1em;font-weight:500}
@media (max-width:600px){.tidebar .tb-next{justify-items:start;text-align:left}}
.state[data-dir="rise"],.tidebar[data-dir="rise"]{--dir:var(--rise)} .state[data-dir="fall"],.tidebar[data-dir="fall"]{--dir:var(--fall)} .state[data-dir="lowsoon"],.tidebar[data-dir="lowsoon"]{--dir:var(--lowsoon)}
.state svg{width:.9em;height:.9em}
.meta{color:var(--muted);margin-top:8px;font-variant-numeric:tabular-nums}
.next .when{font-family:var(--display);font-weight:700;font-size:clamp(40px,4.4vw,80px);line-height:1;font-variant-numeric:tabular-nums}
.next .what{font-family:var(--display);font-weight:600;font-size:clamp(22px,2vw,36px);text-transform:uppercase;letter-spacing:.04em}
.next .in{font-size:1.15em;margin-top:4px;font-variant-numeric:tabular-nums}
.after{margin-top:10px;padding-top:10px;border-top:1px solid var(--rule);color:var(--muted);font-variant-numeric:tabular-nums}
.cond dl{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;margin:8px 0 0;font-variant-numeric:tabular-nums}
.cond dt{color:var(--muted)} .cond dd{margin:0;font-weight:600;text-align:right}
.offset{font-family:var(--display);font-weight:700;font-size:clamp(34px,3.4vw,60px);line-height:1;font-variant-numeric:tabular-nums}
.chip{display:inline-block;font-size:.75em;font-weight:600;letter-spacing:.06em;text-transform:uppercase;padding:.15em .55em;border-radius:3px;border:1px solid currentColor}
.chip.ok{color:var(--ok)} .chip.warn{color:var(--warn)}
.chart{padding:clamp(8px,1vw,16px)}
.chart-head{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;justify-content:space-between;padding:0 6px 6px}
.legend{display:flex;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:.9em}
.legend i{display:inline-block;width:18px;height:3px;vertical-align:middle;margin-right:6px;border-radius:2px}
#chart{width:100%;height:auto;display:block}
#chart text{font-family:var(--mono);fill:var(--muted);paint-order:stroke;stroke:var(--panel);stroke-width:5px;stroke-linejoin:round}
.table-wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;min-width:560px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--rule);white-space:nowrap}
th{font-size:.78em;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:600}
td.day{font-family:var(--display);font-weight:600;font-size:1.25em}
.t-h{font-weight:600} .t-l{font-weight:600}
td .ft{font-family:var(--mono);color:var(--muted);margin-left:6px;font-size:.9em}
footer{color:var(--muted);font-size:.85em;display:flex;flex-wrap:wrap;gap:6px 20px;justify-content:space-between}
footer a{color:inherit}
.alerts{display:grid;gap:8px}
.alert{--a:var(--r2);display:grid;grid-template-columns:auto 1fr auto;gap:4px 18px;align-items:baseline;border:2px solid var(--a);background:color-mix(in srgb,var(--a) 16%,var(--panel));border-radius:8px;padding:10px clamp(12px,1.6vw,22px)}
.alert[data-lvl="warning"]{--a:var(--r4)} .alert[data-lvl="watch"]{--a:var(--r3)} .alert[data-lvl="advisory"]{--a:var(--r2)} .alert[data-lvl="unknown"]{--a:var(--warn)}
.alert[data-lvl="other"]{border-color:var(--rule);background:var(--panel)} .alert[data-lvl="other"] .ev{color:var(--ink)}
.alert .ev{font-family:var(--display);font-weight:700;font-size:clamp(24px,2.4vw,42px);line-height:1;text-transform:uppercase;letter-spacing:.03em;color:var(--a)}
.alert .hd{min-width:0;font-weight:500}
.alert .until{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
.alert-none{color:var(--muted);font-size:.95em}
@media (max-width:700px){.alert{grid-template-columns:1fr}}
.banner{background:var(--now);color:#fff;padding:10px 14px;border-radius:6px;font-weight:600}
</style>

<div class="wrap">
  <header>
    <div>
      <h1>Upper Galveston Bay</h1>
      <div class="sub">Morgans Point, Barbours Cut · NOAA station 8770613 · Houston Ship Channel · heights in feet above MLLW</div>
    </div>
    <div class="hright">
      <div class="clock" id="clock">--:--<small>CT</small></div>
      <div class="sun"><span><span class="sl">Sunrise</span> <span id="sunRise">–</span></span><span><span class="sl">Sunset</span> <span id="sunSet">–</span></span></div>
    </div>
  </header>

  <div id="banner" class="banner" hidden></div>
  <section class="alerts" id="alerts" aria-live="polite"></section>

  <section class="tidebar" id="tidebar" data-dir="slack">
    <div class="state" id="state2">–</div>
    <div class="tb-next">
      <span class="tb-label" id="tbLabel">Time to next tide</span>
      <span class="tb-in" id="tbIn">–</span>
      <span class="tb-at" id="tbAt">&nbsp;</span>
    </div>
  </section>

  <section class="wx" id="wx">
    <div class="wtemp" id="wtBox"><div class="label">Water temp</div><div class="v" id="wtV">–</div><div class="s" id="wtS">&nbsp;</div>
    </div>
    <div><div class="label">Air temp</div><div class="v" id="atV">–</div><div class="s" id="atS">&nbsp;</div></div>
    <div><div class="label">Wind</div><div class="v" id="wdV">–</div><div class="s" id="wdS">&nbsp;</div></div>
  </section>

  <section class="card obsband">
    <div class="obs-main">
      <div class="label">Observed at the gauge</div>
      <div class="big"><span id="obsH">–</span><span class="u">ft</span></div>
      <div class="meta" id="obsWhen">&nbsp;</div>
    </div>
    <div class="delta" id="delta" data-sev="ok">
      <div class="label">Difference from prediction</div>
      <div class="dv" id="deltaV">–</div>
      <div class="dl" id="deltaL">&nbsp;</div>
      <div class="de" id="deltaE">&nbsp;</div>
    </div>
    <div class="obs-side">
      <dl>
        <dt id="predThenL">Predicted for the reading time</dt><dd id="predThen">–</dd>
      </dl>
      <div class="meta" id="fresh">&nbsp;</div>
    </div>
  </section>

  <section class="top">
    <div class="card now">
      <div class="label">Predicted tide now</div>
      <div class="big"><span id="nowH">–</span><span class="u">ft</span></div>
      <div class="state" id="state">–</div>
      <div class="meta" id="rate">&nbsp;</div>
    </div>
    <div class="card next">
      <div class="label">Next tide</div>
      <div class="what" id="nextWhat">–</div>
      <div class="when" id="nextWhen">–</div>
      <div class="in" id="nextIn">&nbsp;</div>
      <div class="after" id="after">&nbsp;</div>
    </div>
  </section>

  <section class="card chart">
    <div class="chart-head">
      <div class="label">Past 12 hours · next 36 hours</div>
      <div class="legend">
        <span><i style="background:var(--muted)"></i>Predicted</span>
        <span><i style="background:var(--ink)"></i>Observed (as of last refresh) · shaded gap = difference</span>
        <span><i style="background:repeating-linear-gradient(90deg,var(--ink) 0 4px,transparent 4px 7px)"></i>Now</span>
      </div>
    </div>
    <svg id="chart" viewBox="0 0 1200 360" role="img" aria-label="Tide curve, 12 hours past to 36 hours ahead"></svg>
  </section>

  <section class="card">
    <div class="label" style="margin-bottom:6px">High and low tides · next 3 days</div>
    <div class="table-wrap"><table id="table"></table></div>
  </section>

  <footer>
    <span>Predictions are astronomical. Wind and river flow move real water levels in Galveston Bay, so check the observed reading.</span>
    <span>Source: <a href="https://tidesandcurrents.noaa.gov/stationhome.html?id=8770613" target="_blank" rel="noopener">NOAA Tides &amp; Currents 8770613</a></span>
  </footer>
</div>

<script>
const D = /*__DATA__*/null;
const TZ = "America/Chicago", LAT = 29.6817, LON = -94.985;
const MIN = 60000;
const fmtTime = new Intl.DateTimeFormat("en-US",{timeZone:TZ,hour:"numeric",minute:"2-digit"});
const fmtClock = new Intl.DateTimeFormat("en-US",{timeZone:TZ,hour:"2-digit",minute:"2-digit",hour12:false});
const fmtDay = new Intl.DateTimeFormat("en-US",{timeZone:TZ,weekday:"short",month:"short",day:"numeric"});
const fmtDayKey = new Intl.DateTimeFormat("en-CA",{timeZone:TZ,year:"numeric",month:"2-digit",day:"2-digit"});
const fmtHour = new Intl.DateTimeFormat("en-US",{timeZone:TZ,hour:"numeric"});
const fmtStamp = new Intl.DateTimeFormat("en-US",{timeZone:TZ,weekday:"short",hour:"numeric",minute:"2-digit"});
const $ = id => document.getElementById(id);
const ft = v => v.toFixed(1);
const t2ms = m => m*MIN;

// Predicted height (ft) at epoch-minute t: Catmull-Rom through hourly points.
function pred(t){
  const x=(t-D.h0)/60, i=Math.floor(x), f=x-i, h=D.h;
  if(i<1||i>=h.length-2) return null;
  const p0=h[i-1],p1=h[i],p2=h[i+1],p3=h[i+2];
  return (0.5*((2*p1)+(-p0+p2)*f+(2*p0-5*p1+4*p2-p3)*f*f+(-p0+3*p1-3*p2+p3)*f*f*f))/100;
}
function dur(mins){mins=Math.max(0,Math.round(mins));const h=Math.floor(mins/60),m=mins%60;return h?`${h} h ${String(m).padStart(2,"0")} min`:`${m} min`}

// Sunrise/sunset (NOAA solar approximation), returns epoch-minutes for the CT calendar day containing ms.
function sunTimes(ms){
  const key=fmtDayKey.format(new Date(ms)); const [Y,M,Dd]=key.split("-").map(Number);
  const n=Math.round(Date.UTC(Y,M-1,Dd,12,0)/86400000+2440587.5-2451545.0); // whole Julian day number
  const Js=n-LON/360, Mn=(357.5291+0.98560028*Js)%360, Mr=Mn*Math.PI/180;
  const C=1.9148*Math.sin(Mr)+0.02*Math.sin(2*Mr)+0.0003*Math.sin(3*Mr);
  const lam=((Mn+C+180+102.9372)%360)*Math.PI/180;
  const Jt=2451545+Js+0.0053*Math.sin(Mr)-0.0069*Math.sin(2*lam);
  const dec=Math.asin(Math.sin(lam)*Math.sin(23.4397*Math.PI/180)), phi=LAT*Math.PI/180;
  const w=Math.acos((Math.sin(-0.833*Math.PI/180)-Math.sin(phi)*Math.sin(dec))/(Math.cos(phi)*Math.cos(dec)));
  const toMin=j=>Math.round((j-2440587.5)*1440);
  return {rise:toMin(Jt-w/(2*Math.PI)), set:toMin(Jt+w/(2*Math.PI))};
}

// National Weather Service alerts for Galveston Bay (GMZ335), Coastal Harris (TXZ313) and Chambers (TXZ214).
// Warnings red, watches orange, advisories yellow; other statements neutral. Older than 30 min = status unknown.
const fmtAlert = new Intl.DateTimeFormat("en-US",{timeZone:TZ,weekday:"short",hour:"numeric",minute:"2-digit"});
function alertLevel(ev){ ev=(ev||"").toLowerCase(); return ev.includes("warning")?"warning":ev.includes("watch")?"watch":ev.includes("advisory")?"advisory":"other"; }
function renderAlerts(nowMs){
  const box=$("alerts"), at=D.alertsAt, rank={warning:0,watch:1,advisory:2,other:3};
  const esc=t=>String(t||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  if(!at || nowMs/MIN-at>30){
    box.innerHTML=`<div class="alert" data-lvl="unknown"><div class="ev">Alert status unknown</div><div class="hd">Can't confirm current NWS warnings${at?` (last checked ${fmtAlert.format(t2ms(at))})`:""}. Check weather.gov or the NWS Houston/Galveston office.</div><div class="until"></div></div>`;
    return;
  }
  const list=(D.alerts||[]).filter(a=>{const end=Date.parse(a.ends||a.expires||"");return !end||end>nowMs;})
    .sort((a,b)=>rank[alertLevel(a.event)]-rank[alertLevel(b.event)]);
  if(!list.length){ box.innerHTML=`<div class="alert-none">No active NWS warnings or advisories for Galveston Bay, Coastal Harris or Chambers · checked ${fmtAlert.format(t2ms(at))}</div>`; return; }
  box.innerHTML=list.map(a=>{const lvl=alertLevel(a.event), end=a.ends||a.expires;
    const until=end?`until ${fmtAlert.format(Date.parse(end))}`:"";
    return `<div class="alert" data-lvl="${lvl}"><div class="ev">${esc(a.event)}</div><div class="hd">${esc(a.headline||a.areaDesc)}</div><div class="until">${esc(until)}</div></div>`;}).join("");
}

function render(){
  const nowMs=Date.now(), now=nowMs/MIN;
  $("clock").innerHTML=fmtClock.format(nowMs)+"<small>CT</small>";
  renderAlerts(nowMs);
  const h=pred(now);
  if(h===null){$("banner").hidden=false;$("banner").textContent="Tide predictions on this board have run out. The scheduled refresh needs attention.";return}

  // Now + state
  const slope=(pred(now+15)-pred(now-15))/0.5; // ft per hour
  const next=D.hl.find(p=>p[0]>now), prev=[...D.hl].reverse().find(p=>p[0]<=now);
  $("nowH").textContent=ft(h);
  const nearTurn=(next&&next[0]-now<25)||(prev&&now-prev[0]<25);
  const up='<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 1 9 7H1z" fill="currentColor"/></svg>';
  const dn='<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 9 1 3h8z" fill="currentColor"/></svg>';
  // Green rising; blue falling; orange in the last hour before a low (slack included).
  const dir=(next&&next[2]==="L"&&next[0]-now<=60)?"lowsoon":(slope>0?"rise":"fall");
  const stateHtml=nearTurn?"Slack":(slope>0?up+"Rising":dn+"Falling");
  for(const id of ["state","state2","tidebar"]) $(id).dataset.dir=dir;
  $("state").innerHTML=stateHtml; $("state2").innerHTML=stateHtml;
  if(next){
    $("tbLabel").textContent=`Time to next ${next[2]==="H"?"high":"low"}`;
    $("tbIn").textContent=dur(next[0]-now);
    $("tbAt").textContent=`${next[2]==="H"?"High":"Low"} ${ft(next[1])} ft at ${fmtTime.format(t2ms(next[0]))}`;
  }
  $("rate").textContent=nearTurn?"Near the turn of the tide":`${slope>0?"+":"−"}${Math.abs(slope).toFixed(2)} ft per hour`;

  // Next tide
  if(next){
    $("nextWhat").textContent=(next[2]==="H"?"High":"Low")+` · ${ft(next[1])} ft`;
    $("nextWhen").textContent=fmtTime.format(t2ms(next[0]));
    $("nextIn").textContent="in "+dur(next[0]-now);
    const n2=D.hl[D.hl.indexOf(next)+1];
    $("after").textContent=n2?`Then ${n2[2]==="H"?"high":"low"} ${ft(n2[1])} ft at ${fmtTime.format(t2ms(n2[0]))}, ${fmtDay.format(t2ms(n2[0]))}`:"";
  }

  // Observed
  const last=D.obs.length?D.obs[D.obs.length-1]:null;
  if(last){
    const pThen=pred(last[0]), off=last[1]-pThen, a=Math.abs(off);
    $("obsH").textContent=ft(last[1]);
    $("obsWhen").textContent=`Reading at ${fmtStamp.format(t2ms(last[0]))}`;
    $("predThenL").textContent=`Predicted for ${fmtTime.format(t2ms(last[0]))}`;
    $("predThen").textContent=`${ft(pThen)} ft`;
    $("delta").dataset.sev=a<0.25?"ok":a<0.75?"warn":"high";
    $("deltaV").textContent=`${off>=0?"+":"−"}${a.toFixed(1)} ft`;
    $("deltaL").textContent=a<0.25?"On prediction":(off>0?"Above prediction":"Below prediction");
    $("deltaE").textContent=a<0.25?"Water is tracking the forecast":`If it holds, water now ≈ ${ft(h+off)} ft`;
  } else {$("obsH").textContent="–";$("obsWhen").textContent="The gauge did not report at the last refresh";$("deltaV").textContent="–";$("deltaL").textContent="No reading"}
  renderWx();
  const s=sunTimes(nowMs); $("sunRise").textContent=fmtClock.format(t2ms(s.rise)); $("sunSet").textContent=fmtClock.format(t2ms(s.set));
  const age=now-D.built, stale=age>13*60;
  $("fresh").innerHTML=`<span class="chip ${stale?"warn":"ok"}">${stale?"Stale":"Current"}</span> Gauge data refreshed ${fmtStamp.format(t2ms(D.built))} · updates 0600 and 1800`;

  drawChart(now);
  drawTable(now);
}

// Water temperature color bands (USCG cold-water guidance; cold shock peaks near 50 °F, Tipton et al. 1998):
// neutral (no color) 70 °F and above, yellow 60–69, orange 50–59, red below 50. Air and wind are information only.
function windChill(tF,kt){const mph=kt*1.15078; if(tF>50||mph<=3) return tF; const v=Math.pow(mph,0.16); return 35.74+0.6215*tF-35.75*v+0.4275*tF*v;}
function renderWx(){
  const wt=D.wt, at=D.at, W=D.wind;
  const arrow=d=>`<svg viewBox="0 0 10 10" aria-hidden="true" style="transform:rotate(${(d+180)%360}deg)"><path d="M5 0 9 4.5H6.2V10H3.8V4.5H1z" fill="currentColor"/></svg>`;
  $("wtV").innerHTML=wt?`${wt.v.toFixed(1)}<small>°F</small>`:"–"; $("wtS").textContent=wt?`at ${fmtStamp.format(t2ms(wt.t))}`:"Not reported";
  $("atV").innerHTML=at?`${Math.round(at.v)}<small>°F</small>`:"–";
  $("wdV").innerHTML=W?`${arrow(W.d)}${W.dr} ${Math.round(W.s)}<small>kt</small>`:"–";
  $("wdS").textContent=W?`gusts ${Math.round(W.g)} kt · at ${fmtStamp.format(t2ms(W.t))}`:"Not reported";
  let wc=null;
  if(at){ const gust=W?Math.max(W.s,(W.s+W.g)/2):0; wc=W?windChill(at.v,gust):at.v; }
  $("atS").textContent=at?(wc!==null&&Math.round(wc)<Math.round(at.v)?`feels like ${Math.round(wc)} °F with wind`:`at ${fmtStamp.format(t2ms(at.t))}`):"Not reported";
  const band=wt?(wt.v>=70?1:wt.v>=60?2:wt.v>=50?3:4):0;
  $("wtBox").dataset.band=String(band);
}

function drawChart(now){
  const W=1200,H=360,L=52,R=12,T=26,B=34, t0=now-12*60, t1=now+36*60;
  const pts=[]; for(let t=t0;t<=t1;t+=10){const v=pred(t); if(v!==null) pts.push([t,v])}
  const obs=D.obs.filter(o=>o[0]>=t0&&o[0]<=now);
  const vals=pts.map(p=>p[1]).concat(obs.map(o=>o[1]));
  let lo=Math.min(0,...vals), hi=Math.max(...vals); const pad=(hi-lo)*0.12||0.5; lo=Math.floor((lo-pad)*2)/2; hi=Math.ceil((hi+pad)*2)/2;
  const X=t=>L+(t-t0)/(t1-t0)*(W-L-R), Y=v=>T+(hi-v)/(hi-lo)*(H-T-B);
  let s="";
  // night shading
  for(let d=-1; d<=2; d++){
    const ms=t2ms(now)+d*86400000, a=sunTimes(ms), b=sunTimes(ms+86400000);
    const x0=Math.max(L,X(a.set)), x1=Math.min(W-R,X(b.rise));
    if(x1>x0) s+=`<rect x="${x0}" y="${T}" width="${x1-x0}" height="${H-T-B}" fill="var(--night)"/>`;
  }
  // grid + y labels
  const step=(hi-lo)>3?1:0.5;
  for(let v=lo; v<=hi+1e-9; v+=step){
    s+=`<line x1="${L}" x2="${W-R}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--rule)" stroke-width="${Math.abs(v)<1e-9?1.6:1}"/>`;
    s+=`<text x="${L-8}" y="${Y(v)+4}" text-anchor="end" font-size="13">${v.toFixed(1)}</text>`;
  }
  // x ticks every 6 h on CT hours
  const firstHour=Math.ceil(t0/60)*60;
  for(let t=firstHour;t<=t1;t+=60){
    const hr=Number(fmtClock.format(t2ms(t)).slice(0,2));
    if(hr%6) continue;
    s+=`<line x1="${X(t)}" x2="${X(t)}" y1="${T}" y2="${H-B}" stroke="var(--rule)" stroke-dasharray="${hr===0?"":"2 4"}"/>`;
    s+=`<text x="${X(t)}" y="${H-B+18}" text-anchor="middle" font-size="13">${hr===0?fmtDay.format(t2ms(t)):fmtHour.format(t2ms(t))}</text>`;
  }
  // predicted area + line
  const line=pts.map((p,i)=>(i?"L":"M")+X(p[0]).toFixed(1)+" "+Y(p[1]).toFixed(1)).join("");
  s+=`<path d="${line}L${X(pts[pts.length-1][0])} ${H-B}L${X(pts[0][0])} ${H-B}Z" fill="var(--ink)" fill-opacity=".06"/>`;
  s+=`<path d="${line}" fill="none" stroke="var(--muted)" stroke-width="3" stroke-linejoin="round"/>`;
  // observed
  if(obs.length>1){
    const oPath=obs.map((o,i)=>(i?"L":"M")+X(o[0]).toFixed(1)+" "+Y(o[1]).toFixed(1)).join("");
    const back=[...obs].reverse().map(o=>"L"+X(o[0]).toFixed(1)+" "+Y(pred(o[0])).toFixed(1)).join("");
    s+=`<path d="${oPath}${back}Z" fill="var(--ink)" fill-opacity=".12"/>`;
    s+=`<path d="${oPath}" fill="none" stroke="var(--ink)" stroke-width="2.5"/>`;
    const lo_=obs[obs.length-1], yo=Y(lo_[1]), yp=Y(pred(lo_[0])), xo=X(lo_[0]), d=lo_[1]-pred(lo_[0]);
    s+=`<line x1="${xo}" x2="${xo}" y1="${yo}" y2="${yp}" stroke="var(--ink)" stroke-width="3"/>`;
    s+=`<circle cx="${xo}" cy="${yo}" r="5" fill="var(--ink)"/>`;
    if(Math.abs(yo-yp)>18) s+=`<text x="${xo-10}" y="${(yo+yp)/2+5}" text-anchor="end" font-size="16" style="fill:var(--ink);font-weight:600">${d>=0?"+":"−"}${Math.abs(d).toFixed(1)} ft</text>`;
  }
  // hi/lo markers
  for(const p of D.hl){ if(p[0]<t0||p[0]>t1) continue;
    const x=X(p[0]), y=Y(p[1]), isH=p[2]==="H", ty=isH?y-12:y+22;
    s+=`<circle cx="${x}" cy="${y}" r="4.5" fill="var(--panel)" stroke="var(--muted)" stroke-width="2.5"/>`;
    s+=`<text x="${Math.min(Math.max(x,L+40),W-R-40)}" y="${Math.min(Math.max(ty,T+10),H-B-6)}" text-anchor="middle" font-size="14" style="fill:var(--ink)">${isH?"H":"L"} ${ft(p[1])} · ${fmtTime.format(t2ms(p[0]))}</text>`;
  }
  // now
  const xn=X(now), hn=pred(now);
  s+=`<line x1="${xn}" x2="${xn}" y1="${T-8}" y2="${H-B}" stroke="var(--ink)" stroke-width="2" stroke-dasharray="6 4"/>`;
  s+=`<circle cx="${xn}" cy="${Y(hn)}" r="7" fill="var(--ink)" stroke="var(--panel)" stroke-width="2"/>`;
  s+=`<text x="${xn+8}" y="${T-10}" font-size="13" style="fill:var(--ink);font-weight:600">NOW</text>`;
  $("chart").innerHTML=s;
}

function drawTable(now){
  const rows={}, order=[];
  for(const p of D.hl){ if(p[0]<now-60) continue; const k=fmtDayKey.format(t2ms(p[0]));
    if(!rows[k]){ if(order.length===3) break; rows[k]=[]; order.push(k);} rows[k].push(p); }
  const max=Math.max(...order.map(k=>rows[k].length),2);
  let s="<thead><tr><th>Day</th>"+Array.from({length:max},(_,i)=>`<th>Tide ${i+1}</th>`).join("")+"<th>Sunrise / sunset</th></tr></thead><tbody>";
  for(const k of order){ const r=rows[k], sun=sunTimes(t2ms(r[0][0]));
    s+=`<tr><td class="day">${fmtDay.format(t2ms(r[0][0]))}</td>`;
    for(let i=0;i<max;i++){ const p=r[i]; s+= p?`<td><span class="${p[2]==="H"?"t-h":"t-l"}">${p[2]==="H"?"High":"Low"} ${fmtTime.format(t2ms(p[0]))}</span><span class="ft">${ft(p[1])} ft</span></td>`:"<td></td>"; }
    s+=`<td>${fmtTime.format(t2ms(sun.rise))} / ${fmtTime.format(t2ms(sun.set))}</td></tr>`;
  }
  $("table").innerHTML=s+"</tbody>";
}

render();
setInterval(render, 30000);
// Keep station screens awake where allowed.
try{ navigator.wakeLock && navigator.wakeLock.request("screen").catch(()=>{}) }catch(e){}
</script>
"""

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "index.html")
