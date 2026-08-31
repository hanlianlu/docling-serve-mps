# Changelog

## 0.5.0

- Raise the docling-slim floor to 2.124.0 and refresh the locked Apple Silicon
  runtime, including docling-ibm-models 4.0.0 and docling-parse 7.16.0. Keep the
  already-current docling-serve 1.31.0, docling-jobkit 3.4.0, docling-core
  2.92.0, and OCRMac 1.0.1 releases aligned. Retain mlx-vlm 0.6.4 as the newest
  release compatible with Docling's macOS Transformers constraint; newer
  mlx-vlm releases require Transformers 5.14 or later while Docling 2.124.0
  requires a version below 5.9.
- Preserve the MPS code/formula preset workaround. Granite Docling's cached MLX
  model already matches the latest upstream revision, while Docling 2.124.0
  still hardcodes the code/formula generation limit, so this dependency refresh
  does not claim to fix runaway formula generation.

## 0.4.0

- Raise the unbounded dependency floors to docling-serve 1.31.0 and
  docling-slim 2.121.0. This includes docling-jobkit 3.4.0, improved multipart
  validation errors, Apple Pages input, corrected rotated-PDF coordinates,
  and MLX bfloat16 log-probability handling.
- Keep the MPS code/formula preset workaround: upstream still defaults to the
  nonexistent `default` preset, and `codeformulav2` still has no MLX engine.

## 0.3.0

- Raise the dependency floors to docling-serve 1.30.0 and docling-slim 2.118.1,
  which pull in docling-jobkit 3.3.x. Only that jobkit maps the service API's
  `do_pdf_heading_hierarchy` onto the pipeline, so before this release the field
  was accepted and silently dropped, leaving every PDF heading at level 1.
  jobkit also turns on `generate_parsed_pages` itself when the request asks for
  font-style inference, so no wrapper setting is needed to make it work.

## 0.2.1

- Escalate `stop` to `SIGKILL` when the service ignores `SIGTERM`, so a wedged
  server can no longer strand its PID file and block the next `start`.

## 0.2.0

- Resolve the code/formula preset to `granite_docling`, the only shipped preset
  with an MLX engine. Docling Serve's stock `default_code_formula_preset` names
  a preset that does not exist, so any client sending a preset fails outright.
- Allow-list `granite_docling` so clients may request it by name as well as
  through the `default` alias.
- Raise the dependency floors to docling-serve 1.29.0 and docling-slim 2.118.0
  and refresh the lockfile.

## 0.1.0

- Package native Docling Serve as an installable Apple Silicon application.
- Add background `start` and `stop` lifecycle commands with health waiting,
  atomic state, and PID reuse protection.
- Default PyTorch-backed stages to MPS with CPU fallback.
- Override Docling's `auto` OCR preset with accurate Apple Vision OCR for
  Simplified Chinese and English.
- Enable the loopback-only Docling UI while disabling remote services and
  external plugins.