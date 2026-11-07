# Say It With Charts (Zelazny)

The chart serves the message, not the data. Choose the chart from what you're trying to say.

## What it is

Gene Zelazny's framework from *Say It With Charts*. The central insight: most people choose a chart by looking at the shape of their data. Zelazny reverses the process — write the message first, then pick the chart that best carries it.

There are **five message types**, each mapping to a narrow set of chart options:

- **Component** — how parts make up a whole (% of total)
- **Item** — how things rank against each other (magnitude comparison)
- **Time series** — how something changes over time
- **Frequency distribution** — how many items fall into each range
- **Correlation** — whether and how two variables move together

Every chart you will ever need belongs to one of these five categories. Identify the category first; the chart choice follows.

## When to apply

Every time you are choosing a chart type — for a presentation, a report, a dashboard panel, an analysis. Also when critiquing an existing chart that isn't landing.

The slide title should be the message sentence, not the axis label. "Revenue grew 15% in Q3" is a title. "Revenue by Quarter" is not.

## How to apply

1. **Write the message in one sentence.** This becomes the chart title. If you cannot write the sentence, you are not ready to choose a chart.
2. **Identify which of the five message types it is.** The sentence will tell you: "X is larger than Y" = item; "X grew over time" = time series; "X is Y% of the total" = component; "most values cluster between A and B" = frequency; "as X rises, Y rises" = correlation.
3. **Pick the matching chart** from the cheat-sheet below.
4. **Check:** does the chart make the message obvious in under 3 seconds? If not, simplify or re-type.

## Cheat-sheet

| Message type | Recommended chart(s) |
|---|---|
| Component (% of total) | Pie chart; 100% stacked bar |
| Item (ranking/magnitude) | Horizontal bar (ranked, largest first) |
| Time series | Column chart (few periods); line chart (many periods) |
| Frequency distribution | Histogram; step chart |
| Correlation | Scatter plot |

Rules:
- **Never use pie** for more than 5 segments or for time comparisons.
- **Never use line** for fewer than 4–5 data points (use column instead).
- **Never use 3D** anything — it distorts perception.
- If two message types apply, use two charts.

## One worked example

**Data available:** Q2 revenue = €1.2M, Q3 revenue = €1.38M.

**Step 1 — write the message:** "Q3 revenue grew 15% over Q2."

**Step 2 — identify the message type:** change over time → **time series**.

**Step 3 — pick the chart:** two periods, discrete comparison → **column chart** with two bars (Q2, Q3), labeled with values.

**Step 4 — check:** a reader sees two bars, Q3 clearly taller, title says "grew 15%." Message lands in under 3 seconds. Done.

What *not* to do: pie chart (no "part of whole" message), line chart (only 2 points — misleading slope), table (hides the magnitude visually).
