"""Build independent Single Pointing documents without source access."""
from copy import deepcopy

from alma_duplicate.parsers.source_list import parse_source_list
from alma_duplicate.separated_setup_input import (
    SEPARATED_INPUT_CONTRACT, SEPARATED_OBSERVATION_CONTRACT,
)


def build_batch_requests(shared_document, source_bytes, *, format='csv'):
    """Expand shared wire input using a validated, bounded source-list upload.

    Return ordered source metadata and detached documents. Scientific readiness
    is validated separately using the same controller as standalone input.
    Uploaded redshift owns every source-dependent frequency in each child.
    """
    preview = parse_source_list(source_bytes, format=format)
    if not preview['is_valid']:
        raise ValueError('Correct all source-list row errors before building requests')
    if not isinstance(shared_document, dict) or not isinstance(shared_document.get('request'), dict):
        raise ValueError('Expected a request document')
    request = shared_document['request']
    if (request.get('target_kind', 'FIXED') != 'FIXED' or
            request.get('geometry', 'SINGLE_POINTING') != 'SINGLE_POINTING'):
        raise ValueError('Batch requests require fixed Single Pointing inputs')
    contract = request.get('line_input_contract')
    if contract is not None and contract not in {
            SEPARATED_INPUT_CONTRACT, SEPARATED_OBSERVATION_CONTRACT}:
        raise ValueError('Unsupported scientific input contract')
    if not isinstance(shared_document.get('search_options'), dict):
        raise ValueError('Expected search_options')
    children = []
    for source in preview['sources']:
        document = deepcopy(shared_document)
        child = document['request']
        original = source['original']
        child.update(target_kind='FIXED', geometry='SINGLE_POINTING', target_name=source['name'],
                     position=dict(ra=original['ra'], dec=original['dec'], frame='ICRS',
                                   ra_format='HMS' if ':' in original['ra'] else 'DEG',
                                   dec_format='DMS' if ':' in original['dec'] else 'DEG'))
        child.pop('source_redshift', None)
        if source['redshift'] is not None:
            child['source_redshift'] = source['redshift']
        if contract is not None:
            requirements = child.get('line_requirements', [])
            if not isinstance(requirements, list) or any(not isinstance(r, dict) for r in requirements):
                raise ValueError('Expected a list of LINE requirements')
            for requirement in requirements:
                requirement.pop('source_redshift', None)
            continuum = child.get('continuum_requirement')
            if continuum is not None:
                if not isinstance(continuum, dict):
                    raise ValueError('Expected a continuum requirement object')
                continuum.pop('source_redshift', None)
        children.append(dict(source=source, document=document))
    return dict(schema_version='batch_requests_1', input_sha256=preview['input_sha256'],
                sources=children)
