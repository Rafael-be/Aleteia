"""Select decision-relevant documents; keep the complete inventory in the audit."""
from urllib.parse import urlsplit, parse_qsl, urlencode


def source_key(url):
    p = urlsplit(url)
    query = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                   if not k.lower().startswith('utm_') and k.lower() not in
                   {'fbclid', 'gclid', 'msclkid', 'mc_cid', 'mc_eid'})
    return (p.hostname or '').lower().removeprefix('www.') + (p.path.rstrip('/') or '/') + '?' + urlencode(query)


def source_label(document):
    title = ' '.join(str(document.get('title') or '').split())
    for separator in ('|', ' - ', ' — ', ' – '):
        if separator in title and 2 <= len(title.rsplit(separator, 1)[1].strip()) <= 50:
            return title.rsplit(separator, 1)[1].strip()
    return (title[:87]+'…' if len(title) > 90 else title) or urlsplit(document['final_url']).hostname.removeprefix('www.')


def select_sources(claims, results, evidence, documents):
    docs = {d['id']: d for d in documents}
    chosen, keys, queues = [], set(), []
    for claim, result in zip(claims, results):
        scored = set(result.get('scoring_source_ids', []))
        candidates = [e for e in evidence if e['claim_id'] == claim.id and e['source_id'] in docs
                      and e.get('contribution', 'decision') != 'incidental'
                      and (e.get('decision_scope', 'applicable') != 'different_context'
                           or e.get('contribution') == 'explanation')]
        candidates.sort(key=lambda e: (e['source_id'] not in scored,
            e.get('retrieval_kind') == 'provider_excerpt', -(e.get('relevance') or 0),
            -(e.get('source_quality') or 0), -abs(e['stance'])))
        groups, selected = set(), []
        # Preserve the best source on each side before filling other origins.
        for sign in (1, -1):
            e = next((e for e in candidates if e['stance']*sign > 0), None)
            if e:
                selected.append(e)
                groups.add((e.get('group'), sign))
        for e in candidates:
            group = (e.get('group', e['source_id']), 1 if e['stance'] > 0 else -1 if e['stance'] < 0 else 0)
            if e not in selected and group not in groups:
                selected.append(e); groups.add(group)
        queues.append(selected[:4 if any(e['stance'] for e in candidates) else 2])
    # Every claim gets its most important source before one claim fills the
    # shared display budget with additional references.
    for rank in range(4):
        for queue in queues:
            if rank >= len(queue):
                continue
            e = queue[rank]
            key = source_key(docs[e['source_id']]['final_url'])
            if key not in keys:
                keys.add(key); chosen.append(e['source_id'])
    return chosen[:12]
