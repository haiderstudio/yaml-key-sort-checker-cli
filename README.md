# yaml-key-sort-checker-cli

Check YAML mapping keys are sorted alphabetically, fail CI when one is out of order — it never edits a file.

[![CI](https://github.com/haiderstudio/yaml-key-sort-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/yaml-key-sort-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`yaml_key_sort_checker` reads the YAML files
you point it at, checks the keys of every
mapping are in alphabetical order, and reports
each key that is out of order with the file and
the line number. It exits 1 when any key is out
of order, so it can fail a CI run. A file with
sorted keys exits 0.

- Sorted keys give cleaner diffs and make a
  duplicate or misplaced key obvious at a
  glance — the same reason requirements files
  are sorted. Every project with a long YAML
  config benefits, and nobody sorts by hand
  reliably.
- Order is plain alphabetical order on the key
  text, ignoring case — "Apple" sorts before
  "banana", and "10" sorts before "2", because
  the check compares characters, not numbers.
- Keys are compared inside their own mapping
  only: a nested mapping starts its own order,
  and each item of a sequence starts its own
  order, so a key is never compared against a
  key from another mapping.
- Comments and blank lines are ignored, and a
  key inside a block scalar, a flow collection,
  or a multi-line string is content, not a key,
  and is never checked.
- The checker is hand-rolled and uses the
  Python standard library only: the standard
  library has no YAML parser, so this tool
  reads lines and tracks indentation level by
  level, the same technique as the
  yaml-indent checker. That is enough to know
  which keys share a mapping and which order
  they are in, without ever parsing a value.
- A file given directly on the command line is
  always checked, whatever its name. A folder
  is walked for files ending in `.yaml` or
  `.yml` only, recursively by default
  (`--no-recursive` stops at the top level).
  `.git` folders are never walked, and
  directory links are never followed.
- `--json` prints the result as JSON, and
  `--stdin` checks one YAML document read from
  standard input.
- A line that uses a tab for indentation is
  reported as a problem — YAML forbids tabs,
  and a tabbed line cannot be ordered reliably.

## Who it is for

Anyone with a YAML config that has grown past
a dozen keys — CI pipelines, app settings,
compose files, action workflows. One gate in
CI, run over the files in the pull request, and
the key added at the bottom of a long mapping
gets put where it belongs instead.

## What it does NOT do

- It does not sort the keys for you. That is a
  human decision — sorting is a change to the
  file, and this tool only reports. Reordering
  the keys it names is a one-line move per key.
- It does not check whether a file is valid
  YAML in any other way. A file can pass this
  check and still fail a real YAML parser for
  another reason.
- It does not check duplicate keys. That is
  repo #57, yaml-duplicate-key-checker-cli —
  duplicates are a different check on the same
  files.
- It does not check indentation. That is repo
  #71, yaml-indent-checker-cli — indentation
  is a different check on the same files.
- It does not check boolean spellings. That is
  repo #79, yaml-bool-checker-cli — spellings
  are a different check on the same files.
- It never rewrites a file, and it never
  touches the network.

## How this differs

- A fresh search of GitHub on Nov 14, 2026
  found 0 results for
  `"yaml-key-sort-checker-cli"` and 0 results
  for `yaml key sort checker` — a completely
  empty field. No rival checks YAML key order
  in local files.
- So the narrow slice stands: key order only,
  per mapping level, case-insensitive, with a
  CI exit code, and no dependency to install —
  the standard library has no YAML parser, so
  there is nothing to install even if you
  wanted to.

## Install

```sh
git clone https://github.com/haiderstudio/yaml-key-sort-checker-cli.git
cd yaml-key-sort-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one YAML file:

```sh
python3 src/yaml_key_sort_checker.py config.yaml
```

A file with sorted keys passes:

```sh
$ python3 src/yaml_key_sort_checker.py examples/good.yaml
OK — 1 file(s) checked, every mapping key is sorted.
```

A file with keys out of order fails, with the
key and line for each one:

```sh
$ python3 src/yaml_key_sort_checker.py examples/bad.yaml
FAIL examples/bad.yaml: line 4 key "apple" is out of order — it sorts before "zebra"
FAIL examples/bad.yaml: line 7 key "apple" is out of order — it sorts before "zebra"
FAIL examples/bad.yaml: line 9 key "banana" is out of order — it sorts before "mango"
Checked 1 file(s), 3 key(s) out of order in 1 file(s).
```

Check a whole folder (`.yaml` and `.yml` files
only — other files are never opened):

```sh
$ python3 src/yaml_key_sort_checker.py examples/
FAIL examples/bad.yaml: line 4 key "apple" is out of order — it sorts before "zebra"
FAIL examples/bad.yaml: line 7 key "apple" is out of order — it sorts before "zebra"
FAIL examples/bad.yaml: line 9 key "banana" is out of order — it sorts before "mango"
Checked 3 file(s), 3 key(s) out of order in 1 file(s).
```

Check one document from standard input:

```sh
$ printf 'zebra: 1\napple: 2\n' | python3 src/yaml_key_sort_checker.py --stdin
FAIL <stdin>: line 2 key "apple" is out of order — it sorts before "zebra"
Checked 1 file(s), 1 key(s) out of order in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/yaml_key_sort_checker.py --json examples/bad.yaml
{
  "files": [
    {
      "path": "examples/bad.yaml",
      "findings": [
        {
          "line": 4,
          "key": "apple",
          "previous": "zebra",
          "reason": "key \"apple\" is out of order — it sorts before \"zebra\""
        },
        {
          "line": 7,
          "key": "apple",
          "previous": "zebra",
          "reason": "key \"apple\" is out of order — it sorts before \"zebra\""
        },
        {
          "line": 9,
          "key": "banana",
          "previous": "mango",
          "reason": "key \"banana\" is out of order — it sorts before \"mango\""
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "findings": 3
}
```

Exit codes: 0 when every mapping key is
sorted, 1 when any key is out of order or a
file cannot be read, 2 for a usage error (a
missing path, a bad flag, or no YAML files
found).

## Examples

Sequences, block scalars, flow collections,
and quoted keys are handled — `examples/edge.yaml`
has a sequence of mappings, a block scalar
holding key-shaped text, a flow list, and
quoted keys, and it passes:

```sh
$ python3 src/yaml_key_sort_checker.py examples/edge.yaml
OK — 1 file(s) checked, every mapping key is sorted.
```

A tab-indented line is reported, not silently
skipped:

```sh
$ printf 'apple: 1\n\tbanana: 2\n' | python3 src/yaml_key_sort_checker.py --stdin
FAIL <stdin>: line 2 uses a tab for indentation — YAML forbids tabs
Checked 1 file(s), 1 key(s) out of order in 1 file(s).
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_yaml_key_sort_checker.py
```

The tests cover sorted files passing (sorted
keys, a single key, an empty document,
case-insensitive order, equal keys, nested
sorted mappings, comments and blank lines
ignored, quoted keys sorted, numeric keys
sorting as text, keys with dashes and
underscores, sequences of mappings sorted,
block scalar content not treated as keys,
folded block scalars, flow collections,
multi-line flow collections, multi-line plain
scalar continuations, multi-line quoted
scalars, document markers resetting the order,
anchor values with nested mappings, keys with
URL values, deeply nested sorted mappings, a
sequence of scalars followed by a key),
out-of-order keys flagged (a simple case, a
nested case, every bad key reported, a
case-insensitive flag, a quoted key flagged,
keys compared within one sequence item, keys
never compared across sequence items, a tab
indented line flagged, the finding naming both
keys), file problems (a file that is not valid
UTF-8, a missing file), the CLI (exit 0/1/2,
folder walking for `.yaml` and `.yml` files,
nested folders, `--no-recursive`, `--exclude`
for files and folders, `.git` skipped, a direct
file checked whatever its name, duplicate paths
checked once, `--json` output, `--stdin` clean
and flagged, `--stdin` with paths refused,
`--version`, a non-UTF-8 file reported, input
files left unchanged, the tool run from another
folder and from the filesystem root, the tool
run under a fake HOME), the bundled examples
(sample output compared byte-for-byte against a
fresh run, and the README-quoted outputs checked
against it), and hygiene checks (no placeholder
text, no absolute paths, stdlib imports only,
no network use in the source, `.env` first in
`.gitignore`, CI file runs the test file, README
names the neighbouring repos).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo.
The idea of sorting YAML keys is not new — the
same reason repo #90,
requirements-sort-checker-cli, exists for
requirements files — but no existing tool
checks YAML key order in local files as a
tested command-line gate, as the search above
shows — and every line of code here is
original, built on nothing but Python's
standard library, using the same
indentation-based technique as repo #71,
yaml-indent-checker-cli.
