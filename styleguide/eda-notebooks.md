# Exploratory data analysis notebooks

How an exploratory notebook on subsurface data is ordered, what it may claim and how it is worded. It is the third format beside the story and the deck, chosen by purpose in the same
way: a story is one argument read once, a deck teaches a body of knowledge in parts, and an exploratory notebook shows what one kind of data holds and how far it can be trusted. SubScout
holds the guide and does not build the notebook. The guide is about structure, statistics and language; colour and type follow the register of the project that applies it. Draft, 2026-11-14. Thresholds marked **[convention]** are common practice, not findings: they bind only when a project adopts them.

An exploratory notebook answers one question about one kind of data, shows the reader how far the data can be trusted before any statistic, and ends on what the data cannot say. It does
not argue a case: for that, write a story (see [story-format.md](story-format.md)).

## 1. What binds

| Tier | Rule |
|---|---|
| **[Law]** | Every figure and quoted number carries one of Observed, Derived or Interpreted (see [language.md](language.md)); an Interpreted value never appears without its range or assumption. |
| **[Law]** | A method that fails its validity gate is not drawn and not reported as a finding. It is listed, with the reason, in the validity ledger (section 7). |
| **[Law]** | No measured value is dropped silently. A value set aside (outside a physical range, flagged by the source, undefined under a transform) is counted and its count is shown. |
| **[Default]** | The order of sections in section 2. A step that does not apply is listed with its reason, not left out. |
| **[Law]** | The thresholds of sections 3 to 5 are the same for every topic. A topic does not get a threshold of its own; a topic that cannot reach a state at the stated count is shown at the state it reaches. |
| **[Law]** | The ladder of every notebook is written by hand, from the question of that notebook. A ladder generated from a specification is accepted only for a batch of existing notebooks that is being brought into the format, and never for a new notebook. |

## 2. The ladder

| Step | Content |
|---|---|
| Question and set-up | One question, a diagram of how the quantity is measured, and a summary whose numbers are computed when the notebook runs |
| Data map | Which inputs support which outputs, before any statistic (section 5) |
| Basis of analysis | Source and date, measurement type, unit, depth reference, count of rows and of wellbores or fields, the rule for missing values, confidence level. The same block in every notebook |
| Univariate | One variable at a time: count and missing share; location, spread and shape; censoring and detection limits; physical bounds; outliers flagged and kept; then by wellbore, formation or fluid class, then against depth or time |
| Bivariate | Pairs chosen from a published relation or the physics, never from all combinations; the published relation drawn with its grade; rank and linear coefficients side by side; the same pair after conditioning on depth, wellbore or class; residuals against the relation |
| Multivariate | A pair matrix of the retained variables and coplots, then PCA, clustering or grouping only if the gate of section 4 passes |
| What the data cannot say | Gaps from the data map, untested assumptions, the literature or data that would close each |
| Validity ledger | One row per method considered: tried or not, gate result, outcome (section 7) |
| Knowledge used | The entries relied on, their grades and what the page must add for each grade |

A notebook that is mainly a register of counts and sizes (fields, licences, wellbores per window) keeps the order but is short on the multivariate step. A notebook that documents a data model is
not an exploratory notebook and carries only the data map and a glossary.

## 3. Transforms

A transform is shown only when it earns its place against a stated criterion, computed and printed, with the raw and the transformed view side by side. Where no transform helps, one line in
the ledger says so and the raw scale stays.

| For | Transforms | The criterion |
|---|---|---|
| Skewed positive values (permeability, rates, volumes, concentrations) | logarithm, square root, reciprocal, Box-Cox | skewness falls by at least half; a Box-Cox exponent whose interval holds zero is reported as a logarithm |
| Values with zeros or both signs (residuals, revisions, differences) | inverse hyperbolic sine, log of one plus the value, Yeo-Johnson | the transform exists everywhere; the lower tail is no longer a spike |
| Counts | square root, Anscombe | variance no longer rises with the mean |
| Bounded fractions (saturation, porosity, shares, water cut) | logit, arcsine of the square root | the range fills; spread near the bounds is stabilised |
| Closed compositions (gas components, mineralogy) | centred or isometric log-ratio | the parts sum to a constant: PCA or distance on raw parts is not allowed |
| A known first-order effect | detrending against depth or position; normalising by a reference (effective stress, plateau rate, recoverable volume); a change of frame (height above a contact, time since start-up, flattening on a marker) | curves from different wellbores align; the frame is on the axis |
| Different calibrations | robust standardisation within a wellbore (median and median absolute deviation) | between-wellbore offset is nuisance, and is reported |
| A relation that bends | transform of one or both axes (log-log, semi-log, Horner time, Leverett J) | the gap between rank and linear correlation closes; slope and intercept have intervals |
| Series | differencing, resampling to a regular step, spectral density in decibels, change-point detection, semi-variogram after a normal score | stationarity improves, or a period, step or range is found that the raw series hides |

