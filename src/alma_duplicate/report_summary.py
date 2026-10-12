"""Read shared nonmatching criterion summaries without evaluating science."""


def criterion_record(value, document):
    """Resolve a v6 summary reference; legacy/full criteria remain inline."""
    if isinstance(value, dict):
        return value
    table = document.get('summary_criteria')
    if (document.get('report_version') != '6' or type(value) is not int
            or not isinstance(table, list) or not 0 <= value < len(table)
            or not isinstance(table[value], dict)):
        raise ValueError('Invalid shared criterion summary reference')
    return table[value]


def resolve_context_summary(context, document):
    """Resolve one displayed page, sharing immutable records instead of copying them."""
    if document.get('report_version') != '6' or context.get('detail_level') != 'SUMMARY':
        return context

    def scope(value):
        result = dict(value)
        result['criteria'] = [criterion_record(r, document) for r in value['criteria']]
        result['line_pairs'] = [dict(pair, criteria=[criterion_record(r, document)
                                                   for r in pair['criteria']])
                                for pair in value['line_pairs']]
        if value.get('beam_variants'):
            result['beam_variants'] = [scope(v) for v in value['beam_variants']]
        return result

    return scope(context)
