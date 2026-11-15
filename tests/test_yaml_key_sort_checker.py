#!/usr/bin/env python3
"""Tests for yaml_key_sort_checker — stdlib unittest only."""

import ast
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml_key_sort_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


def findings_of(text):
    return checker.check_text(text)


class TestSortedPasses(unittest.TestCase):
    def test_sorted_keys_pass(self):
        self.assertEqual(findings_of("apple: 1\nbanana: 2\ncherry: 3\n"),
                         [])

    def test_single_key_passes(self):
        self.assertEqual(findings_of("only: 1\n"), [])

    def test_empty_document_passes(self):
        self.assertEqual(findings_of(""), [])
        self.assertEqual(findings_of("\n\n"), [])

    def test_case_insensitive_order_passes(self):
        self.assertEqual(
            findings_of("Apple: 1\nbanana: 2\nCherry: 3\n"), [])

    def test_equal_keys_pass(self):
        # Duplicates are another checker's job; equal keys
        # are not out of order.
        self.assertEqual(findings_of("apple: 1\napple: 2\n"), [])

    def test_nested_sorted_passes(self):
        text = ("app:\n"
                "  name: x\n"
                "  port: 3000\n"
                "  version: 1\n")
        self.assertEqual(findings_of(text), [])

    def test_comments_and_blank_lines_ignored(self):
        text = ("# a comment\n"
                "\n"
                "apple: 1 # trailing comment\n"
                "\n"
                "# zebra: 9 is only a comment\n"
                "banana: 2\n")
        self.assertEqual(findings_of(text), [])

    def test_quoted_keys_sorted_pass(self):
        text = ("'alpha': 1\n"
                '"Beta": 2\n')
        self.assertEqual(findings_of(text), [])

    def test_numeric_keys_sort_as_text(self):
        # "10" sorts before "2": plain alphabetical order.
        self.assertEqual(findings_of("10: a\n2: b\n"), [])

    def test_keys_with_dashes_and_underscores(self):
        self.assertEqual(
            findings_of("api-key: 1\napi_key: 2\napp-name: 3\n"), [])

    def test_sequence_of_mappings_sorted_passes(self):
        text = ("items:\n"
                "  - address: a\n"
                "    name: x\n"
                "  - address: b\n"
                "    name: y\n")
        self.assertEqual(findings_of(text), [])

    def test_block_scalar_content_not_keys(self):
        text = ("note: |\n"
                "  zebra: this is text\n"
                "  apple: so is this\n"
                "zebra: 1\n")
        self.assertEqual(findings_of(text), [])

    def test_folded_block_scalar_content_not_keys(self):
        text = ("note: >\n"
                "  zebra: text\n"
                "  apple: text\n"
                "zebra: 1\n")
        self.assertEqual(findings_of(text), [])

    def test_flow_collection_keys_not_checked(self):
        self.assertEqual(findings_of("tags: [zebra, apple]\n"), [])
        self.assertEqual(
            findings_of("pair: {zebra: 1, apple: 2}\n"), [])

    def test_multiline_flow_collection_not_checked(self):
        text = ("tags: [\n"
                "  zebra: 1,\n"
                "  apple: 2,\n"
                "]\n"
                "zebra: 3\n")
        self.assertEqual(findings_of(text), [])

    def test_multiline_plain_scalar_continuation(self):
        text = ("apple: some long\n"
                "  zebra: text with a colon\n"
                "  mango: more text\n"
                "banana: 1\n")
        self.assertEqual(findings_of(text), [])

    def test_multiline_quoted_scalar(self):
        text = ("apple: \"a long\n"
                "  zebra: title\n"
                "  mango: more\"\n"
                "banana: 1\n")
        self.assertEqual(findings_of(text), [])

    def test_document_markers_reset_order(self):
        text = ("zebra: 1\n"
                "---\n"
                "apple: 2\n")
        self.assertEqual(findings_of(text), [])

    def test_anchor_value_with_nested_mapping(self):
        text = ("app: &defaults\n"
                "  name: x\n"
                "  port: 1\n"
                "banana: 2\n")
        self.assertEqual(findings_of(text), [])

    def test_key_with_url_value(self):
        text = ("apple: http://example.com\n"
                "banana: 2\n")
        self.assertEqual(findings_of(text), [])

    def test_deeply_nested_sorted(self):
        text = ("a:\n"
                "  b:\n"
                "    c: 1\n"
                "    d: 2\n"
                "  e: 3\n"
                "f: 4\n")
        self.assertEqual(findings_of(text), [])

    def test_sequence_of_scalars_then_key(self):
        text = ("items:\n"
                "  - one\n"
                "  - two\n"
                "name: x\n")
        self.assertEqual(findings_of(text), [])


