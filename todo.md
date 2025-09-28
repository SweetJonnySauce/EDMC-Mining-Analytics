
## Must haves
- After-action analytics report
- Send after-action mining report to discord webhook
- Only track total mined. Don't need both added and total now. 
- Record where you are mining
- minimize app when not mining now works, but only collapses the boxes. 
- Limpets adandoned is counting more than it should. I think it counts failed collector limpets too. Fix this. This can be definied as starting# - current# - launched# (all types) = abandoned#

## Should haves
- % of asteroids where the commodity was present
- compare multiple runs
- break load.py into smaller files. Make sure EDMC expected methods remain in load.py
- Record each MiningRefined, LaunchDrone, and Cargo for more detailed analysis. We could use MiningRefined to estimate chunk collecting efficiency.
- Wait some time before showing prospector lost. This wait time could be user configurable.
- Hyperlink on Commodity name to do Inara search for nearest/best price (configurable)

## Could haves
- When entering a ring, check EDSM to see if you know anything about the hotspot/location
- On distribution we could also show 0% rocks?

## Nice to haves
- If limpets are purchased check to see if the quantity is close to the total size of the cargo hold. If so, you could prep a "pre-mining" workflow. This could also be determined if the ship loadout has a prospector limpet and refinery.
- If possible get nearby prices and estimate the profit obtainable.

## Additional Info
https://elite-journal.readthedocs.io/en/latest/
