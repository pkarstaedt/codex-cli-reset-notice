#!/usr/bin/env python3
"""Build an allowlisted release ZIP and checksum without user data or caches."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = [".codex-plugin/plugin.json", ".agents/plugins/marketplace.json", "hooks/hooks.json",
         "codex_reset.py", "install.py", "test_codex_reset.py", "build_release.py",
         "verify_plugin.py", "README.md", "LICENSE", ".gitignore"]


def build():
    manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    name, version = manifest["name"], manifest["version"]
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    archive = destination / f"{name}-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for item in FILES:
            path = ROOT / item
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Missing or unsafe release file: {item}")
            entry = zipfile.ZipInfo(f"{name}/{item}")
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            output.writestr(entry, path.read_bytes())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{checksum}  {archive.name}\n")
    print(archive)
    return archive


if __name__ == "__main__":
    build()
