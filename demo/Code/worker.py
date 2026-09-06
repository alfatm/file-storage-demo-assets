"""Extract searchable text for Cloud demo uploads."""

import json
import logging
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

log = logging.getLogger("worker")
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    return " ".join(node.text or "" for node in root.iter(WORD_NS + "t"))


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx(path)
    if suffix in {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".html", ".ts", ".py"}:
        return path.read_text(encoding="utf-8", errors="replace")
    log.info("no extractor for %s", suffix)
    return ""


def process(payload: dict[str, str]) -> dict[str, str | int]:
    source = Path(payload["path"]).resolve()
    text = extract_text(source)
    return {"path": str(source), "chars": len(text), "text": text[:200_000]}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    payload = json.load(sys.stdin)
    json.dump(process(payload), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
