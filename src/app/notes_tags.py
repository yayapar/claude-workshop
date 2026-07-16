"""Count the #tags used across a collection of Markdown notes.

Two limitations are accepted deliberately, rather than growing a full CommonMark
parser inside a tag counter:

- Four-space-indented code blocks are not treated as code, so tags inside them
  are counted. Detecting them correctly means tracking list context, because an
  indented line beneath a list item is a continuation rather than code, and
  getting that wrong would silently drop real tags.
- An inline code span that wraps across a newline is only stripped on its first
  line, so a tag on its second line can leak.
"""

import argparse
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

__all__ = ["count_tags", "extract_tags", "iter_markdown", "main", "notes_tags"]

# A tag must start the line or follow whitespace or an opening bracket, which
# rules out URL fragments (example.com#install). The body needs at least one
# letter or underscore, which rules out issue references (#123). A leading "# "
# is a heading, not a tag, and never matches because the body cannot start with
# a space.
TAG_RE = re.compile(
    r"""(?:(?<=[\s(\[{"'])|^)\#([A-Za-z0-9_/-]*[A-Za-z_][A-Za-z0-9_/-]*)""",
    re.MULTILINE,
)

# Group 1 is the run of fence characters, group 2 the info string ("python" in
# "```python"). CommonMark allows up to three spaces of indentation.
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
INLINE_CODE_RE = re.compile(r"`+[^`]*`+")


def _strip_code(text: str) -> str:
    """Blank out fenced code blocks and inline code spans.

    Code is replaced rather than deleted so that surrounding text cannot be
    joined together into a token that looks like a tag.

    A closing fence must use the same character as its opening fence and be at
    least as long, per CommonMark. Length matters: a note documenting Markdown
    itself may wrap a ``` example in a ```` fence, and treating the inner fence
    as the closing one would spill the example back into the counted text.
    """
    lines: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if fence is None:
            if match:
                marker = match.group(1)
                fence = (marker[0], len(marker))
                lines.append("")
            else:
                lines.append(INLINE_CODE_RE.sub(" ", line))
        else:
            lines.append("")
            if match:
                marker = match.group(1)
                char, length = fence
                # A closing fence carries no info string, so "```python" while
                # already inside a block is content rather than a terminator.
                if marker[0] == char and len(marker) >= length and not match.group(2).strip():
                    fence = None
    return "\n".join(lines)


def extract_tags(text: str) -> list[str]:
    """Return every tag in `text`, without the leading "#", in document order.

    Tags are case-sensitive, so #Python and #python are reported separately.
    """
    # Trailing separators are trimmed so that "#project/" reads as "project".
    return [tag.rstrip("/-") for tag in TAG_RE.findall(_strip_code(text))]


def _iter_dir(root: Path) -> Iterator[Path]:
    for found in sorted(root.rglob("*.md")):
        # Hidden files and directories are someone else's data: .git, .obsidian
        # and .venv all carry Markdown that the author never wrote as notes.
        # The check is relative to the root, so scanning a dotted path directly
        # still works.
        if any(part.startswith(".") for part in found.relative_to(root).parts):
            continue
        if found.is_file():
            yield found


def iter_markdown(path: Path | str) -> Iterator[Path]:
    """Return the Markdown files at `path`, recursing if it is a directory.

    A missing path raises immediately rather than on first iteration, which is
    why this is not itself a generator: a caller that builds the iterator and
    consumes it later should not have the error surface somewhere unrelated.
    """
    path = Path(path)
    if path.is_dir():
        return _iter_dir(path)
    if path.is_file():
        return iter((path,))
    raise FileNotFoundError(f"No such file or directory: {path}")


def count_tags(path: Path | str) -> Counter[str]:
    """Count each unique tag across every *.md file under `path`.

    Notes are decoded as UTF-8, tolerating a byte-order mark. Undecodable bytes
    are replaced instead of raising, so a single note in some other encoding
    degrades to losing that one tag rather than aborting the whole scan.
    """
    counts: Counter[str] = Counter()
    for note in iter_markdown(path):
        text = note.read_text(encoding="utf-8-sig", errors="replace")
        counts.update(extract_tags(text))
    return counts


def notes_tags(path: Path | str = ".", *, file: TextIO | None = None) -> Counter[str]:
    """Print each unique #tag under `path` with its count, sorted by tag.

    Returns the counts so callers can use them without re-scanning. `file`
    defaults to the current sys.stdout, resolved per call so that redirects
    are honoured.
    """
    file = sys.stdout if file is None else file
    counts = count_tags(path)
    if counts:
        width = max(len(tag) for tag in counts) + 1
        for tag, count in sorted(counts.items(), key=lambda kv: (kv[0].lower(), kv[0])):
            print(f"{'#' + tag:<{width}}  {count}", file=file)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="notes-tags",
        description="Count the #tags used across Markdown notes.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        type=Path,
        help="Markdown file, or directory to scan recursively (default: .)",
    )
    args = parser.parse_args(argv)
    try:
        notes_tags(args.path)
    except OSError as exc:  # FileNotFoundError and PermissionError included
        print(f"notes-tags: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
