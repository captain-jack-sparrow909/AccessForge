"""Minimal child-process entry point for the fixed CAD compiler contract."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Never

from accessforge.cad.compiler import compile_design_spec, write_compilation_result
from accessforge.cad.schemas import DesignSpec


def _disable_network() -> None:
    """Block Python-level sockets in the child as a defence-in-depth control."""

    def blocked(*_: object, **__: object) -> Never:
        raise RuntimeError("Network access is disabled in the AccessForge CAD compiler.")

    # These stdlib attributes are intentionally replaced only in the disposable
    # worker process. They do not share their original callable types, so the
    # narrowly scoped ignores document that deliberate defence-in-depth patch.
    socket.socket = blocked  # type: ignore[misc,assignment]
    socket.create_connection = blocked
    socket.getaddrinfo = blocked


def main(argv: list[str] | None = None) -> int:
    arguments = argv or sys.argv[1:]
    if len(arguments) != 2:
        return 2
    if os.environ.get("ACCESSFORGE_CAD_NO_NETWORK") == "1":
        _disable_network()
    input_path = Path(arguments[0]).resolve()
    output_directory = Path(arguments[1]).resolve()
    try:
        spec = DesignSpec.model_validate_json(input_path.read_text(encoding="utf-8"))
        result = compile_design_spec(spec, output_directory)
        write_compilation_result(result, output_directory)
    except Exception as exc:
        print(f"AccessForge CAD compilation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
