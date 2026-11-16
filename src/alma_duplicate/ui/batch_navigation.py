"""Read-only navigation over saved batch identity and availability."""
PURPOSE_LABELS = {'LINE': 'Spectral line', 'CONTINUUM': 'Continuum'}


def navigation_context(manifest, source_id, purpose, *, visual=False):
    """Keep upload order and purpose; never substitute an available sibling check."""
    sources = manifest['sources']
    index = next((i for i, source in enumerate(sources) if source['source_id'] == source_id), None)
    if index is None:
        return None

    def destination(source, selected_purpose):
        report = next((r for r in source['reports'] if r['purpose'] == selected_purpose), None)
        available = report is not None and report['availability'] == 'AVAILABLE'
        status = (report['availability'] if report['state'] == 'COMPLETED' else report['state']) if report else 'NOT_REQUESTED'
        return dict(source_id=source['source_id'], name=source['source']['name'],
                    purpose=selected_purpose, label=PURPOSE_LABELS.get(selected_purpose, selected_purpose),
                    run_id=report['run_id'] if available else None, status=status,
                    endpoint='run_visualization' if visual else 'run_view')

    current = sources[index]
    return dict(batch_id=manifest['batch_id'], source_id=source_id, name=current['source']['name'],
                position=index + 1, total=len(sources), purpose=purpose, visual=visual,
                current=destination(current, purpose),
                previous=destination(sources[index - 1], purpose) if index else None,
                next=destination(sources[index + 1], purpose) if index + 1 < len(sources) else None,
                purposes=[destination(current, report['purpose']) for report in current['reports']])
