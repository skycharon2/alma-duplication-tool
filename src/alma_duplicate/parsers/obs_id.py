"""Parse ALMA Archive obs_id values without reconstructing rows."""

from __future__ import annotations

import math
import re

from alma_duplicate.domain.archive import (
    ObsIdConfidence,
    ObsIdFailureClass,
    ObsIdIssue,
    ObsIdParseResult,
    ObsIdParseStatus,
    ObsIdWidthContract,
    ObsIdWidthMetadataStatus,
    ObsIdWidthStatus,
    unavailable_obs_id_width_contract,
)

OBS_ID_PARSER_VERSION = "3"

OBS_ID_PATTERN = re.compile(
    r"^(?P<member_ous_uid>uid://.+?)"
    r"\.source\."
    r"(?P<source_name>.+)"
    r"\.spw\."
    r"(?P<spw_token>[^.]+)$"
)


def _issue(
    code: str,
    message: str,
    token: str | None = None,
) -> ObsIdIssue:
    return ObsIdIssue(
        code=code,
        message=message,
        token=token,
    )


def _is_float_nan(value: object) -> bool:
    return (
        isinstance(value, float)
        and math.isnan(value)
    )


def _normalize_obs_id(
    value: str | bytes | float | None,
) -> tuple[str | None, bool]:
    """Return normalized text and whether the value is missing."""

    if value is None or _is_float_nan(value):
        return None, True

    if isinstance(value, bytes):
        text = value.decode(
            "utf-8",
            errors="replace",
        ).strip()
    else:
        text = str(value).strip()

    return text, False


def _width_status(
    obs_id_length: int | None,
    contract: ObsIdWidthContract,
) -> ObsIdWidthStatus:
    """Compare length only with usable live response metadata."""

    if obs_id_length is None:
        return ObsIdWidthStatus.NOT_EVALUABLE

    if (
        contract.metadata_status
        is ObsIdWidthMetadataStatus.UNBOUNDED
    ):
        return ObsIdWidthStatus.WITHIN_UNBOUNDED

    maximum = contract.reported_max_length
    if maximum is None:
        return ObsIdWidthStatus.NOT_EVALUABLE
    if obs_id_length < maximum:
        return ObsIdWidthStatus.BELOW_REPORTED_MAXIMUM
    if obs_id_length == maximum:
        return ObsIdWidthStatus.AT_REPORTED_MAXIMUM
    return (
        ObsIdWidthStatus
        .ABOVE_REPORTED_MAXIMUM_SCHEMA_DRIFT
    )


def _width_issues(
    *,
    normalized_value: str | None,
    width_status: ObsIdWidthStatus,
) -> tuple[ObsIdIssue, ...]:
    if width_status is not (
        ObsIdWidthStatus
        .ABOVE_REPORTED_MAXIMUM_SCHEMA_DRIFT
    ):
        return ()

    return (
        _issue(
            "obs_id_above_reported_maximum_schema_drift",
            (
                "obs_id exceeds the maximum length reported by the "
                "response VOTable FIELD descriptor."
            ),
            normalized_value,
        ),
    )


def _failed_result(
    *,
    raw_value: str | bytes | float | None,
    normalized_value: str | None,
    obs_id_length: int | None,
    width_contract: ObsIdWidthContract,
    confidence: ObsIdConfidence,
    failure_class: ObsIdFailureClass,
    issues: tuple[ObsIdIssue, ...],
) -> ObsIdParseResult:
    width_status = _width_status(
        obs_id_length,
        width_contract,
    )
    return ObsIdParseResult(
        raw_value=raw_value,
        normalized_value=normalized_value,
        member_ous_uid=None,
        source_name=None,
        spw_token=None,
        spw_index=None,
        obs_id_length=obs_id_length,
        width_contract=width_contract,
        width_status=width_status,
        at_historical_truncation_boundary=(
            obs_id_length
            == width_contract.historical_truncation_boundary
            if obs_id_length is not None
            else False
        ),
        parse_status=ObsIdParseStatus.FAILED,
        confidence=confidence,
        failure_class=failure_class,
        issues=issues
        + _width_issues(
            normalized_value=normalized_value,
            width_status=width_status,
        ),
        parser_version=OBS_ID_PARSER_VERSION,
    )


def _classify_historical_boundary_failure(
    text: str,
) -> tuple[ObsIdFailureClass, ObsIdIssue]:
    """Classify failed grammar at the observed truncation boundary."""

    if text.endswith(".spw."):
        failure_class = (
            ObsIdFailureClass
            .TRUNCATED_AFTER_SPW_MARKER_AT_HISTORICAL_BOUNDARY
        )
        return (
            failure_class,
            _issue(
                failure_class.value.lower(),
                (
                    "obs_id ends immediately after the SPW marker at "
                    "the historical truncation boundary."
                ),
                text,
            ),
        )

    if ".source." in text and ".spw." not in text:
        failure_class = (
            ObsIdFailureClass
            .TRUNCATED_IN_SOURCE_SEGMENT_AT_HISTORICAL_BOUNDARY
        )
        return (
            failure_class,
            _issue(
                failure_class.value.lower(),
                (
                    "obs_id reaches the historical truncation boundary "
                    "while still inside the source segment."
                ),
                text,
            ),
        )

    if ".source." in text:
        failure_class = (
            ObsIdFailureClass
            .TRUNCATED_OTHER_SUFFIX_AT_HISTORICAL_BOUNDARY
        )
        return (
            failure_class,
            _issue(
                failure_class.value.lower(),
                (
                    "obs_id has a source marker but an incomplete or "
                    "unsafe suffix at the historical truncation boundary."
                ),
                text,
            ),
        )

    failure_class = (
        ObsIdFailureClass
        .HISTORICAL_BOUNDARY_WITHOUT_SOURCE_MARKER
    )
    return (
        failure_class,
        _issue(
            failure_class.value.lower(),
            (
                "obs_id reaches the historical truncation boundary "
                "without a recognizable source marker."
            ),
            text,
        ),
    )


