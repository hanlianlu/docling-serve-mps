# OCRMac Integration Design

## Goal

Use Apple Vision OCR for future Docling conversions on this macOS service while
leaving DLightRAG and LightRAG unchanged. Preserve LightRAG's current request
contract, including `ocr_preset=auto` and `force_ocr=true`.

## Scope

Only the `docling-serve-mps` repository changes. Existing processed documents,
database records, vectors, knowledge graphs, and parser caches are not migrated
or reprocessed. The new OCR behavior applies when a document next reaches this
Docling service.

## Configuration

Install OCRMac through Docling's supported `feat-ocr-mac` extra. Configure
Docling Serve's official `custom_ocr_presets` setting to replace the built-in
`auto` preset with:

```json
{
  "auto": {
    "kind": "ocrmac",
    "framework": "vision",
    "recognition": "accurate",
    "lang": ["zh-Hans", "en-US"]
  }
}
```

Docling Serve registers custom presets after built-in presets, so this entry
replaces the built-in `auto` mapping. LightRAG continues sending
`ocr_preset=auto`; Docling Serve resolves it to OCRMac. The request's
`force_ocr=true` remains authoritative and is passed to the resulting OCRMac
options as full-page OCR.

## Why Vision Accurate

Use OCRMac's public Apple Vision path rather than its Live Text path. Vision
accurate provides Docling with real confidence values and stable bounding boxes.
The Live Text wrapper uses internal macOS classes, emits placeholder confidence,
defaults to token-level output, and has an unresolved repeated-call memory issue.

## Files

- `pyproject.toml`: add Docling's OCRMac feature extra while retaining the UI.
- `uv.lock`: lock OCRMac and its macOS framework dependencies.
- `service.env`: define the custom `auto` OCR preset.
- `README.md`: document effective OCR behavior, language order, and scope.

No proxy, request rewriting, monkey patch, fallback engine, or RAG-side setting
is introduced.

## Validation

1. Verify the environment setting parses and the manager registry resolves
   `auto` to `OcrMacOptions` with Vision, accurate recognition, and
   `zh-Hans,en-US`.
2. Verify a LightRAG-equivalent request keeps full-page OCR enabled after preset
   resolution.
3. Restart the background service and confirm `/health` and `/ui/` respond.
4. Convert a small generated bilingual PDF through the same async Docling HTTP
   endpoints used by LightRAG.
5. Confirm logs and resolved options identify OCRMac, and exported JSON/Markdown
   contain both Chinese and English text.
6. Verify the service remains loopback-only, remote services and external
   plugins remain disabled, and the repository contains no credentials or AI
   attribution.

## Rollback

Remove the custom OCR preset and OCRMac feature extra, sync the existing lock,
and restart the service. LightRAG will again resolve `auto` using Docling's
installed-engine order. No DLightRAG or LightRAG rollback is required.