# Changelog

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