def parse_obs_id(
    raw_value: str | bytes | float | None,
    *,
    width_contract: ObsIdWidthContract | None = None,
) -> ObsIdParseResult:
    """Parse one Archive obs_id and attach independent width evidence.

    Parsing is intentionally separate from cross-field validation. This
    function does not compare the parsed Member UID with the Archive
    member_ous_uid column and does not create a row key.
    """

    effective_contract = (
        width_contract
        if width_contract is not None
        else unavailable_obs_id_width_contract()
    )
    normalized, is_missing = _normalize_obs_id(raw_value)

    if is_missing:
        return _failed_result(
            raw_value=raw_value,
            normalized_value=None,
            obs_id_length=None,
            width_contract=effective_contract,
            confidence=ObsIdConfidence.FAILED_OTHER,
            failure_class=ObsIdFailureClass.MISSING,
            issues=(
                _issue(
                    "missing_obs_id",
                    "obs_id is missing.",
                ),
            ),
        )

    assert normalized is not None

    if not normalized:
        return _failed_result(
            raw_value=raw_value,
            normalized_value=None,
            obs_id_length=0,
            width_contract=effective_contract,
            confidence=ObsIdConfidence.FAILED_OTHER,
            failure_class=ObsIdFailureClass.BLANK,
            issues=(
                _issue(
                    "blank_obs_id",
                    "obs_id is blank.",
                ),
            ),
        )

    obs_id_length = len(normalized)
    at_historical_boundary = (
        obs_id_length
        == effective_contract.historical_truncation_boundary
    )
    width_status = _width_status(
        obs_id_length,
        effective_contract,
    )
    match = OBS_ID_PATTERN.fullmatch(normalized)

    if match is not None:
        member_ous_uid = match.group("member_ous_uid")
        source_name = match.group("source_name")
        spw_token = match.group("spw_token")

        structural_issues: list[ObsIdIssue] = []

        if not source_name.strip():
            structural_issues.append(
                _issue(
                    "source_name_blank",
                    (
                        "Parsed source segment contains "
                        "only whitespace."
                    ),
                    source_name,
                )
            )

        if not spw_token.isdigit():
            structural_issues.append(
                _issue(
                    "spw_token_not_integer",
                    (
                        "Parsed SPW token is not an "
                        "unsigned integer."
                    ),
                    spw_token,
                )
            )

        if not structural_issues:
            if at_historical_boundary:
                confidence = (
                    ObsIdConfidence
                    .PARSED_AT_HISTORICAL_TRUNCATION_BOUNDARY
                )
                historical_issues = (
                    _issue(
                        (
                            "parsed_at_historical_"
                            "truncation_boundary"
                        ),
                        (
                            "obs_id satisfies the visible grammar exactly "
                            "at the historically observed truncation "
                            "boundary; an unseen suffix may be missing."
                        ),
                        normalized,
                    ),
                )
            else:
                confidence = ObsIdConfidence.PARSED_COMPLETE
                historical_issues = ()

            return ObsIdParseResult(
                raw_value=raw_value,
                normalized_value=normalized,
                member_ous_uid=member_ous_uid,
                source_name=source_name,
                spw_token=spw_token,
                spw_index=int(spw_token),
                obs_id_length=obs_id_length,
                width_contract=effective_contract,
                width_status=width_status,
                at_historical_truncation_boundary=(
                    at_historical_boundary
                ),
                parse_status=ObsIdParseStatus.PARSED,
                confidence=confidence,
                failure_class=None,
                issues=historical_issues
                + _width_issues(
                    normalized_value=normalized,
                    width_status=width_status,
                ),
                parser_version=OBS_ID_PARSER_VERSION,
            )

        base_issues = tuple(structural_issues)
    else:
        base_issues = (
            _issue(
                "unexpected_obs_id_format",
                (
                    "obs_id does not match the expected "
                    "Member.source.Source.spw.SPW grammar."
                ),
                normalized,
            ),
        )

    if at_historical_boundary:
        failure_class, boundary_issue = (
            _classify_historical_boundary_failure(
                normalized
            )
        )
        return _failed_result(
            raw_value=raw_value,
            normalized_value=normalized,
            obs_id_length=obs_id_length,
            width_contract=effective_contract,
            confidence=(
                ObsIdConfidence
                .FAILED_AT_HISTORICAL_TRUNCATION_BOUNDARY
            ),
            failure_class=failure_class,
            issues=base_issues + (boundary_issue,),
        )

    return _failed_result(
        raw_value=raw_value,
        normalized_value=normalized,
        obs_id_length=obs_id_length,
        width_contract=effective_contract,
        confidence=ObsIdConfidence.FAILED_OTHER,
        failure_class=(
            ObsIdFailureClass
            .NON_BOUNDARY_GRAMMAR_EXCEPTION
        ),
        issues=base_issues,
    )
