"""Tests for utility functions."""

import hashlib
import tempfile
from pathlib import Path

from ma2_forums_miner.utils import sha256_file, safe_thread_folder


class TestSha256File:
    def test_known_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        expected = "sha256:" + hashlib.sha256(b"hello world").hexdigest()
        assert sha256_file(f) == expected

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        expected = "sha256:" + hashlib.sha256(b"").hexdigest()
        assert sha256_file(f) == expected

    def test_large_file(self, tmp_path):
        """Verify chunked reading works for files larger than 8KB."""
        f = tmp_path / "large.bin"
        data = b"x" * 20000
        f.write_bytes(data)
        expected = "sha256:" + hashlib.sha256(data).hexdigest()
        assert sha256_file(f) == expected


class TestSafeThreadFolder:
    def test_basic(self):
        result = safe_thread_folder("30890", "Moving Fixtures Between Layers")
        assert result == "thread_30890_Moving_Fixtures_Between_Layers"

    def test_special_characters_removed(self):
        result = safe_thread_folder("12345", 'How to: Export/Import "Shows"?')
        assert "/" not in result
        assert ":" not in result
        assert '"' not in result
        assert "?" not in result
        assert result.startswith("thread_12345_")

    def test_truncation(self):
        long_title = "A" * 100
        result = safe_thread_folder("99999", long_title, max_length=20)
        title_part = result.replace("thread_99999_", "")
        assert len(title_part) <= 20

    def test_spaces_to_underscores(self):
        result = safe_thread_folder("1", "hello world foo")
        assert " " not in result
        assert "hello_world_foo" in result

    def test_path_traversal_characters(self):
        result = safe_thread_folder("1", "../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result
        assert result.startswith("thread_1_")
