#!/usr/bin/env python3
"""Check YAML files for mapping keys in sorted order.

Run: python3 src/yaml_key_sort_checker.py config.yaml
     python3 src/yaml_key_sort_checker.py project/
     python3 src/yaml_key_sort_checker.py --stdin < config.yaml

Sorted keys give cleaner diffs and make a
duplicate or misplaced key obvious at a glance —
the same reason requirements files are sorted.
This tool reads the YAML files you point it at,
checks the keys of every mapping are in
alphabetical order, and reports each key that is
out of order with the file and the line number.
It exits 1 when any key is out of order, so it
can fail a CI run. A file with sorted keys
exits 0.

Order is plain alphabetical order on the key
text, ignoring case — "Apple" sorts before
"banana", and "10" sorts before "2", because
the check compares characters, not numbers.
Keys are compared inside their own mapping
only: a nested mapping starts its own order,
and each item of a sequence starts its own
order, so a key is never compared against a
key from another mapping. Comments and blank
lines are ignored, and a key inside a block
scalar, a flow collection, or a multi-line
string is content, not a key, and is never
checked.

The checker is hand-rolled and uses the Python
standard library only: the standard library has
no YAML parser, so this tool reads lines and
tracks indentation level by level, the same
technique as the yaml-indent checker. That is
enough to know which keys share a mapping and
which order they are in, without ever parsing
a value.

It never rewrites a file, never touches the
network, and reads only the files and folders
you point it at.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"

DOUBLE_KEY_RE = re.compile(r'"((?:[^"\\]|\\.)*)"\s*:(\s|$)')
SINGLE_KEY_RE = re.compile(r"'((?:[^']|'')*)'\s*:(\s|$)")
PLAIN_KEY_RE = re.compile(r"(.+?)\s*:(\s|$)")


def strip_comment(line):
    """Remove a trailing YAML comment: '#' outside quotes, at the start or after whitespace."""
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_single:
            if ch == "'":
                if i + 1 < len(line) and line[i + 1] == "'":
                    i += 2
                    continue
                in_single = False
        elif in_double:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_double = False
        else:
            if ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
                return line[:i]
        i += 1
    return line


def flow_delta(text):
    """Net change in flow-collection depth from one line, quotes ignored."""
    depth = 0
    in_single = False
    in_double = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_single:
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    i += 2
                    continue
                in_single = False
        elif in_double:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_double = False
        else:
            if ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
        i += 1
    return depth


def quote_closes(text, quote):
    """True when a quoted scalar starting this text closes on the same line."""
    i = 1
    while i < len(text):
        ch = text[i]
        if quote == '"':
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                return True
        else:
            if ch == "'":
                if i + 1 < len(text) and text[i + 1] == "'":
                    i += 2
                    continue
                return True
        i += 1
    return False


def extract_key(text):
    """Split mapping text into (key, rest) or (None, None).

    text is one line with its indent and any "- "
    prefix already removed. A quoted key is
    unquoted; a plain key keeps its text as
    written, without trailing spaces.
    """
    match = DOUBLE_KEY_RE.match(text)
    if match:
        return match.group(1), text[match.end():]
    match = SINGLE_KEY_RE.match(text)
    if match:
        return match.group(1).replace("''", "'"), text[match.end():]
    match = PLAIN_KEY_RE.match(text)
    if match:
        return match.group(1).strip(), text[match.end():]
    return None, None


def _strip_anchor_or_tag(value):
    """Remove leading anchor/tag tokens from a value.

    "key: &name" leaves nothing, so the value is a
    nested mapping below; "key: &name [1, 2]"
    leaves the flow collection.
    """
    rest = value.strip()
    while rest.startswith("&") or rest.startswith("!"):
        parts = rest.split(None, 1)
        if len(parts) == 1:
            return ""
        rest = parts[1].lstrip()
    return rest


def check_text(text):
    """Check one document's text.

    Returns a list of findings, each {"line": int,
    "key": str or None, "previous": str or None,
    "reason": str}, in document order. A finding
    with a key names a key out of order; a finding
    with no key names a line that uses a tab for
    indentation, which YAML forbids.
    """
    findings = []
    # Each mapping open: [indent column, last key seen, lowercased].
    stack = []
    flow_depth = 0
    block_indent = None
    quote_char = None
    continuation_indent = None

    def note_key(line_no, column, key):
        """Compare one key against its mapping, record a finding if out of order."""
        lowered = key.lower()
        while stack and stack[-1][0] > column:
            stack.pop()
        if stack and stack[-1][0] == column:
            previous = stack[-1][1]
            if previous is not None and lowered < previous:
                findings.append({
                    "line": line_no,
                    "key": key,
                    "previous": previous,
                    "reason": ('key "%s" is out of order — it sorts '
                               'before "%s"' % (key, previous)),
                })
            stack[-1][1] = lowered
        else:
            stack.append([column, lowered])

    for number, raw in enumerate(text.splitlines(), 1):
        if raw.strip() == "":
            continue
        leading = raw[:len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in leading:
            findings.append({
                "line": number,
                "key": None,
                "previous": None,
                "reason": ("uses a tab for indentation — "
                           "YAML forbids tabs"),
            })
            continue
        indent = len(leading)
        stripped = raw[indent:]
        if block_indent is not None:
            if indent > block_indent:
                continue
            block_indent = None
        if quote_char is not None:
            if quote_closes(stripped, quote_char):
                quote_char = None
            continue
        if continuation_indent is not None:
            if indent > continuation_indent:
                continue
            continuation_indent = None
        content = strip_comment(raw).rstrip()
        if content.strip() == "":
            continue
        body = content.lstrip(" ")
        if body in ("---", "..."):
            stack = []
            flow_depth = 0
            block_indent = None
            quote_char = None
            continuation_indent = None
            continue
        if body.startswith("? "):
            continue
        delta = flow_delta(body)
        if flow_depth > 0:
            flow_depth += delta
            continue
        if body[0] in "[{":
            flow_depth += delta
            continue
        is_sequence = body == "-" or body.startswith("- ")
        if is_sequence:
            item = body[2:] if body.startswith("- ") else ""
            key_column = indent + 2
            while stack and stack[-1][0] > indent:
                stack.pop()
            if item == "":
                continue
            key, rest = extract_key(item)
            if key is None:
                while stack and stack[-1][0] >= key_column:
                    stack.pop()
                continue
            while stack and stack[-1][0] >= key_column:
                stack.pop()
            note_key(number, key_column, key)
            value = _strip_anchor_or_tag(rest)
            if value == "":
                pass
            elif value[0] in "|>":
                block_indent = key_column
            elif value[0] in "[{":
                flow_depth += delta
            elif value[0] in "\"'" and not quote_closes(value, value[0]):
                quote_char = value[0]
            else:
                continuation_indent = key_column
            continue
        key, rest = extract_key(body)
        if key is None:
            continue
        note_key(number, indent, key)
        value = _strip_anchor_or_tag(rest)
        if value == "":
            pass
        elif value[0] in "|>":
            block_indent = indent
        elif value[0] in "[{":
            flow_depth += delta
        elif value[0] in "\"'" and not quote_closes(value, value[0]):
            quote_char = value[0]
        else:
            continuation_indent = indent
    return findings


def check_file(path):
    """Check one file. Returns (findings, error)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], str(exc)
    return check_text(text), None


