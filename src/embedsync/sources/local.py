"""Source document providers."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SourceDocument:
    doc_id: str
    content: str
    metadata: dict[str, str]


class LocalFileSource:
    """Read documents from a local directory."""

    def __init__(self, directory: Path, glob: str = "**/*.md") -> None:
        self.directory = directory
        self.glob = glob

    def list_documents(self) -> list[SourceDocument]:
        docs: list[SourceDocument] = []
        for path in self.directory.glob(self.glob):
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.directory))
            docs.append(
                SourceDocument(
                    doc_id=rel,
                    content=path.read_text(encoding="utf-8"),
                    metadata={"path": rel},
                )
            )
        return docs
