# Changelog

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