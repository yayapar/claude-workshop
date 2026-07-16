# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

This project is managed entirely with **uv** (not pip/venv). Python 3.14 is pinned via `.python-version` and provided by uv's standalone build. All Python invocation should go through `uv run`.

## Structure

- The `app` package is installed in editable mode, so tests import it as `import app`, not by relative path.
