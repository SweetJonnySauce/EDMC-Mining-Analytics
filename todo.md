
## Must haves
- After-action analytics report
- Send after-action mining report to discord webhook
- Find total cargo size on ship swap (if possible) and keep it handy. ShipyardSwap: {"timestamp":"2025-09-28T17:04:22Z","event":"ShipyardSwap","ShipType":"corsair","ShipID":82,"StoreOldShip":"Python","StoreShipID":68,"MarketID":blah}
- Prospectors: Provide a user configurable option for how long it should wait to count a prospector as lost.
- Versioning: Move versioning to its own file.
- Metrics: Calculate collection efficiency based on timing of multiple MiningRefined events. 


## Should haves
- compare multiple runs
- Record each MiningRefined, LaunchDrone, and Cargo for more detailed analysis. We could use MiningRefined to estimate chunk collecting efficiency.
- Wait some time before showing prospector lost. This wait time could be user configurable.
- Hyperlink on Commodity name to do Inara search for nearest/best price (configurable)
- Add material to the total you have so you can see how full you are. 

## Could haves
- When entering a ring, check EDSM to see if you know anything about the hotspot/location
- On distribution we could also show 0% rocks?

## Nice to haves
- If limpets are purchased check to see if the quantity is close to the total size of the cargo hold. If so, you could prep a "pre-mining" workflow. This could also be determined if the ship loadout has a prospector limpet and refinery.
- If possible get nearby prices and estimate the profit obtainable.

## Additional Info
https://elite-journal.readthedocs.io/en/latest/
