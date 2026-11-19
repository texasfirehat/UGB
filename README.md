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
| neutral (no color) | 70 °F and above | Below 70 °F is the U.S. Coast Guard's general cold-water warning level. |
| yellow | 60–69 °F | Cold water; cold shock is possible on sudden entry. Below 60 °F the Coast Guard requires its boat crews to wear protective suits. |
| orange | 50–59 °F | Cold shock is strong (Tipton et al. 1998, https://doi.org/10.1007/s004210050416). |
| red | below 50 °F | Cold shock is at its strongest around 50 °F (same study). The Coast Guard requires dry suits for its crews below 50 °F. |

Most cold-water deaths come from cold shock (the first 1–3 minutes) and swimming failure rather than hypothermia (Leuci, Tipton et al. 2026, https://doi.org/10.1152/japplphysiol.00578.2026), which is why the bands use water temperature only.

The Coast Guard crew-clothing thresholds come from secondary sources describing the Rescue and Survival Systems Manual; the manual itself could not be checked.

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
