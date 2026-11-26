1. **P1 — License filtering is bypassed for alternatives.** [scripts/build_r2.py:110](/home/pranavsh/projects/specsheet/scripts/build_r2.py:110) copies `b.x[*].alt` from the ungated index, although headline values come from gated records. [verdict.ts:66](/home/pranavsh/projects/specsheet/api-worker/src/verdict.ts:66) then compares those values: changing a threshold changes `disagree` versus exclusion, allowing restricted values to be inferred through results/counts.
   **Fix:** derive alternatives exclusively from policy-gated records.
   **Exit:** a restricted-only alternative neither appears in the free pack nor changes free query membership, counts, or statuses; an authorized alternative still produces disagreement.

2. **P1 — Image inheritance overrides conflicting configuration evidence.** [scripts/imgattach.py:102](/home/pranavsh/projects/specsheet/scripts/imgattach.py:102) returns `identity_variant="exact"` for a single-SKU page without checking `idn.variants`, `region`, or `shared`. Those checks exist only in the later OCR branch. A controlled reproduction with page SKU `A2667111` and detected variant `A2667113` returns exact binding, so another configuration’s electrical facts can attach automatically.
   **Fix:** apply conflicting-identity vetoes before either binding branch.
   **Exit:** foreign variant/region/shared-ID fixtures cannot produce exact claims, including images with empty `file_models`.

3. **P1 — UPS parsing converts bounds/ranges into exact facts and accepts sibling-model prose.** [crawler/adapters/_powerstation.py:450](/home/pranavsh/projects/specsheet/crawler/adapters/_powerstation.py:450) reproduces `“up to 20 ms” → 20` and `“10–20 ms” → 20`. At [line 454](/home/pranavsh/projects/specsheet/crawler/adapters/_powerstation.py:454), substring matching also accepts `Explorer 1000 Plus` prose for `Explorer 1000`.
   **Fix:** preserve explicit upper bounds, reject or represent ranges, and require exact model identity.
   **Exit:** both labelled-row and prose fixtures retain `up_to`; ranges never become exact endpoints; sibling/suffixed model copy emits nothing.

Additional findings:
- **Verdict parity:** [verdict.ts:27](/home/pranavsh/projects/specsheet/api-worker/src/verdict.ts:27) converts `null` range endpoints to zero, whereas Python rejects them; [line 54](/home/pranavsh/projects/specsheet/api-worker/src/verdict.ts:54) treats object key order as significant, unlike Python’s sorted serialization. Add both parity fixtures.
- **Per-capacity naming remains ambiguous:** [scripts/import.py:365](/home/pranavsh/projects/specsheet/scripts/import.py:365) selects the first capacity-matching alias without model/SKU binding; equal-capacity configurations can inherit another model’s name. At [line 405](/home/pranavsh/projects/specsheet/scripts/import.py:405), fallback to the parent name can still retain a wrong capacity. Require identity-bound aliases or a capacity-neutral fallback.

Read-only review; targeted Python reproductions executed.