class TestOutOfOrderFlagged(unittest.TestCase):
    def test_simple_out_of_order(self):
        found = findings_of("zebra: 1\napple: 2\n")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["line"], 2)
        self.assertEqual(found[0]["key"], "apple")
        self.assertEqual(found[0]["previous"], "zebra")

    def test_nested_out_of_order(self):
        text = ("app:\n"
                "  zebra: 1\n"
                "  apple: 2\n")
        found = findings_of(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["line"], 3)

    def test_each_bad_key_reported(self):
        text = "c: 1\nb: 2\na: 3\n"
        found = findings_of(text)
        self.assertEqual([f["line"] for f in found], [2, 3])

    def test_case_insensitive_flag(self):
        found = findings_of("Banana: 1\napple: 2\n")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["key"], "apple")

    def test_quoted_key_out_of_order(self):
        found = findings_of('"zebra": 1\n\'apple\': 2\n')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["key"], "apple")

    def test_sequence_item_keys_compared_within_item(self):
        text = ("items:\n"
                "  - name: x\n"
                "    address: y\n")
        found = findings_of(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["key"], "address")

    def test_sequence_items_do_not_compare_across_items(self):
        # "name" in the second item is not compared
        # against "name" in the first item.
        text = ("items:\n"
                "  - name: b\n"
                "    age: 3\n"
                "  - name: a\n"
                "    age: 2\n")
        found = findings_of(text)
        self.assertEqual(len(found), 2)
        self.assertEqual([f["key"] for f in found],
                         ["age", "age"])

    def test_tab_indentation_flagged(self):
        found = findings_of("apple: 1\n\tbanana: 2\n")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["line"], 2)
        self.assertIsNone(found[0]["key"])
        self.assertIn("tab", found[0]["reason"])

    def test_finding_reason_names_both_keys(self):
        found = findings_of("zebra: 1\napple: 2\n")
        self.assertIn("apple", found[0]["reason"])
        self.assertIn("zebra", found[0]["reason"])


class TestCheckFile(unittest.TestCase):
    def test_non_utf8_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.yaml", b"\xff\xfe\n")
            bad, error = checker.check_file(path)
            self.assertEqual(bad, [])
            self.assertIn("UTF-8", error)

    def test_missing_file_is_an_error(self):
        bad, error = checker.check_file("/nonexistent/missing.yaml")
        self.assertEqual(bad, [])
        self.assertTrue(error)


