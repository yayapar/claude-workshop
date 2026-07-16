"""Count the #tags used across a collection of Markdown notes."""

import argparse
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

__all__ = ["count_tags", "extract_tags", "iter_markdown", "notes_tags"]

# A tag must start the line or follow whitespace or an opening bracket, which
# rules out URL fragments (example.com#install). The body needs at least one
# letter or underscore, which rules out issue references (#123). A leading "# "
# is a heading, not a tag, and never matches because the body cannot start with
# a space.
TAG_RE = re.compile(
    r"""(?:(?<=[\s(\[{"'])|^)\#([A-Za-z0-9_/-]*[A-Za-z_][A-Za-z0-9_/-]*)""",
    re.MULTILINE,
)

FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`+[^`]*`+")


def _strip_code(text: str) -> str:
    """Blank out fenced code blocks and inline code spans.

    Code is replaced rather than deleted so that surrounding text cannot be
    joined together into a token that looks like a tag.
    """
    lines: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        if fence is None:
            match = FENCE_RE.match(line)
            if match:
                fence = match.group(1)[0]
                lines.append("")
            else:
                lines.append(INLINE_CODE_RE.sub(" ", line))
        else:
            lines.append("")
            if (match := FENCE_RE.match(line)) and match.group(1)[0] == fence:
                fence = None
    return "\n".join(lines)


def extract_tags(text: str) -> list[str]:
    """Return every tag in `text`, without the leading "#", in document order.

    Tags are case-sensitive, so #Python and #python are reported separately.
    """
    # Trailing separators are trimmed so that "#project/" reads as "project".
    return [tag.rstrip("/-") for tag in TAG_RE.findall(_strip_code(text))]


def iter_markdown(path: Path) -> Iterator[Path]:
    """Yield the Markdown files at `path`, recursing if it is a directory."""
    if path.is_dir():
        yield from sorted(p for p in path.rglob("*.md") if p.is_file())
    elif path.is_file():
        yield path
    else:
        raise FileNotFoundError(f"No such file or directory: {path}")


def count_tags(path: Path | str) -> Counter[str]:
    """Count each unique tag across every *.md file under `path`."""
    counts: Counter[str] = Counter()
    for note in iter_markdown(Path(path)):
        counts.update(extract_tags(note.read_text(encoding="utf-8")))
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
    except (FileNotFoundError, OSError) as exc:
        print(f"notes-tags: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
