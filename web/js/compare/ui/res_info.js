export const RES_INFO_SOURCE_URL = "https://www.reddit.com/r/EliteMiners/comments/jordsf/basic_mining_facts_prospector_limpet_information/";

export function getResInfoDialogModel() {
  return {
    title: "Why 0.26t per percentage point outside RES?",
    summaryPoints: [
      "The comparison report uses a mining rule-of-thumb from the linked EliteMiners post rather than a value derived from your own session logs.",
      "The post assumes an A-rated prospector and treats expected yield as a combination of fragment count and fragment mineral percentage.",
      "Outside RES, the combined average works out to about 0.26 tons of refined commodity for each 1% shown on the prospector readout.",
    ],
    tables: [
      {
        title: "Fragment Count",
        description: "Average fragment count per asteroid with an A-rated prospector. Higher counts usually mean more total refined yield from the same rock.",
        columns: ["Area", "Average Fragments"],
        rows: [
          ["Hazardous", "50.5"],
          ["High", "47"],
          ["Regular", "42"],
          ["Low", "38"],
          ["Outside", "35"],
        ],
      },
      {
        title: "Fragment Mineral Scaling",
        description: "Average fraction of the prospector's displayed mineral percentage that ends up in mined fragments. Higher scaling means richer fragments.",
        columns: ["Area", "Average Scaling"],
        rows: [
          ["Hazardous", "105%"],
          ["High", "97.5%"],
          ["Regular", "90%"],
          ["Low", "82.5%"],
          ["Outside", "75%"],
        ],
      },
      {
        title: "Yield Multiplier",
        description: "Rule-of-thumb tons per percentage point. Multiply the displayed mineral percent by this value to estimate refined tons from that asteroid on average.",
        columns: ["Area", "Tons per Percentage Point"],
        rows: [
          ["Hazardous", "0.53 t"],
          ["High", "0.46 t"],
          ["Regular", "0.38 t"],
          ["Low", "0.31 t"],
          ["Outside", "0.26 t"],
        ],
      },
    ],
    closingNote: "These values are averaged heuristics from the linked thread, so individual asteroids can still vary quite a bit.",
    sourceUrl: RES_INFO_SOURCE_URL,
  };
}
