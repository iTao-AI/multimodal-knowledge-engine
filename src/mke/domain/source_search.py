"""Selected active Source identity shared by scoped Search and its consumers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSearchScope:
    source_id: str
    publication_id: str
    publication_revision: int
    run_id: str
    content_fingerprint: str
