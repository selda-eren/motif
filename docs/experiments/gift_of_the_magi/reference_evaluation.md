# Reference evaluation: "The Gift of the Magi" (O. Henry)

Written 2026-10-27 **before any model output was generated** for this text. It is written from the
source text and its segmentation only (`python -m motif.cli segments gift_of_the_magi`, 6 passages).
Passage numbers are 1-based, as in the UI.

Each development has two parts:
- **Stated in the text.** Events and facts the text states outright. A reader needs no interpretation for these.
- **Interpretive expectation.** What a careful reader would infer, especially how later passages change
  what earlier ones mean. These are judgements, not facts, and other readings are possible.

## Segmentation

| Passage | Words | Content |
|---|---|---|
| P1 | 399 | $1.87, Christmas tomorrow; the flat; $20 a week; Della has saved for months to buy Jim something "worthy of the honor of being owned by Jim" |
| P2 | 300 | The pier glass; the two treasures, Jim's gold watch and Della's hair; she lets her hair down, cries, and goes out |
| P3 | 306 | Madame Sofronie buys the hair for $20; Della finds a platinum fob chain "worthy of The Watch" for $21; Jim uses an old leather strap |
| P4 | 364 | Curls "like a truant schoolboy"; Della's prayer "make him think I am still pretty"; Jim stares with an expression she "could not read" |
| P5 | 309 | "You say your hair is gone?"; "nobody could ever count my love for you"; the narrator: "The magi brought valuable gifts, but that was not among them. This dark assertion will be illuminated later on."; Jim says no haircut could make him like her less; the package |
| P6 | 379 | The combs for the hair that is gone; Della offers the chain; "I sold the watch to get the money to buy your combs"; the magi coda: "foolish children ... most unwisely sacrificed" yet "of all who give gifts these two were the wisest. They are the magi." |

**Structural risk, noted before running.** Both reveals and the coda fall in P6. So the ending can
reinterpret earlier material only through P6 to P1-P5 links. Links inside P6, such as combs to
sold watch, are within-passage and do not show retrospective change.

## Reference developments

### D1. Poverty as the constraint (P1, then P3, P5)
- **Stated in the text.** Della has $1.87 and the income has shrunk to $20 a week (P1). The hair sells for $20 and
  the chain costs $21, leaving 87 cents (P3). In P5 the narrator says: "Eight dollars a week or a million a year—what is the difference?"
- **Interpretive expectation.** Poverty is what turns a gift into a sacrifice. P5 later reframes the money as
  irrelevant to what matters between them.
- **Minimum for a hit.** A cross-passage link from the P1 poverty or $1.87 unit to the hair sale or chain purchase
  (P3), or a reframing by P5's "what is the difference?".

### D2. The two treasures: Jim's watch and Della's hair (P2)
- **Stated in the text.** "Two possessions of the James Dillingham Youngs in which they both took a mighty pride": Jim's
  gold watch, an heirloom, and Della's hair (P2).
- **Interpretive expectation.** This is the set-up for the whole story, and both treasures are later sacrificed. It is
  the most important early material for the ending to reach back to.
- **Minimum for a hit.** The watch and the hair are extracted as units in P2, or as one unit naming both. They are
  then linked from P3 and/or P6.

### D3. Della sells her hair to buy a chain for Jim's watch (P2 to P3)
- **Stated in the text.** She sells her hair for $20. She buys a platinum fob chain "worthy of The Watch" to replace
  the "old leather strap" (P3).
- **Interpretive expectation.** Her gift draws its value from his treasure. It only makes sense if the watch
  exists. The sacrifice is deliberate (P2: the tear, the faltering).
- **Minimum for a hit.** A cross-passage relation from the hair sale or chain (P3) back to the hair or watch (P2).

### D4. Jim's unreadable reaction (P4 to P5, explained in P6)
- **Stated in the text.** Jim stares with "an expression ... that she could not read"; it is "not anger, nor surprise,
  nor disapproval" (P4). He asks "You say your hair is gone?" "with an air almost of idiocy" (P5). He also says "you may
  see why you had me going a while at first" (P5).
- **Interpretive expectation.** P6 retroactively explains the stare. Jim was not reacting to how she looks. He was
  realising that the combs he bought by selling his watch are now useless. A reader's reading of P4 and P5 changes
  at P6.
