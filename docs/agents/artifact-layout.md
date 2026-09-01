# Artifact Layout

Structured `StateDict` data is the source of truth. Markdown is a rendered audit/read surface. Runtime files live under:

```text
artifacts/sessions/{session_id}/
  manifest.json
  workflow.log.jsonl
  llm_calls.log.jsonl      # per-call LLM telemetry (tokens, status, duration)
  llm_payloads.log.jsonl   # per-call request/response bodies; LLM_LOG_PAYLOAD=false disables
  onboarding/{questionnaire,submission}.md
  profile/learner_profile.md
  path/{dual_axis_snapshot,learning_path,path_decision}.md
  round-01/{retrieval_context,expert drafts,cross reviews,revisions,course_package,judge_report}.md
  audio/
    slide_001.mp3          # per-slide narration audio
    ...
    audio_manifest.json
  presentation/
    course_deck.pptx
    pptx_manifest.json
    previews/
      slide_001.png        # per-slide PNG preview for frontend thumbnails
      slide_002.png
      ...
  feedback/{feedback_report,learner_profile_update,grading_report}.md
```

`path/learning_path.md` renders the planned route as a table and lists the per-node fine-grained `knowledge_points` extracted from the static DAG.

## Ownership rules

- The graph side-effect wrapper (`_with_runtime_side_effects` in `backend/app/graph/workflow.py`) owns Markdown artifact I/O. Agent nodes must not write files directly.
- `generate_pptx` is a graph-layer wrapper that calls `backend/app/presentation/service.py`. It is not an Agent node.
- Audio synthesis happens after `slide_deck` succeeds; the graph wrapper writes `audio/` files.
- Artifact paths are session-scoped and path traversal must remain rejected.

## PPTX pipeline

1. `slide_deck` produces structured `course_slides` (one item per slide, with narration).
2. If `PATENT_TUTOR_PPTX_ENABLED` is on, `generate_pptx` calls `backend/app/presentation/service.py`.
3. The service uses the configured `generate_pptx` LLM only for strict `PresentationDesign` JSON.
4. The backend deterministically renders the visual direction, theme/template selection, decorative layer, semantic patent-course components and speaker notes.
5. Outputs:
   - `presentation/course_deck.pptx`
   - `presentation/previews/slide_*.png` (three-digit, zero-padded)
   - `presentation/pptx_manifest.json` with fields `artifact`, `source_slide_count`, `design_theme`, `preview_images`

The LLM does not return binary PPTX, XML, SVG or arbitrary external resources.

## Degradation

- PPTX generation is enabled by default and can be disabled by setting `PATENT_TUTOR_PPTX_ENABLED=false` (also accepts `0`, `off`, `no` case-insensitively).
- `slide_deck` is enabled by default and can be disabled by setting `PATENT_TUTOR_SLIDE_DECK_ENABLED=false` (also accepts legacy `SLIDE_DECK_ENABLED`).
- On PPTX failure the node returns `status="degraded"`; the course, Markdown artifacts and audio continue.
- There is no final Markdown file; `course_package.md` is the integrated course process artifact.
