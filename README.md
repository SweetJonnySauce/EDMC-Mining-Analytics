# EDMC Mining Analytics

[![Github All Releases](https://img.shields.io/github/downloads/SweetJonnySauce/EDMC-Mining-Analytics/total.svg)](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics/releases/latest)

EDMC Mining Analytics extends Elite Dangerous Market Connector (EDMC) with a mining-focused control panel. The plugin listens to in-game journal events to present live production metrics, highlight rock quality, and capture session history without leaving EDMC.

Please report issues on [GitHub](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics/issues). Your feedback helps shape the next release.

## Key Features
- Real-time mining dashboard showing cargo totals, tons-per-hour trends, limpets, refinements-per-minute to gauge your collection efficiency and ship context.
- Cross platform. Works on Windows and Linux.
- EDMCOverlay support built in. Track total tons per hour, RPM, % full, and limpets remaining on your HUD.
- Automated session management that starts, pauses, and resets analytics in response to journal events or user input, with optional auto-resume when activity resumes.
- Prospecting intelligence with duplicate detection, commodity histograms, and quick-glance content summaries for each asteroid.
- Integrations that help you act on the data, including Inara commodity lookups for nearest/best price (click on the commodity name in the table), EDSM lookup for reserve level and ring type, and Discord webhook summaries of completed runs.
- Optional market search for estimated sell prices with overlay and Discord summary support.
- No in-game configurations needed. Simply install it as an EDMC plugin and restart EDMC.
- Optional warning that you are in a non-metallic ring (for those laser platinum miners)
- Configurable experience covering update cadence, histogram bin size, cargo capacity inference, logging retention, and alert thresholds.
- Optional JSON session archive for deeper analysis or sharing, retained locally according to your preferences.
- Nearby Hotspot finder with integrated real-time Spansh search: type-ahead system lookup, ring/signal filters, minimum hotspot threshold, and clipboard copy shortcuts for quick in-game paste.

## Screenshots
### Minimal display when not mining
The orange "hotspot" next to the details button is how you launch the hotspot finder. 
<img width="502" height="44" alt="image" src="https://github.com/user-attachments/assets/7043d593-b72d-4041-b644-a318b031c80c" />

### Detailed mining metrics while you mine

<img width="506" height="381" alt="image" src="https://github.com/user-attachments/assets/7106b07b-020f-4bd7-9fec-e8d48b68ce23" />

### Click on %Range value to see the yield distribution of the asteroids you've prospected

<img width="685" height="228" alt="image" src="https://github.com/user-attachments/assets/00f8e485-5df8-4fe2-a752-7d782dbf3e2d" />

### Nearby Hotspot finder!

<img width="1101" height="597" alt="image" src="https://github.com/user-attachments/assets/89f806a4-bcc3-4ab6-b884-f847c517bf08" />

### Settings dialog box

<img width="1284" height="982" alt="image" src="https://github.com/user-attachments/assets/8bb31cb7-ad94-44f7-bcd0-3508a3fea2d8" />

### Summarize (ang brag) in your Discord channel

<img width="452" height="777" alt="image" src="https://github.com/user-attachments/assets/c2957523-4d9e-416d-b6fc-d65d8376a7c1" />

### Optionally, you can send HUD stats to EDMCOverlay

<img width="929" height="425" alt="image" src="https://github.com/user-attachments/assets/d98cb973-fadd-4850-abd0-25248e78e918" />



## Requirements
- [Elite Dangerous Market Connector](https://github.com/EDCD/EDMarketConnector) 6.0.0 or newer (Python 3.13 runtime).

## Installation
1. Open EDMC and choose `File → Settings → Plugins`, then click `Open Plugins Folder` to reveal your plugins directory.
2. Download the latest release or clone the repository from [GitHub](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics). Do **not** download individual files. Keep the directory structure intact (`integrations/`, `session_recorder.py`, `commodity_links.json`, etc.). 
3. Extract the `EDMC-Mining-Analytics` from the release .zip file and move it to the EDMC plugin directory.
4. Restart EDMC. The plugin appears under `Plugins → EDMC Mining Analytics` and adds a panel to the main window.

_To update, replace the contents of the `EDMC-Mining-Analytics` folder with the files from the latest release and restart EDMC._

## First Run & Configuration
- The plugin panel opens automatically in EDMC to view live metrics. The interface follows the active EDMC theme automatically with some noticable gaps that I have not been able to fix yet.
- Use the plugin preferences (within EDMC's Plugins tab) to adjust histogram bin size, refresh cadence, and refinement per minute (RPM) thresholds.
- Toggle automatic unpause behaviour, enable session logging, and define how many session files to retain.
- Configure Inara search mode and filters (carriers, surface ports) for one-click commodity lookups.
- Use the Market search tab to set Spansh filters for estimated sell prices (pad size, distance, demand, freshness).
- Provide an optional Discord webhook URL and image links to deliver session summaries, and use the built-in test button to confirm connectivity.

## Using the Plugin
- Simply start mining. The plugin recognises mining states, begins tracking tonnage, and monitors prospecting and refinement events.
- Cargo updates and limpet usage are tracked automatically, including abandoned collectors and drones launched.
- Click the commodity in the Commodities column to do an Inara search for nearest/best price for selling.
- Click the value in the `% Range` column in the Commodities table to open histograms that visualise asteroid yield % distributions.
- When you leave mining (supercruise, manual reset, etc.), the session recorder can persist a JSON summary and optionally push a Discord embed.

## Support
Questions, ideas, or bugs? Open an issue on [GitHub](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics/issues). Feedback helps shape the next release. Yes, this project is 100% vibe coded using Codex. I'm doing it as an experiment/learning experience to see what is possible.

*EDMC Mining Analytics is a community project and is not affiliated with Frontier Developments or the EDCD team.*

- Big thanks to [Aussig of BGS-Tally](https://github.com/aussig/BGS-Tally) fame for auto-update functionality examples and other bits.
- Thanks to [FCDN](https://github.com/aweeri/FCDN) for the Discord integration ideas.
- Thanks to [Leerensucher](https://github.com/Leerensucher) for the idea of having multiple images for the discord summary.
