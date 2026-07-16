import io
from pathlib import Path

import pytest

from app.notes_tags import count_tags, extract_tags, iter_markdown, main, notes_tags

NOTES = Path(__file__).parent / "data" / "notes"


class TestExtractTags:
    def test_finds_tags_and_preserves_order(self):
        assert extract_tags("#beta then #alpha then #beta") == ["beta", "alpha", "beta"]

    def test_tag_at_start_of_line(self):
        assert extract_tags("#alpha leads the line") == ["alpha"]

    @pytest.mark.parametrize("text", ["# Heading", "## Sub-heading", "###### Deep"])
    def test_headings_are_not_tags(self, text):
        assert extract_tags(text) == []

    def test_url_fragment_is_not_a_tag(self):
        assert extract_tags("see https://example.com/docs#install now") == []

    def test_numeric_reference_is_not_a_tag(self):
        assert extract_tags("fixes #123") == []

    def test_alphanumeric_tag_is_allowed(self):
        assert extract_tags("#py3 and #v2rollout") == ["py3", "v2rollout"]

    def test_fenced_code_is_skipped(self):
        text = "#kept\n\n```python\n# comment\nx = '#hidden'\n```\n\n#also-kept"
        assert extract_tags(text) == ["kept", "also-kept"]

    def test_tilde_fenced_code_is_skipped(self):
        assert extract_tags("~~~\n#hidden\n~~~\n#kept") == ["kept"]

    def test_shorter_inner_fence_does_not_close_a_longer_outer_fence(self):
        assert extract_tags("````\n```\n#hidden\n```\n````\n#kept") == ["kept"]

    def test_longer_closing_fence_is_allowed(self):
        assert extract_tags("```\n#hidden\n``````\n#kept") == ["kept"]

    def test_a_different_fence_character_does_not_close(self):
        assert extract_tags("```\n~~~\n#hidden\n```\n#kept") == ["kept"]

    def test_info_string_does_not_close_a_fence(self):
        # "```python" inside a block is content, not a terminator.
        assert extract_tags("```\n```python\n#hidden\n```\n#kept") == ["kept"]

    def test_unclosed_fence_swallows_rest_of_file(self):
        assert extract_tags("#kept\n```\n#hidden\n") == ["kept"]

    def test_inline_code_is_skipped(self):
        assert extract_tags("use `#hidden` but keep #kept") == ["kept"]

    def test_nested_tags_are_kept_whole(self):
        assert extract_tags("#project/alpha") == ["project/alpha"]

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("#done.", "done"),
            ("#done,", "done"),
            ("#done!", "done"),
            ("#done?", "done"),
            ("(#done)", "done"),
            ("#done's", "done"),
            ("#project/", "project"),
            ("#done-", "done"),
        ],
    )
    def test_surrounding_punctuation_is_trimmed(self, text, expected):
        assert extract_tags(text) == [expected]

    def test_hyphens_and_underscores_are_kept(self):
        assert extract_tags("#in-progress #needs_review") == ["in-progress", "needs_review"]

    def test_tags_are_case_sensitive(self):
        assert extract_tags("#Python #python") == ["Python", "python"]

    def test_empty_text(self):
        assert extract_tags("") == []


class TestIterMarkdown:
    def test_finds_markdown_recursively_and_ignores_other_files(self):
        found = {p.relative_to(NOTES).as_posix() for p in iter_markdown(NOTES)}
        assert found == {
            "basic.md",
            "edge-cases.md",
            "headings-and-code.md",
            "no-tags.md",
            "sub/nested-note.md",
        }

    def test_single_file_path(self):
        assert list(iter_markdown(NOTES / "basic.md")) == [NOTES / "basic.md"]

    def test_hidden_directories_are_skipped(self):
        # tests/data/notes/.obsidian/plugin-readme.md exists and must not appear.
        assert not any(".obsidian" in p.parts for p in iter_markdown(NOTES))

    def test_a_dotted_root_is_still_scanned(self, tmp_path):
        # Hidden-ness is judged relative to the root, so pointing at a dotted
        # directory on purpose must not filter everything away.
        root = tmp_path / ".obsidian"
        root.mkdir()
        (root / "note.md").write_text("#alpha\n")
        assert [p.name for p in iter_markdown(root)] == ["note.md"]

    def test_missing_path_raises_eagerly(self, tmp_path):
        # Not wrapped in list(): the error must surface at call time, not on
        # first iteration.
        with pytest.raises(FileNotFoundError):
            iter_markdown(tmp_path / "nope")


