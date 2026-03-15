"""Tests for diff_parser — unified diff parsing into per-file structures."""
import pytest
from app.services.diff_parser import FileDiff, parse_unified_diff, diff_files_to_dict


SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
index abc1234..def5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,6 @@
 import os
+import sys

 def main():
-    print("hello")
+    print("hello world")
     return 0
"""

NEW_FILE_DIFF = """\
diff --git a/src/new_file.py b/src/new_file.py
new file mode 100644
index 0000000..abc1234
--- /dev/null
+++ b/src/new_file.py
@@ -0,0 +1,3 @@
+def greet():
+    return "hi"
+
"""

DELETED_FILE_DIFF = """\
diff --git a/old.txt b/old.txt
deleted file mode 100644
index abc1234..0000000
--- a/old.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-line one
-line two
"""

RENAME_DIFF = """\
diff --git a/old_name.py b/new_name.py
similarity index 95%
rename from old_name.py
rename to new_name.py
index abc..def 100644
--- a/old_name.py
+++ b/new_name.py
@@ -1,3 +1,3 @@
-# old
+# new
 pass
"""

MULTI_FILE_DIFF = SAMPLE_DIFF + NEW_FILE_DIFF + DELETED_FILE_DIFF


class TestParseUnifiedDiff:
    def test_empty_input(self):
        assert parse_unified_diff("") == []
        assert parse_unified_diff(None) == []
        assert parse_unified_diff("   \n  ") == []

    def test_modified_file(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert len(files) == 1
        f = files[0]
        assert f.path == "src/main.py"
        assert f.status == "M"
        assert f.additions == 2
        assert f.deletions == 1

    def test_new_file(self):
        files = parse_unified_diff(NEW_FILE_DIFF)
        assert len(files) == 1
        f = files[0]
        assert f.path == "src/new_file.py"
        assert f.status == "A"
        assert f.additions == 3
        assert f.deletions == 0

    def test_deleted_file(self):
        files = parse_unified_diff(DELETED_FILE_DIFF)
        assert len(files) == 1
        f = files[0]
        assert f.path == "old.txt"
        assert f.status == "D"
        assert f.additions == 0
        assert f.deletions == 2

    def test_renamed_file(self):
        files = parse_unified_diff(RENAME_DIFF)
        assert len(files) == 1
        f = files[0]
        assert f.path == "new_name.py"
        assert f.status == "R"

    def test_multi_file(self):
        files = parse_unified_diff(MULTI_FILE_DIFF)
        assert len(files) == 3
        paths = [f.path for f in files]
        assert "src/main.py" in paths
        assert "src/new_file.py" in paths
        assert "old.txt" in paths

    def test_patch_content_preserved(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert "diff --git" in files[0].patch
        assert "+import sys" in files[0].patch

    def test_no_diff_headers(self):
        assert parse_unified_diff("just some random text\nno diffs here") == []


class TestDiffFilesToDict:
    def test_converts_to_dicts(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        dicts = diff_files_to_dict(files)
        assert len(dicts) == 1
        d = dicts[0]
        assert d["path"] == "src/main.py"
        assert d["status"] == "M"
        assert d["additions"] == 2
        assert d["deletions"] == 1
        assert isinstance(d["patch"], str)

    def test_empty_list(self):
        assert diff_files_to_dict([]) == []

    def test_roundtrip_fields(self):
        files = parse_unified_diff(MULTI_FILE_DIFF)
        dicts = diff_files_to_dict(files)
        for d in dicts:
            assert set(d.keys()) == {"path", "status", "additions", "deletions", "patch"}