class TestCLI(unittest.TestCase):
    def test_sorted_file_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "good.yaml", "apple: 1\nbanana: 2\n")
            code, out, _err = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn("OK —", out)

    def test_unsorted_file_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.yaml", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("FAIL", out)
            self.assertIn('key "apple" is out of order', out)
            self.assertIn("1 key(s) out of order", out)

    def test_no_paths_is_usage_error(self):
        code, _out, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("give at least one", err)

    def test_missing_path_is_usage_error(self):
        code, _out, err = run_cli(["no-such-file.yaml"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _out, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no YAML files found", err)

    def test_bad_flag_is_usage_error(self):
        code, _out, _err = run_cli(["--nope"])
        self.assertEqual(code, 2)

    def test_folder_walk_finds_yaml_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.yaml", "zebra: 1\napple: 2\n")
            write(tmp, "b.yml", "apple: 1\nbanana: 2\n")
            write(tmp, "notes.txt", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("a.yaml", out)
            self.assertNotIn("notes.txt", out)
            self.assertIn("Checked 2 file(s)", out)

    def test_nested_folders_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "sub/deep.yaml", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("deep.yaml", out)

    def test_no_recursive_stops_at_top_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "top.yaml", "apple: 1\n")
            write(tmp, "sub/deep.yaml", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli(["--no-recursive", tmp])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_exclude_pattern_skips_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "keep.yaml", "apple: 1\n")
            write(tmp, "skip.yaml", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli(["--exclude", "*skip.yaml", tmp])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_exclude_pattern_skips_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "keep.yaml", "apple: 1\n")
            write(tmp, "vendor/bad.yaml", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli(["--exclude", "vendor", tmp])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_git_folder_never_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/sample.yaml", "zebra: 1\napple: 2\n")
            write(tmp, "app.yaml", "apple: 1\n")
            code, out, _err = run_cli([tmp])
            self.assertEqual(code, 0)
            self.assertIn("1 file(s) checked", out)

    def test_direct_file_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "config.txt", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn('key "apple" is out of order', out)

    def test_duplicate_paths_checked_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.yaml", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli([path, path])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.yaml", "zebra: 1\napple: 2\n")
            code, out, _err = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 1)
            self.assertEqual(data["files"][0]["findings"][0]["key"],
                             "apple")
            self.assertEqual(data["files"][0]["findings"][0]["line"], 2)
            self.assertIsNone(data["files"][0]["error"])

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("apple: 1\nbanana: 2\n")
            code, out, _err = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn("OK —", out)

    def test_stdin_flagged(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("zebra: 1\napple: 2\n")
            code, out, _err = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn('key "apple" is out of order', out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _out, err = run_cli(["--stdin", "a.yaml"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _err = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("yaml_key_sort_checker 1.0.0", out)

    def test_non_utf8_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.yaml", b"\xff\xfe\n")
            code, out, _err = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.yaml", "zebra: 1\napple: 2\n")
            before = Path(path).read_text()
            run_cli([path])
            self.assertEqual(Path(path).read_text(), before)

    def test_cli_runs_from_another_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.yaml", "zebra: 1\napple: 2\n")
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src/yaml_key_sort_checker.py"),
                 path],
                cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('key "apple" is out of order',
                          result.stdout)

    def test_cli_runs_from_filesystem_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.yaml", "apple: 1\n")
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src/yaml_key_sort_checker.py"),
                 path],
                cwd="/", capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn("OK —", result.stdout)

    def test_cli_runs_under_fake_home(self):
        # A test that only passes because a local path exists
        # is not a passing test: HOME must not matter.
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = str(Path(tmp) / "fakehome")
            os.makedirs(fake_home)
            path = write(tmp, "a.yaml", "zebra: 1\napple: 2\n")
            env = dict(os.environ, HOME=fake_home)
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src/yaml_key_sort_checker.py"),
                 path],
                cwd=tmp, capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn('key "apple" is out of order',
                          result.stdout)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        good = subprocess.run(
            [sys.executable, "src/yaml_key_sort_checker.py",
             "examples/good.yaml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0)
        self.assertIn(good.stdout.strip(), readme)
        bad = subprocess.run(
            [sys.executable, "src/yaml_key_sort_checker.py",
             "examples/bad.yaml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(bad.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/yaml_key_sort_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 3 file(s), 3 key(s) out of order "
                      "in 1 file(s).", folder.stdout)
        self.assertIn("Checked 3 file(s), 3 key(s) out of order "
                      "in 1 file(s).", readme)
        edge = subprocess.run(
            [sys.executable, "src/yaml_key_sort_checker.py",
             "examples/edge.yaml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(edge.returncode, 0)
        self.assertIn(edge.stdout.strip(), readme)
        js = subprocess.run(
            [sys.executable, "src/yaml_key_sort_checker.py",
             "--json", "examples/bad.yaml"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True, skip_examples=True):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")
                       and not (skip_tests and d == "tests")
                       and not (skip_examples and d == "examples")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True,
                                     skip_examples=False):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\", "/tmp/"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src/yaml_key_sort_checker.py",
                       REPO / "tests/test_yaml_key_sort_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"yaml_key_sort_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src/yaml_key_sort_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_yaml_key_sort_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        self.assertIn("yaml-indent-checker-cli", readme)
        self.assertIn("yaml-duplicate-key-checker-cli", readme)
        self.assertIn("yaml-bool-checker-cli", readme)
        self.assertIn("requirements-sort-checker-cli", readme)


if __name__ == "__main__":
    unittest.main()
