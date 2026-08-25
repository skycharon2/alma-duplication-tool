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
)

OBS_ID_PARSER_VERSION = "1"
OBS_ID_DECLARED_WIDTH = 64

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


def _failed_result(
    *,
    raw_value: str | bytes | float | None,
    normalized_value: str | None,
    obs_id_length: int | None,
    declared_width: int,
    confidence: ObsIdConfidence,
    failure_class: ObsIdFailureClass,
    issues: tuple[ObsIdIssue, ...],
) -> ObsIdParseResult:
    return ObsIdParseResult(
        raw_value=raw_value,
        normalized_value=normalized_value,
        member_ous_uid=None,
        source_name=None,
        spw_token=None,
        spw_index=None,
        obs_id_length=obs_id_length,
        declared_width=declared_width,
        at_declared_width=(
            obs_id_length == declared_width
            if obs_id_length is not None
            else False
        ),
        parse_status=ObsIdParseStatus.FAILED,
        confidence=confidence,
        failure_class=failure_class,
        issues=issues,
        parser_version=OBS_ID_PARSER_VERSION,
    )


def _classify_width_failure(
    text: str,
) -> tuple[ObsIdFailureClass, ObsIdIssue]:
    """Classify a failed value exactly at the declared width."""

    if text.endswith(".spw."):
        failure_class = (
            ObsIdFailureClass
            .TRUNCATED_AFTER_SPW_MARKER_AT_WIDTH
        )
        return (
            failure_class,
            _issue(
                failure_class.value.lower(),
                (
                    "obs_id ends immediately after the SPW "
                    "marker at the declared width."
                ),
                text,
            ),
        )

    if ".source." in text and ".spw." not in text:
        failure_class = (
            ObsIdFailureClass
            .TRUNCATED_IN_SOURCE_SEGMENT_AT_WIDTH
        )
        return (
            failure_class,
            _issue(
                failure_class.value.lower(),
                (
                    "obs_id reaches the declared width while "
                    "still inside the source segment."
                ),
                text,
            ),
        )

    if ".source." in text:
        failure_class = (
            ObsIdFailureClass
            .TRUNCATED_OTHER_SUFFIX_AT_WIDTH
        )
        return (
            failure_class,
            _issue(
                failure_class.value.lower(),
                (
                    "obs_id has a source marker but an "
                    "incomplete or unsafe suffix at the "
                    "declared width."
                ),
                text,
            ),
        )

    failure_class = (
        ObsIdFailureClass
        .WIDTH_LIMIT_WITHOUT_SOURCE_MARKER
    )
    return (
        failure_class,
        _issue(
            failure_class.value.lower(),
            (
                "obs_id reaches the declared width without "
                "a recognizable source marker."
            ),
            text,
        ),
    )


def parse_obs_id(
    raw_value: str | bytes | float | None,
    *,
    declared_width: int = OBS_ID_DECLARED_WIDTH,
) -> ObsIdParseResult:
    """Parse one Archive obs_id and attach width-risk evidence.

    Parsing is intentionally separate from cross-field validation.
    This function does not compare the parsed Member UID with the
    Archive member_ous_uid column and does not create a row key.
    """

    if declared_width <= 0:
        raise ValueError(
            "declared_width must be a positive integer"
        )

    normalized, is_missing = _normalize_obs_id(
        raw_value
    )

    if is_missing:
        return _failed_result(
            raw_value=raw_value,
            normalized_value=None,
            obs_id_length=None,
            declared_width=declared_width,
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
            declared_width=declared_width,
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

    # Values longer than the declared Archive width are outside
    # the currently observed service contract.
    if obs_id_length > declared_width:
        return _failed_result(
            raw_value=raw_value,
            normalized_value=normalized,
            obs_id_length=obs_id_length,
            declared_width=declared_width,
            confidence=ObsIdConfidence.FAILED_OTHER,
            failure_class=(
                ObsIdFailureClass
                .NON_WIDTH_GRAMMAR_EXCEPTION
            ),
            issues=(
                _issue(
                    "obs_id_exceeds_declared_width",
                    (
                        "obs_id exceeds the configured "
                        "declared width."
                    ),
                    normalized,
                ),
            ),
        )

    match = OBS_ID_PATTERN.fullmatch(normalized)

    if match is not None:
        member_ous_uid = match.group(
            "member_ous_uid"
        )
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
            if obs_id_length == declared_width:
                confidence = (
                    ObsIdConfidence
                    .PARSED_AT_DECLARED_WIDTH_TRUNCATION_POSSIBLE
                )
                issues = (
                    _issue(
                        (
                            "parsed_at_declared_width_"
                            "truncation_possible"
                        ),
                        (
                            "obs_id satisfies the visible "
                            "grammar exactly at the declared "
                            "width; an unseen suffix may have "
                            "been truncated."
                        ),
                        normalized,
                    ),
                )
            else:
                confidence = (
                    ObsIdConfidence
                    .PARSED_BELOW_DECLARED_WIDTH
                )
                issues = ()

            return ObsIdParseResult(
                raw_value=raw_value,
                normalized_value=normalized,
                member_ous_uid=member_ous_uid,
                source_name=source_name,
                spw_token=spw_token,
                spw_index=int(spw_token),
                obs_id_length=obs_id_length,
                declared_width=declared_width,
                at_declared_width=(
                    obs_id_length == declared_width
                ),
                parse_status=ObsIdParseStatus.PARSED,
                confidence=confidence,
                failure_class=None,
                issues=issues,
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

    if obs_id_length == declared_width:
        failure_class, width_issue = (
            _classify_width_failure(normalized)
        )

        return _failed_result(
            raw_value=raw_value,
            normalized_value=normalized,
            obs_id_length=obs_id_length,
            declared_width=declared_width,
            confidence=(
                ObsIdConfidence
                .FAILED_AT_DECLARED_WIDTH_TRUNCATION_LIKELY
            ),
            failure_class=failure_class,
            issues=base_issues + (width_issue,),
        )

    return _failed_result(
        raw_value=raw_value,
        normalized_value=normalized,
        obs_id_length=obs_id_length,
        declared_width=declared_width,
        confidence=ObsIdConfidence.FAILED_OTHER,
        failure_class=(
            ObsIdFailureClass
            .NON_WIDTH_GRAMMAR_EXCEPTION
        ),
        issues=base_issues,
    )