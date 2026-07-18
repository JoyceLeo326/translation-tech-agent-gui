from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path, PurePosixPath


def _extended_path(path: Path) -> str:
    value = str(path.resolve())
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def package_release(source: Path, output: Path) -> tuple[int, int]:
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Release directory not found: {source}")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    source_extended = _extended_path(source)
    file_count = 0
    byte_count = 0
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for directory, _, filenames in os.walk(source_extended):
            for filename in filenames:
                full_path = os.path.join(directory, filename)
                relative = os.path.relpath(full_path, source_extended)
                archive_name = (PurePosixPath(source.name) / PurePosixPath(relative.replace("\\", "/"))).as_posix()
                archive.write(full_path, archive_name)
                file_count += 1
                byte_count += os.stat(full_path).st_size

    with zipfile.ZipFile(output) as archive:
        corrupt_member = archive.testzip()
        if corrupt_member:
            raise RuntimeError(f"Corrupt ZIP member: {corrupt_member}")
        archived_files = sum(1 for item in archive.infolist() if not item.is_dir())
    if archived_files != file_count:
        raise RuntimeError(f"ZIP file count mismatch: expected {file_count}, got {archived_files}")
    return file_count, byte_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a UTF-8, long-path-safe Windows release archive.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    file_count, byte_count = package_release(args.source, args.output)
    print(f"Release archive ready: {args.output.resolve()}")
    print(f"Files: {file_count}")
    print(f"Uncompressed bytes: {byte_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
