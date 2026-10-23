"""Member-bound product discovery records, independent of pointing extraction."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArchiveProduct:
    row_index: int
    member_ous_uid: str
    access_url: str | None
    service_def: str | None
    semantics: str
    description: str
    content_type: str
    content_length: int | None
    link_auth: str | None
    link_authorized: str | None
    kind: str
    issues: tuple[str, ...] = ()
    binding: str = 'DATALINK_ROW_MEMBER_ID'
    pointing_content: str = 'NOT_INSPECTED'
    asdm_binding: str = 'NOT_ESTABLISHED'


@dataclass(frozen=True, slots=True)
class ProductDiscovery:
    member_ous_uid: str
    requested_asdm_uid: str | None
    status: str
    products: tuple[ArchiveProduct, ...] = ()
    issues: tuple[str, ...] = ()
    response_sha256: str | None = None
    response_bytes: int = 0
    http_status: int | None = None
    method_version: str = 'archive_member_datalink_1'
    completeness: str = 'MEMBER_PRODUCT_INVENTORY_NOT_ESTABLISHED'
