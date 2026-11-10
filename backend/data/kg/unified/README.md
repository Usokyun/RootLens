# Public-source executable knowledge seeds

`bottle-working-graph.v2.json` is a reusable v2 working package, not a case-specific
answer. Import it with `POST /api/kg/working-graphs/import`, then select the returned
working graph for a bottle image or typed Evidence v2 query. The five candidates
are plausible upstream families; the images do not establish factory causes.

Origin: Bucher Emhart Glass, *Glass container defects: Causes and remedies*,
[2024 public guide](https://www.emhartglass.com/sites/default/files/publications/2024-07/BEG_BR0060RevA-Defect_Guide-WEB.pdf),
PDF pages **13 and 20** (printed pages 18–19 and 32–33). Source assertions preserve
the parsed unit IDs and page locators. The actual LLM proposed the domain blueprint;
the compiler generated the IDs, gates, shared rules, source links and graph view.
No test image, measured value or native dataset label was supplied to construction.

One explicit, model-scoped compatibility binding additionally maps the legacy
`BrokenRimDefect` appearance symbol to the broader `broken_glass` cue. This is
declared vocabulary migration, not new visual recognition or a source-derived
manufacturing assertion. Applied binding IDs and original values remain in traces.

The seed declares no source-derived quantitative break-size threshold. Force,
temperature, timing and equipment-state observations remain unavailable; the
compiler report lists this limitation. Image geometry is still extracted and
stored, but is not silently promoted to a source-supported cause discriminator.

The raw public PDF, parsed text, model responses, failed builds and actual runs
are local experiment artifacts under `backend/runs/unified_reasoning/`, not bundled
training data. See the execution record and the final reproducibility guide.

## Process-window seed

`tep-working-graph.v2.json` uses exactly the same IR, core and global weights.
Its original sources are the variable/disturbance documentation in `teprob.f`
and actual controller code in `temain_mod.f` from the
[public Braatz process archive](https://github.com/camaramm/tennessee-eastman-profBraatz).
These describe process/control relationships, not a verified configuration of
every downloaded data sequence. Thresholds absent from sources are declared
heuristics. Controller comments are not treated as fault ground truth.

The first source-generated graph missed cooling manifestations by requiring
alternative changes simultaneously. The revised build permits alternatives;
all three pre-fault windows returned no match, and the known fault families
appeared among candidates for the tested post-fault windows. **Top-ranked families
were not the known injected faults**. This seed demonstrates executable, traceable
comparison, not fault-identification accuracy. The negative runs are retained.
