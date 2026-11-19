# Upper Galveston Bay board

`index.html` is the whole board in one file. It needs no server code, accounts or API keys.

## What it does on each screen

- Pulls live data straight from NOAA Tides & Currents station 8770613 (Morgans Point, Barbours Cut):
  - water level, wind, water temperature and air temperature every 6 minutes
  - tide predictions (60 days ahead) every 6 hours
- Pulls active National Weather Service warnings, watches and advisories every 5 minutes (see below).
- Updates the clock, the rising/falling bar, the countdown and the "now" marker every 30 seconds.
- Shows **Stale** next to "Gauge data updated" if it hasn't reached NOAA for 30 minutes.
- Has about a year of tide predictions built in, so the tide readout still works if the internet drops.
- Catches up straight away when a screen wakes from sleep or the network comes back.

## Hosting it (pick one)

1. **Department web server or intranet.** Copy `index.html` into any folder the server already serves, and point the station screens at that address.
2. **GitHub Pages (free, public address).** Create a repository, add `index.html`, then turn on Settings → Pages → Deploy from branch. The page only shows public NOAA data.
3. **A file on the screen's PC.** Copy `index.html` to the PC and open it in Chrome or Edge, full screen with F11. This also works with no web server.

The screens need internet access to `api.tidesandcurrents.noaa.gov` and `api.weather.gov`. If station networks filter traffic, ask IT to allow both addresses.

## Weather warnings and advisories

Under the header, the board lists every active National Weather Service alert for three zones:

- **Galveston Bay (GMZ335)**, the marine zone: small craft advisories, gale and storm warnings, special marine warnings
- **Coastal Harris (TXZ313)**: Morgans Point, La Porte, west Baytown
- **Chambers (TXZ214)**: east Baytown

Tropical storm and hurricane watches and warnings are issued for both the marine and the land zones, so they appear too.

| Color | Meaning |
|---|---|
| red | any warning (for example Hurricane, Tropical Storm, Gale, Special Marine) |
| orange | any watch |
| yellow | any advisory (for example Small Craft Advisory) |
| neutral | other statements (for example Rip Current Statement) |
| amber "Alert status unknown" | the board hasn't reached the weather service for 30 minutes, so it can't confirm there are no alerts |

Warnings are listed first. Expired alerts drop off. When nothing is active, a small gray line says so with the time of the last check.

## Water temperature colors

The water temperature tile is color coded by temperature alone (no key is shown on the board; the bands are below):

| Color | Water temperature | Why this cut-off |
|---|---|---|
| neutral (no color) | 70 °F and above | Below 70 °F is the U.S. Coast Guard's general boating-safety warning level for cold water. This cut-off is not from the crew manual below. |
| yellow | 60–69 °F | Cold water; cold shock is possible on sudden entry. Coast Guard boat crews still wear a work uniform and life jacket at these temperatures. |
| orange | 50–59 °F | Cold shock is strong (Tipton et al. 1998, https://doi.org/10.1007/s004210050416). Coast Guard boat crews must wear anti-exposure coveralls or a dry suit. |
| red | below 50 °F | Cold shock is at its strongest around 50 °F (same study). Coast Guard boat crews must wear a dry suit when the air is also below 50 °F; otherwise coveralls or a dry suit. |

Most cold-water deaths come from cold shock (the first 1–3 minutes) and swimming failure rather than hypothermia (Leuci, Tipton et al. 2026, https://doi.org/10.1152/japplphysiol.00578.2026), which is why the bands use water temperature only.

### Coast Guard crew clothing rules

From the Coast Guard *Rescue and Survival Systems Manual*, COMDTINST M10470.10G (September 2014, with Change 1 of May 2015), Part 2, Chapter 3, B.2, Tables 2-5 and 2-6 (page 2-19):

| Water | Table 2-5 "50/50 Box" (units issued anti-exposure coveralls) | Table 2-6 "Flat 60 Box" (units without coveralls) |
|---|---|---|
| 60 °F and above | Work uniform and Type III life jacket, at any air temperature | Work uniform and Type III life jacket |
| 50–59 °F | Anti-exposure coveralls | Dry suit with Layer I and II undergarments, Type III life jacket and neoprene hood |
| below 50 °F | Anti-exposure coveralls if air is 50 °F or above; dry suit (as above) if air is also below 50 °F | Dry suit (as above) |

Wind is not part of either table; the manual only requires wind speed to be recorded when a unit waives the requirement. Air temperature matters only below 50 °F water, to choose between coveralls and a dry suit. The 70 °F cut-off comes from the Coast Guard's general boating-safety advice, not from this manual.

Newer editions of the manual were issued in 2020 (M10470.10H) and 2026 (10470.10I) and have not been checked; their tables may differ.

Air temperature and wind speed and direction are shown as general information only. They are not color coded.

Have your training or EMS staff review the bands before crews rely on them. To change a cut-off, edit `renderWx()` in `index.html`.

## Colors

| Item | Color | Meaning |
|---|---|---|
| Top bar | green | tide rising |
| Top bar | blue | tide falling |
| Top bar | orange | last hour before a low |
| Difference box | green | water within 0.25 ft of the prediction |
| Difference box | amber | 0.25–0.75 ft off |
| Difference box | red | 0.75 ft or more off |
| Water temp tile | neutral → yellow → orange → red | 70 °F+ → 60–69 → 50–59 → below 50 °F |

## Rebuilding the page

`index.html` is generated by two scripts in `tools/`. You only need them to refresh the year of tide predictions built into the page (the fallback used when the internet is down), or if you'd rather edit the source than `index.html` directly.

```bash
pip install requests
python3 tools/build_tide_page.py tide.html
python3 tools/make_standalone.py tide.html index.html
```

- `build_tide_page.py` holds the page's layout, styles and display code. It downloads about 13 months of NOAA predictions plus the latest gauge readings and NWS alerts, and embeds them in `tide.html`.
- `make_standalone.py` wraps that into the self-hosted `index.html` and adds the code that refreshes from NOAA and the weather service in the browser.

If you edit `index.html` directly, make the same change in `tools/build_tide_page.py`; otherwise the next rebuild will undo it. The embedded predictions cover about 13 months from the last rebuild. The live page fetches fresh predictions every 6 hours anyway, so a rebuild once a year is plenty.
