# Changelog

## 0.1.0

- Package native Docling Serve as an installable Apple Silicon application.
- Add background `start` and `stop` lifecycle commands with health waiting,
  atomic state, and PID reuse protection.
- Default PyTorch-backed stages to MPS with CPU fallback.
- Override Docling's `auto` OCR preset with accurate Apple Vision OCR for
  Simplified Chinese and English.
- Enable the loopback-only Docling UI while disabling remote services and
  external plugins.