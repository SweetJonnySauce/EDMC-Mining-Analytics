# EDMC Mining Analytics

EDMC Mining Analytics extends Elite Dangerous Market Connector (EDMC) with a mining-focused control panel. The plugin listens to in-game journal events to present live production metrics, highlight rock quality, and capture session history without leaving EDMC.

This is a beta release. As such, breaking changes may be introduced. Please report issues on [GitHub](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics/issues). Your feedback helps shape the next release.

## Key Features
- Real-time mining dashboard showing cargo totals, tons-per-hour trends, limpets, refinements-per-minute and ship context.
- Automated session management that starts, pauses, and resets analytics in response to journal events or user input, with optional auto-resume when activity resumes.
- Prospecting intelligence with duplicate detection, commodity histograms, and quick-glance content summaries for each asteroid.
- Integrations that help you act on the data, including Inara commodity lookups and Discord webhook summaries of completed runs.
- Configurable experience covering update cadence, histogram bin size, cargo capacity inference, logging retention, and alert thresholds.
- Optional JSON session archive for deeper analysis or sharing, retained locally according to your preferences. (currently in development)

## Screenshots
### Minimal display when not mining

<img width="501" height="39" alt="image" src="https://github.com/user-attachments/assets/287fe085-519a-4415-aa5e-4dc55c10cf7c" />

### Detailed mining metrics while you mine

<img width="611" height="508" alt="image" src="https://github.com/user-attachments/assets/7c78855c-c2f7-49ba-bfe7-ea5b39280ab1" />

### Click on %Range value to see the yield distribution of the asteroids you've prospected

<img width="685" height="228" alt="image" src="https://github.com/user-attachments/assets/00f8e485-5df8-4fe2-a752-7d782dbf3e2d" />

### Settings dialog box (admittedly, it needs a re-layout)

<img width="522" height="919" alt="image" src="https://github.com/user-attachments/assets/41c6f1f7-1b54-4f65-aaf6-c8db2b10891d" />

### Summarize (ang brag) in your Discord channel

<img width="487" height="797" alt="image" src="https://github.com/user-attachments/assets/9975568a-97a8-4d1d-ab44-5dc32948301f" />

### Optionally, you can send HUD stats to EDMCOverlay

<img width="929" height="425" alt="image" src="https://github.com/user-attachments/assets/d98cb973-fadd-4850-abd0-25248e78e918" />



## Requirements
- [Elite Dangerous Market Connector](https://github.com/EDCD/EDMarketConnector) 5.x or newer.

## Installation
1. Open EDMC and choose `File → Settings → Plugins`, then click `Open Plugins Folder` to reveal your plugins directory.
2. Download the latest release or clone the repository from [GitHub](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics). Do **not** download individual files. Keep the directory structure intact (`integrations/`, `session_recorder.py`, `commodity_links.json`, etc.). If you download a release .zip file use the contents of the folder inside the zip file. Do not copy the top level folder.
4. Create a folder named `EDMC-Mining-Analytics` inside the EDMC plugins directory if it does not already exist.
5. Copy the entire contents of the release (or clone) into that folder.
6. Restart EDMC. The plugin appears under `Plugins → EDMC Mining Analytics` and adds a panel to the main window.

_To update, replace the contents of the `EDMC-Mining-Analytics` folder with the files from the latest release and restart EDMC._

## First Run & Configuration
- The plugin panel opens automatically in EDMC to view live metrics. The interface follows the active EDMC theme automatically with some noticable gaps that I have not been able to fix yet.
- Use the plugin preferences (within EDMC's Plugins tab) to adjust histogram bin size, refresh cadence, and refinement per minute (RPM) thresholds.
- Toggle automatic unpause behaviour, enable session logging, and define how many session files to retain.
- Configure Inara search mode and filters (carriers, surface ports) for one-click commodity lookups.
- Provide an optional Discord webhook URL and image to deliver session summaries, and use the built-in test button to confirm connectivity.

## Using the Plugin
- Simply start mining. The plugin recognises mining states, begins tracking tonnage, and monitors prospecting and refinement events.
- Cargo updates and limpet usage are tracked automatically, including abandoned collectors and drones launched.
- Click the `% Range` column in the prospects table to open interactive histograms that visualise material distributions.
- When you leave mining (supercruise, manual reset, etc.), the session recorder can persist a JSON summary and optionally push a Discord embed.

## Session History & Webhooks
- Enable `Session logging` in preferences to write structured summaries to the plugin's `session_data/` directory. Retention is configurable.
- Discord webhook summaries include duration, output, RPM, prospector usage, top commodities, and materials, making it easy to share highlights.
- Use the `Test Webook` control to validate your webhook configuration without completing a full session.

## Support
Questions, ideas, or bugs? Open an issue on [GitHub](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics/issues). Feedback helps shape the next release. Yes, this project is 100% vibe coded using Codex. I'm doing it as an experiment/learning experience to see what is possible.

*EDMC Mining Analytics is a community project and is not affiliated with Frontier Developments or the EDCD team.*

- Big thanks to [Aussig of BGS-Tally](https://github.com/aussig/BGS-Tally) fame for auto-update functionality examples and other bits.
- Thanks to [FCDN](https://github.com/aweeri/FCDN) for the Discord integration ideas.

