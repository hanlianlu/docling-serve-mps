# Changelog

## 0.7.1

- Serve Docling's implicit code/formula default with an engine MPS can run.
  Docling Serve consults its preset registry only when a request names a preset,
  so a request that enables code or formula enrichment without one — the shape
  the bundled UI sends, and any hand-written API call in the same shape — ran
  Docling's own `codeformulav2` default, whose only engine refuses MPS outright
  and failed the whole conversion. Both lifecycle modes now exec a launcher that
  replaces that one stage spec with the `granite_docling` preset Docling already
  ships for Apple Silicon; naming a preset still wins, and `codeformulav2` is
  still refused by name.
- Keep `stop` and `start` able to recognize a service started by an earlier
  release. The launcher changes the command line the PID record fingerprints, so
  the previous fingerprint stays accepted instead of leaving an upgraded machine
  with a service it refuses to stop or, worse, a second server beside it.
- Fail at startup rather than per request when Docling renames either stage spec
  or drops the MLX engine, and warn when `UVICORN_WORKERS` is greater than one,
  where uvicorn worker processes import Docling themselves and the substituted
  default does not reach them.

## 0.7.0

- Raise the dependency floors to docling-serve 1.34.0 and docling-slim 2.128.0,
  and refresh the locked Apple Silicon runtime: docling-core 2.97.0,
  docling-parse 7.20.0, docling-ibm-models 4.0.2, docling-jobkit 3.7.0, PyTorch
  2.14.0, and torchvision 0.29.0.
- Move to Transformers 5.17.0 and MLX 0.32.2, which releases the previous
  `mlx-vlm` 0.6.4 ceiling: the MLX runtime that serves the code/formula preset
  is now 0.7.1.
- Document the behavior this refresh re-verified, because both mechanisms are
  the reason this package exists and neither is upstream's default:
  - Docling 2.128.0 still hardcodes the `codeformulav2` preset as the implicit
    default for code/formula enrichment. That preset still has no MLX engine,
    so the packaged `default` alias and the allow-list remain necessary for any
    request that names a preset; upstream's own engine selection rejects MPS for
    it (`MPS is not supported by this model`), which is why the omit-the-preset
    path stays unsupported.
  - The override resolves `default` to `granite_docling`, and docling's
    auto-inline engine still selects MLX for it on Apple Silicon, loading
    `ibm-granite/granite-docling-258M-mlx` rather than the Transformers path.
  - The OCRMac `auto` preset override and the docling-core decoded-image
    ceiling (`DOCLINGCORE_MAX_IMAGE_DECODED_SIZE`, 64 MiB) both still apply;
    docling-core 2.97.0 continues to read that setting and to enforce it when it
    materializes a referenced image.

## 0.6.0

- Add `docling-serve-mps run`: exec Docling Serve in the foreground with the
  packaged defaults, for process supervisors (launchd, systemd) that own the
  service lifecycle. It neither takes the lifecycle lock nor writes a pid
  record, so a supervisor unit can name one command instead of duplicating
  every default in its own environment.

## 0.5.1

- Raise the decoded-image ceiling to 64 MiB through
  `DOCLINGCORE_MAX_IMAGE_DECODED_SIZE`. docling-core refuses to materialize a
  referenced image above 20 MiB, so a client exporting with
  `image_export_mode=referenced` (LightRAG always does) aborts the whole
  conversion at export time when a single large photograph exceeds it.

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