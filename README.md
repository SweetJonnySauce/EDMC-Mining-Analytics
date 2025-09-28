# EDMC-Mining-Analytics

EDMC-Mining-Analytics is a plugin for Elite Dangerous Market Connector (EDMC) that tracks and analyzes your mining activities. It provides an in-game UI for monitoring mining statistics, including com[...]

This is at best an alpha script. Use at your own peril.

## Features

- Tracks mining sessions, prospecting, harvested commodities and materials.
- Displays mining analytics in a dedicated UI pane within EDMC.
- Visualizes yield distributions for mined materials with interactive histograms.
- Calculates and displays mining efficiency (tons per hour) for each commodity.
- Preferences pane for configuring histogram bin sizes and update intervals.
- Automatically detects mining state from journal events.
- Handles version checking and update notifications.

## Installation

1. **Prerequisites**:  
   - Ensure you have [Elite Dangerous Market Connector (EDMC)](https://github.com/EDCD/EDMarketConnector) installed.
   - Python 3.7+ (EDMC includes its own Python environment).
   
2. **Download the Plugin**:  
   - Download **all files** from the [repository](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics) or from a release.  
     _Note: Do **not** just download `load.py`. The plugin now requires all files in the repository to function properly._

3. **Install the Plugin**:  
   - Create a folder named `EDMC-Mining-Analytics` in EDMC's `plugins` directory:
     - On Windows:  
       Usually found at `%LOCALAPPDATA%\EDMarketConnector\plugins`
     - On Mac:  
       `~/Library/Application Support/EDMarketConnector/plugins`
   - Place **all the downloaded files** into the `EDMC-Mining-Analytics` folder.

4. **Restart EDMC**  
   - The plugin will appear in EDMC's Plugins menu.

## Usage

- Start mining in Elite Dangerous. The plugin will automatically detect mining activity and display real-time analytics.
- Use the "EDMC Mining Analytics" tab in EDMC to view and interact with your mining data.
- Configure preferences (bin sizes, update intervals) under the plugin's Preferences pane.

## Development Install

Clone the repository into your EDMC plugins directory:

```sh
git clone https://github.com/SweetJonnySauce/EDMC-Mining-Analytics.git
```

Restart EDMC to enable the plugin.

## Support & Feedback

For issues, suggestions, or contributions, please visit the [GitHub repository](https://github.com/SweetJonnySauce/EDMC-Mining-Analytics).

---

*This project is not affiliated with Frontier Developments plc or Elite Dangerous. EDMC is developed by the [EDCD](https://github.com/EDCD/EDMarketConnector) team.*
