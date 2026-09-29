"""Identify Python comments without treating strings or executable code as tags."""

import io
import tokenize

from .common import CheckError


def comment_lines(content, path):
    """Return a line-preserving UTF-8 import view and genuine comment line numbers."""
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(content).readline)
        source = content.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
        lines = io.StringIO(source).readlines()
        view = ["\n" if line.endswith(("\n", "\r")) else "" for line in lines]
        comments = set()
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                row, column = token.start
                view[row - 1] = " " * column + token.string + view[row - 1]
                comments.add(row)
    except (SyntaxError, UnicodeError, tokenize.TokenError) as exc:
        raise CheckError(f"Cannot tokenize Python annotations in {path}: {exc}") from exc
    return "".join(view).encode("utf-8"), comments
