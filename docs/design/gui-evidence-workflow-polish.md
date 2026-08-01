# GUI Evidence Workflow Polish

## Document control

| Field | Value |
|---|---|
| Repository | `Runndownn/Wilson-Eval3ngine-` |
| Base head | `cf2b35714ce7c422a48758ec817f8a8a2b8a8d11` |
| Branch | `feat/gui-evidence-workflow-polish` |
| Date | 2026-07-31 |
| Visual direction | Preserve and evolve the established Wilson dark, blue/cyan, evidence-oriented interface |

## Operator problems addressed

The connected GUI exposed several related usability and state-management problems:

1. Endpoint tests could report one or more discovered NVIDIA models while the registered Models inventory still showed four models. Health feedback was transient and did not explain the relationship between provider discovery and registry reconciliation.
2. The five-page workflow appeared as compact tabs rather than a prominent operating sequence.
3. Panels, cards, and functional zones needed clearer visual boundaries.
4. The Generate Reports model selector flattened every model into one list, making large NVIDIA or gateway inventories difficult to navigate.
5. Chart generation used global controls detached from the run they affected. Missing and deleted chart states were not sufficiently visible.
6. Blocking browser confirmation dialogs and full-list refreshes caused disruptive focus or viewport changes.
7. Report cards exposed file metadata but did not immediately explain what each report represented or provide an intentional in-card viewing action.
8. Synthetic chart examples lacked an explicit, clearly labelled generation path.

## Product decisions

### Five-stage operating workflow

The five workflow stages remain Endpoints, Models, Generate, Charts, and Reports. Each stage is now a bordered navigation card with a number, title, and purpose. Every page repeats its position as `Workflow N of 5`, making the current operating context visible without relying only on color.

### Endpoint health and registry reconciliation

Endpoint health and model registration remain distinct concepts, but the interface now makes the transition explicit. `Test & reconcile models` first invokes the endpoint-specific health test and then invokes the authoritative model discovery endpoint. The endpoint card shows its registered model count and last test time, while the completion toast reports both models found by the provider and models newly added to the registry.

This does not claim that every provider-reported model was registered when collisions or validation rules prevent it. The registered Models inventory remains the source of truth for evaluation selection.

### Model family navigation

The generation selector now has two coordinated surfaces:

- **Popular six:** six high-signal registered models selected deterministically from the filtered inventory using model-name characteristics and availability. This is navigation guidance, not a performance ranking.
- **All families:** expandable family cards inferred from model identifiers, such as Llama, Mistral, Qwen, Gemma, OpenAI, Claude, Nemotron, Embeddings, Vision, and Safety.

A model may appear in both surfaces, but both controls operate on the same selected-model set. Search and provider filters apply to both. Open families and selected models remain stable during ordinary rendering.

### Chart lifecycle

Chart inventory and chart mutation are deliberately separated:

- Refresh is read-only and never creates content.
- Every telemetry evidence run remains visible even when it currently has no chart files.
- Individual chart deletion and whole-run chart deletion persist through telemetry deletion markers.
- Refresh respects those markers and never resurrects deleted artifacts.
- Every run has an explicit Generate charts action. That action is the only operation allowed to clear deletion markers and restore the selected run.
- Partial chart sets trigger generation rather than being treated as complete.
- A complete undeleted chart set is reused without unnecessary rendering.
- Demonstration charts use a separate `POST /api/charts/demo` endpoint and are labelled synthetic.

### Stable interactions

Job WebSocket events update the job card in place and no longer force navigation to the Generate page. Destructive UI actions no longer open blocking `confirm()` dialogs. Buttons show local busy state, the backend performs the authoritative mutation, and the affected inventory is reconciled afterward. A scroll-preserving render helper protects the viewport when purely presentational state changes, such as minimizing a chart run.

### Chart rendering and evidence inspection

Chart cards expose descriptions, categories, per-run context, available/missing counts, and a visible image-failure state. The expanded chart window keeps image evidence and metadata together and adds a direct `Data & metadata` control. Chart images remain same-origin and are not replaced with fabricated client-side values.

### Report understanding

Each PDF card now includes a plain-language summary derived only from repository-provided run and model metadata. The PDF is loaded into the card only when the operator clicks `View report in card`, reducing initial page load while retaining a full-tab reader and evidence-bundle export.

## Accessibility and responsive behavior

- Workflow cards are native buttons and expose `aria-current` for the active stage.
- Family headers are native buttons with `aria-expanded`.
- Chart image failures have visible text rather than an empty frame.
- Status messages remain in a polite live region.
- Focus styling remains inherited from the established design system.
- Workflow navigation scrolls horizontally at intermediate widths.
- Five-step strips, endpoint cards, chart summaries, report metadata, and family layouts collapse for narrow screens.

## Security and integrity considerations

- Dynamic values continue to be HTML-escaped before markup insertion.
- Provider health reconciliation uses existing validated REST endpoints and does not expose provider credentials.
- Chart generation still requires real evaluation evidence, except for the separately named demo endpoint.
- Synthetic demo charts cannot be mistaken for a normal evidence run in the interface.
- Refresh does not mutate state.
- Explicit regeneration is auditable because it changes only the selected run's deletion markers and chart artifacts.
- Report and chart resources remain same-origin.

## Compatibility effects

- Operators who previously expected deleted charts never to be recoverable can now restore them, but only by pressing the affected run's Generate action.
- The global chart-run dropdown remains hidden in the DOM for compatibility, but it is no longer the primary interaction.
- Large model inventories may show the same popular model in its family card; selection state is shared and unambiguous.
- The in-card PDF viewer is lazy-loaded and may still depend on the browser's built-in PDF capability; the full-report link remains the fallback.

## Validation plan

Repository tests cover:

- unique chart and demo routes;
- read-only chart inventory;
- reuse of a complete chart set;
- restoration of a fully deleted chart run;
- regeneration of a partial chart set;
- explicit, labelled demo generation;
- refusal to generate real charts without evaluation evidence;
- five-stage workflow markup;
- popular and family selector contracts;
- endpoint-test/model-discovery sequencing;
- per-run chart actions;
- absence of blocking confirmation dialogs;
- absence of forced tab navigation during WebSocket events;
- report summary and lazy in-card viewer contracts;
- required boundary-layer selectors.

Executable browser validation should exercise NVIDIA discovery reconciliation, family expansion, repeated selection from both surfaces, long-running job updates while another tab is active, individual and whole-run chart deletion, refresh persistence, explicit restoration, demo generation, image error states, PDF lazy loading, keyboard order, reduced motion, and narrow-screen layouts.
