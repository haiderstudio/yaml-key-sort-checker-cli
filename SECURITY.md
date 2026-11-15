# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the YAML files you point it at, and it never rewrites a file and never changes anything. It writes nothing except the report on standard output (and usage errors on standard error). It never fetches a URL: remote addresses are skipped, not opened.

It parses the files you give it with a small hand-rolled line reader — it does not run anything in the files, so a key in a checked file is reported, never executed.

If you find a case where the tool edits a file, or reports a pass for a file holding a mapping key out of order, please open an issue describing the exact commands and input.