- **Minimum for a hit.** A revision of the P4 or P5 reaction unit, or a REFRAMES or CAUSES link to it from P6
  (combs and/or watch sold). This needs recall across passages with little word overlap ("stare", "expression"
  against "combs", "sold the watch").

### D5. The combs: Jim's gift is for the hair that is gone (P6, reaching back to P2-P3)
- **Stated in the text.** The combs that "Della had worshipped long in a Broadway window", "just the shade to wear in the beautiful
  vanished hair". "The tresses that should have adorned the coveted adornments were gone." (P6)
- **Interpretive expectation.** This is the first reversal. Her sacrifice has made his gift unusable.
- **Minimum for a hit.** A cross-passage link from the combs (P6) to the hair (P2) or the hair sale (P3).

### D6. Jim sold the watch: the chain is useless (P6, reinterpreting P2-P3)
- **Stated in the text.** "I sold the watch to get the money to buy your combs." (P6)
- **Interpretive expectation.** This is the second, symmetric reversal and the story's central irony. Each sold the
  treasure the other's gift was meant to serve. It should change the **reading** of the P3 chain ("worthy of The
  Watch") and of the P2 watch. This is the clearest test of retrospective reinterpretation.
- **Minimum for a hit.** A revised reading of the P2 watch or P3 chain unit, or a REFRAMES or CONTRADICTS link from the
  P6 watch-sold unit to it. A within-P6 link alone counts as partial.

### D7. Foolish or wise: the magi (P5 foreshadowing, P6 resolution; title)
- **Stated in the text.** In P5 the narrator says: "The magi brought valuable gifts, but that was not among them. This dark assertion will
  be illuminated later on." In P6 they are "two foolish children ... who most unwisely sacrificed", and then "of all who give gifts these two were the wisest ...
  They are the magi."
- **Interpretive expectation.** The ending reverses the apparent failure, since both gifts are useless, into the
  story's claim that the sacrifice made out of love is the real gift. P6 resolves the "dark assertion" promised in P5.
- **Minimum for a hit.** A link from the P6 "wisest / they are the magi" unit back to P5's magi assertion, or to the
  sacrifices (P3 / P6). For full credit, the Journey also ends on this reframing.

### D8. Della's fear of losing Jim's regard (P4, resolved in P5). Minor
- **Stated in the text.** "Please God, make him think I am still pretty" (P4). "Don't you like me just as well, anyhow?" (P5).
  "I don't think there's anything in the way of a haircut ... that could make me like my girl any less." (P5)
- **Interpretive expectation.** Her fear is answered before the reveal. Love does not depend on the treasure.
- **Minimum for a hit.** A cross-passage link from P5 (Jim's reassurance) to P4 (the prayer or fear).

## The ending (the question this experiment asks)

The ending should cause **revisions** (changed readings) of earlier units, not just new links. At least:
- the P3 chain or P2 watch (D6), and
- the P4 or P5 reaction (D4), and/or
- the "foolish" sacrifice reread as wise (D7).

If P6 produces no revisions of earlier units, MORe has represented the ending without letting it change
the meaning of what came before.

## Scoring rules

- **Development recall:** hit / partial / miss against the minimum conditions above.
- **Precision:** every REFRAMES, CONTRADICTS and CAUSES relation, and every revision, is rated supported /
  plausible / unsupported against the text. One rater (an AI assistant), so the ratings are provisional.
- **Error attribution for each partial or miss:**
  - *Perception*: the needed unit was never extracted, or its quote was rejected.
  - *Recall*: the earlier unit exists but was not in working memory (the activated set) when the later passage was integrated.
  - *Integration*: the earlier unit was in working memory, but no relation or revision was proposed, or the one proposed was wrong.
- **Journey:** do the stages follow the arc (want, sacrifice, reveal, double reversal, magi)? Does it name
  the double irony? Does its final transition classify the ending as a reinterpretation?

## Predictions, recorded before running (to be checked, not scored)

- D2, D3, D5 and D6 share words ("watch", "hair", "chain") across passages. Lexical recall should find them.
- D4 has little word overlap between P6 and the P4 stare. A miss here would most likely be a recall failure.
- D7 shares "magi" between P5 and P6. It should be recalled.