class TestCountTags:
    def test_counts_across_the_example_notes(self):
        assert count_tags(NOTES) == {
            "python": 4,  # three in basic.md, one in sub/nested-note.md
            "testing": 2,
            "markdown": 2,
            "project/alpha": 1,
            "project/beta": 1,
            "done": 1,
            "shipped": 1,
            "wrapped": 1,
            "in-progress": 1,
            "needs_review": 1,
            "recursion": 1,
        }

    def test_counts_a_single_file(self):
        assert count_tags(NOTES / "basic.md") == {"python": 3, "testing": 2}

    def test_file_without_tags(self):
        assert count_tags(NOTES / "no-tags.md") == {}

    def test_accepts_a_string_path(self):
        assert count_tags(str(NOTES / "basic.md")) == {"python": 3, "testing": 2}

    def test_empty_directory(self, tmp_path):
        assert count_tags(tmp_path) == {}

    def test_hidden_directories_contribute_nothing(self, tmp_path):
        (tmp_path / "note.md").write_text("#alpha\n")
        vendored = tmp_path / ".venv"
        vendored.mkdir()
        (vendored / "README.md").write_text("#vendored\n")
        assert count_tags(tmp_path) == {"alpha": 1}

    def test_byte_order_mark_does_not_swallow_the_first_tag(self, tmp_path):
        note = tmp_path / "bom.md"
        note.write_bytes(b"\xef\xbb\xbf#alpha and #beta\n")
        assert count_tags(note) == {"alpha": 1, "beta": 1}

    def test_undecodable_note_does_not_abort_the_scan(self, tmp_path):
        (tmp_path / "good.md").write_text("#alpha\n")
        (tmp_path / "latin.md").write_bytes("#caf\xe9 and #beta\n".encode("latin-1"))
        # The malformed byte costs us that one tag, but #beta in the same file
        # and every tag in every other file still land.
        counts = count_tags(tmp_path)
        assert counts["alpha"] == 1
        assert counts["beta"] == 1


class TestNotesTags:
    def test_prints_each_tag_with_its_count_sorted(self, tmp_path):
        (tmp_path / "note.md").write_text("#beta #alpha #beta #Gamma\n")
        out = io.StringIO()
        notes_tags(tmp_path, file=out)
        assert [line.split() for line in out.getvalue().splitlines()] == [
            ["#alpha", "1"],
            ["#beta", "2"],
            ["#Gamma", "1"],
        ]

    def test_columns_are_aligned(self, tmp_path):
        (tmp_path / "note.md").write_text("#a #considerably-longer\n")
        out = io.StringIO()
        notes_tags(tmp_path, file=out)
        lines = out.getvalue().splitlines()
        assert [line.rindex("1") for line in lines] == [len(lines[1]) - 1] * 2

    def test_returns_the_counts(self, tmp_path):
        (tmp_path / "note.md").write_text("#alpha #alpha\n")
        assert notes_tags(tmp_path, file=io.StringIO()) == {"alpha": 2}

    def test_prints_nothing_when_there_are_no_tags(self, tmp_path):
        (tmp_path / "note.md").write_text("just prose\n")
        out = io.StringIO()
        notes_tags(tmp_path, file=out)
        assert out.getvalue() == ""


class TestMain:
    def test_scans_the_given_path(self, capsys):
        assert main([str(NOTES / "basic.md")]) == 0
        assert capsys.readouterr().out == "#python   3\n#testing  2\n"

    def test_defaults_to_the_working_directory(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "note.md").write_text("#alpha\n")
        monkeypatch.chdir(tmp_path)
        assert main([]) == 0
        assert capsys.readouterr().out == "#alpha  1\n"

    def test_missing_path_reports_an_error(self, tmp_path, capsys):
        assert main([str(tmp_path / "nope")]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "notes-tags:" in captured.err

    def test_undecodable_note_does_not_raise(self, tmp_path, capsys):
        # UnicodeDecodeError is a ValueError, so it would sail past the OSError
        # handler and reach the user as a traceback.
        (tmp_path / "latin.md").write_bytes("#alpha tag\n".encode("latin-1") + b"\xff\xfe")
        assert main([str(tmp_path)]) == 0
        assert capsys.readouterr().out == "#alpha  1\n"

    def test_unreadable_directory_reports_an_error(self, tmp_path, capsys):
        note = tmp_path / "note.md"
        note.write_text("#alpha\n")
        note.chmod(0o000)
        try:
            assert main([str(note)]) == 1
            assert "notes-tags:" in capsys.readouterr().err
        finally:
            note.chmod(0o644)
