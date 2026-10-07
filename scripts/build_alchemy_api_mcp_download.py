"""Build the user-downloadable, source-aligned Alchemy HTTP MCP bundle."""
from __future__ import annotations

from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "services" / "alchemy_codex_local_adapter"
OUTPUT = ROOT / "src_skeleton" / "app" / "static" / "downloads" / "alchemy-api-mcp-v1.zip"
PUBLIC_GUIDE = OUTPUT.parent / "ALCHEMY_MCP_INSTALL.md"
PACKAGE = "alchemy_api_mcp"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = {
        f"{PACKAGE}/__init__.py": b'"""Alchemy API MCP download package."""\n',
        f"{PACKAGE}/server.py": (ADAPTER / "standalone_api_mcp.py").read_bytes(),
        f"{PACKAGE}/product_tools.py": (ADAPTER / "product_tools.py").read_bytes(),
        f"{PACKAGE}/versioned_tools.py": (ADAPTER / "versioned_tools.py").read_bytes(),
        "README.md": (ROOT / "docs" / "ALCHEMY_MCP_INSTALL.md").read_bytes(),
    }
    guide = files["README.md"]
    PUBLIC_GUIDE.write_bytes(guide)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    print(f"Built {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
