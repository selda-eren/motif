import type { RelationType, TransitionKind } from "./types";

// Visual vocabulary for relation types. Primary types get colour AND a distinct line pattern,
// so they stay distinguishable without colour.
export const RELATION_STYLE: Record<RelationType, { label: string; verb: string; color: string; dash?: string; width: number; primary: boolean }> = {
  REFRAMES:    { label: "Reframes",    verb: "reframes",       color: "var(--lapis)",      width: 2.2, primary: true },
  CONTRADICTS: { label: "Contradicts", verb: "contradicts",    color: "var(--vermilion)",  width: 1.8, dash: "5 3", primary: true },
  SUPPORTS:    { label: "Supports",    verb: "supports",       color: "var(--verdigris)",  width: 1.6, primary: true },
  REFINES:     { label: "Refines",     verb: "refines",        color: "var(--ochre)",      width: 1.2, primary: false },
  CAUSES:      { label: "Causes",      verb: "causes",         color: "var(--sepia)",      width: 1.2, dash: "1 3", primary: false },
  CHANGES_STATE: { label: "Changes state of", verb: "changes the state of", color: "var(--sepia)", width: 1.4, dash: "6 2", primary: false },
  RELATES_TO:  { label: "Relates to",  verb: "relates to",     color: "var(--faded)",      width: 1,   dash: "2 4", primary: false },
};

export const RELATION_ORDER: RelationType[] = ["REFRAMES", "CONTRADICTS", "SUPPORTS", "REFINES", "CAUSES", "CHANGES_STATE", "RELATES_TO"];

/** Roman numerals for small ordinal labels (stages, book chapters). Correct for any n >= 1 (LXXXVI for 86).
 *  Passage numbers are NOT written in Roman numerals: they are internal indices, shown as ordinary numbers. */
export function roman(n: number): string {
  const table: [number, string][] = [[1000, "m"], [900, "cm"], [500, "d"], [400, "cd"], [100, "c"], [90, "xc"],
    [50, "l"], [40, "xl"], [10, "x"], [9, "ix"], [5, "v"], [4, "iv"], [1, "i"]];
  let out = "";
  for (const [v, s] of table) while (n >= v) { out += s; n -= v; }
  return out.toUpperCase();
}

/** A passage's number as shown to readers: the 0-based index + 1, in ordinary digits. */
export const passageNo = (idx: number): string => String(idx + 1);

export const isDemo = (provenance: string) => provenance !== "model";


// Reader-facing names for the Journey's interpretive layer (not the MORe relation ontology).
export const TRANSITION_KIND: Record<TransitionKind, { label: string; gloss: string }> = {
  development: { label: "Develops", gloss: "extends or deepens an earlier idea" },
  reinterpretation: { label: "Reinterprets", gloss: "changes what an earlier idea or image means" },
  contradiction: { label: "Challenges", gloss: "opposes an earlier idea or answers an objection" },
  consequence: { label: "Draws a consequence", gloss: "follows out an implication of an earlier idea" },
  analogy: { label: "Draws a parallel", gloss: "sets up a structural parallel" },
  succession: { label: "Comes next", gloss: "follows in sequence; no stronger link is recorded" },
  unclassified: { label: "Unclassified", gloss: "the evidence does not show what kind of move this is" },
};