A normal-score transform makes skewness zero by construction, so skewness cannot choose it. It is applied on purpose, before a variogram or a Gaussian method, and the back-transform is kept.

## 4. Gates for the multivariate step

A method is drawn only if its gate passes. Each result goes into the ledger either way. **[convention]**

| Method | Gate |
|---|---|
| **PCA** | at least 100 complete rows and 10 per variable, counted on the effective sample size for depth or time series; at most 30 % of rows lost to missing values and no imputation to reach the count; not a closed composition (log-ratio first); Kaiser-Meyer-Olkin at least 0.6 and Bartlett's test rejects an identity matrix; the first two components explain at least 60 % or the scree has a clear elbow; the first loading vector is stable (cosine at least 0.9) when wellbores are resampled as wholes, with at least five wellbores |
| **Clustering** | more than one cluster by the gap statistic; silhouette at least 0.25; every cluster stable under resampling (Jaccard at least 0.75, by wellbore when wellbores are given); at least 10 members per cluster; at least one variable not used to form the clusters differs between them. A cluster that cannot be named from the domain is reported as a statistical grouping |
| **Binning, grouping** | at least 10 members per bin; edges from a physical or published boundary before quantiles; for bins used as groups in an analysis, the bins explain at least 0.02 more variance than the continuous variable does through its rank correlation |
| **Correlation matrix** | rank correlation by default; a pair with fewer than 10 overlapping values is blank; the matrix points to pairs worth a panel and is not a finding |
| **Trend or regression** | residuals against fitted values and depth; a trend is a fit over a stated range and is not extrapolated |

Rows within a wellbore, a depth step or a field are not independent, so the effective sample is smaller than the row count. Where a result rests on fewer than ten wellbores the page says
so on every statistic: "exploratory, n = 6 wellbores".

## 5. The data map

The data map answers which input supports which output, and how well.

- **Rows** are inputs, one per measurement type, with its unit, its basis (measured, derived, modelled, assumed) and the count of wellbores or fields that hold it.
- **Columns** are the outputs the notebook gives.
- **A cell** holds the input's state where the output needs it, drawn larger for a core need and smaller for a supporting one. An output takes the state of its weakest core input; a supporting input
  is listed and never lowers it.

| State | Rule | Symbol |
|---|---|---|
| Good | at least 30 entities, measured or derived basis | filled circle, count |
| Partial | 10 to 29 entities, or 30 or more on a modelled or assumed basis | half-filled circle, count |
| Little | 1 to 9 entities | open circle, count |
| Not held | the data exist elsewhere and are not in the store | cross, "not held" |

Colour never carries the state alone: every state has a symbol and a count, and a table view of the same cells is available. Use a status ramp that is clear of the project's reserved colours
(hydrocarbon types in particular), and check it for colour-vision differences by simulation. An amber on white is below 3:1, so the symbol and the count are not optional.

A project whose data are one field says so in the data map: with a few dozen wellbores nothing can be good by these counts, and the map shows that plainly.

## 6. Knowledge, data and diagrams

- A published relation is drawn with its grade and tested on the data in hand: untested, confirmed, or not supported. A contested relation is drawn alongside its rivals and the disagreement is
  stated as a finding. Constants are read from the knowledge store and never typed into a notebook.
- A notebook whose table was written by a pipeline also tests that table: the expected columns, types, key, ranges and null share are checked, and the notebook states how many checks failed.
- The diagram of how a quantity is measured is linked from the page that carries it, not copied.

## 7. The validity ledger

| Method | Outcome | Reason |
|---|---|---|
| Transform of permeability | reported | log10 takes the skewness from 5.4 to 0.1 |
| PCA of drilling channels | not valid | Kaiser-Meyer-Olkin 0.48 (needs 0.6) |
| Clustering of plugs | not applicable | two wellbores |

An outcome is `reported`, `not valid` or `not applicable`. The ledger is a table at the end of the notebook, in the order the methods were considered.

## 8. Language

Impersonal, British English, sentence-case headings, metric first (see [language.md](language.md)). The statistics are written in the academic register and the data in the subsurface one:

- "The distribution of permeability is right-skewed (skewness 3.1); the geometric mean is the better central value."
- "Porosity and log permeability are rank-correlated (Spearman ρ = 0.78, n = 412 plugs in 9 wellbores); within a facies the relation is weaker (ρ = 0.41)."
- "Conditional on depth, the residual from the published relation is …"
- "The relation is published and untested elsewhere; on these data it holds between … and …, and departs below …"
- "Principal component analysis was not applied: Kaiser-Meyer-Olkin 0.48, below 0.6."

A coefficient is described as association unless a mechanism is shown. A cluster is a grouping, a component is a direction of variance, and neither is a geological unit until the domain
names it.