def _is_yaml_file(path):
    name = Path(path).name.lower()
    return name.endswith(".yaml") or name.endswith(".yml")


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of YAML files.

    A file given directly is always checked, whatever
    its name. A folder is walked for files ending in
    .yaml or .yml only, recursively by default. .git
    folders are never walked, and directory links
    are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for dirpath, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(dirpath) / name
                    if not _is_yaml_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_finding(path, finding):
    """One human-readable line for one out-of-order key."""
    return ("FAIL %s: line %d %s"
            % (path, finding["line"], finding["reason"]))


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except (FileNotFoundError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no YAML files found", file=sys.stderr)
        return 2
    results = []
    findings = 0
    files_with_findings = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            findings += count
            files_with_findings += 1
        results.append({"path": path, "findings": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "findings": findings},
            indent=2, ensure_ascii=False))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for finding in result["findings"]:
                print(format_finding(result["path"], finding))
        if findings:
            print("Checked %d file(s), %d key(s) out of order "
                  "in %d file(s)." % (len(files), findings,
                                      files_with_findings))
        else:
            print("OK — %d file(s) checked, every mapping key "
                  "is sorted." % len(files))
    return 1 if findings else 0


def run_stdin(as_json=False):
    """Check one YAML document read from standard input."""
    text = sys.stdin.read()
    bad = check_text(text)
    findings = len(bad)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "findings": bad,
                        "error": None}],
             "checked": 1, "findings": findings},
            indent=2, ensure_ascii=False))
    else:
        for finding in bad:
            print(format_finding("<stdin>", finding))
        if findings:
            print("Checked 1 file(s), %d key(s) out of order "
                  "in 1 file(s)." % findings)
        else:
            print("OK — 1 file(s) checked, every mapping key "
                  "is sorted.")
    return 1 if findings else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="yaml_key_sort_checker",
        description="Check YAML mapping keys are sorted "
                    "alphabetically, fail CI when one is out "
                    "of order. Report-only: it never edits "
                    "a file.")
    parser.add_argument("paths", nargs="*",
                        help="YAML files or folders to walk")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one YAML document from "
                             "standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one YAML file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
