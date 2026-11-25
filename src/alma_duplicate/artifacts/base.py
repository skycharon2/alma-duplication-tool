"""Small storage contract shared by publication and saved-report readers."""
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Mapping, Protocol


FILES = {'report': 'report.json', 'request': 'request.json', 'inspection': 'inspection.json',
         'view': 'view.json', 'queue-candidates': 'queue-candidates.jsonl'}
INPUT_FILES = {'source-list': 'source-list.bin', 'ot-pointings': 'ot-pointings.bin'}


@dataclass(frozen=True)
class Artifact:
    kind: str
    storage_key: str
    sha256: str
    byte_size: int
    stored_byte_size: int | None = None


class ArtifactStore(Protocol):
    def put_bundle(self, files: Mapping[str, Path]) -> list[Artifact]: ...
    def open_verified(self, artifact: Artifact) -> BinaryIO: ...
