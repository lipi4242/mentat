# MECE

Mutually Exclusive, Collectively Exhaustive. A quality test for any decomposition.

## What it is

**Mutually Exclusive (ME):** no item fits more than one bucket. Every element belongs to exactly one category.

**Collectively Exhaustive (CE):** no item is left out. Every element fits somewhere.

MECE is not itself a decomposition method — it is a **test** you apply to a decomposition. A MECE structure has no overlap (no double-counting, no confusion about where something belongs) and no gaps (nothing falls through the cracks).

## When to apply

Any time you decompose something:
- Building an issue tree (why is X happening?)
- Options analysis (what are the alternatives?)
- Segmenting users, markets, or problems
- Structuring an argument (Pyramid Principle requires MECE groupings)
- Breaking down a project into workstreams

## How to apply

1. **Define the universe.** What is the set of things you're splitting? Be explicit. "All reasons this customer might be unhappy." "All possible pricing strategies."
2. **Choose a single splitting dimension.** A MECE split works on one dimension at a time. If you mix dimensions (by function AND by geography), you'll get overlap.
3. **Generate the buckets.**
4. **Test ME:** can any item fit two buckets? If yes, merge or re-split.
5. **Test CE:** is there any item in the universe that fits no bucket? If yes, add a bucket or expand an existing one.

Common MECE split patterns: by function, by geography, by time period, by customer segment, by causal category (People / Process / Technology / Policy).

## One worked example

**Question:** Why is this customer angry?

Split on causal category: **Product / Process / People / Pricing**

- **Product** — bug, missing feature, poor UX
- **Process** — slow delivery, bad onboarding, broken workflow
- **People** — rude support rep, wrong contact, miscommunication
- **Pricing** — felt overcharged, surprise invoice, wrong tier

**ME check:** does a "surprise invoice" fit both Process and Pricing? It could be a billing process failure. Resolve: put it in Pricing; Process covers workflow issues only. If both matter, break it out as a sub-item under the most accurate parent.

**CE check:** what if the customer is angry because a competitor offered a better deal? That's a Pricing signal — fits. No gap found.

Result: a clean 4-bucket issue tree covering every known cause with no double-counting.
