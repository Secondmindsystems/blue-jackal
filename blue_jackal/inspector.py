"""Read bounded local evidence for presentation; never change a receipt."""
import difflib
import hashlib
import json
from .contract import ContractError, beneath, digest
from .runner import find_record


def _text(base, name, expected):
    if expected is None:
        return None, 'Not present in recorded snapshot'
    try:
        path = beneath(base, name)
        if path.stat().st_size > 65536:
            return None, 'File exceeds 64 KiB display limit'
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            return None, 'Unavailable: current bytes do not match recorded hash'
        value = data.decode('utf-8')
        if '\x00' in value:
            return None, 'Binary content is not displayed'
        return value, 'Verified against recorded SHA-256'
    except (OSError, ValueError, ContractError):
        return None, 'Unavailable: file missing, unsafe or not UTF-8'


def collect(root, record):
    """Enrichment is local-only and deliberately absent from exported reports."""
    ids = record.get('run_ids', []) if record.get('type') == 'matrix' else [record.get('id')]
    result = {}
    for ident in ids[:32]:
        try:
            folder, run = find_record(root, ident)
            if run.get('id') != ident or run.get('type') != 'run':
                raise ValueError('Not an exact run identity')
            for key in ('contract_sha256', 'engine_sha256', 'seed_sha256', 'oracle_sha256'):
                if key in record and record[key] != run.get(key):
                    raise ValueError('Linked run does not match parent evidence')
            files = []
            for name in run.get('changes', [])[:20]:
                before, bs = _text(folder/'seed', name, run.get('initial_state', {}).get(name))
                after, ats = _text(folder/'workspace', name, run.get('final_state', {}).get(name))
                difference = None
                if (before is not None or name not in run.get('initial_state', {})) and (after is not None or name not in run.get('final_state', {})):
                    difference = ''.join(difflib.unified_diff((before or '').splitlines(True), (after or '').splitlines(True), fromfile='Before', tofile='After'))
                files.append(dict(path=name, before=before, after=after, before_status=bs, after_status=ats, diff=difference))
            task = None
            try:
                source = beneath(folder.parent, run['source_folder'])
                frozen_path = beneath(source, 'frozen.json')
                if frozen_path.stat().st_size <= 262144:
                    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
                    if digest(frozen['contract']) == run['contract_sha256']:
                        task = frozen['contract']['task']['prompt']
            except (OSError, ValueError, KeyError, ContractError):
                pass
            result[ident] = dict(run=run, files=files, task=task,
                                 note='Showing at most 20 changed files, 64 KiB per file. Missing original bytes are not reconstructed.')
        except (OSError, ValueError, KeyError, ContractError) as exc:
            result[ident] = dict(error='Linked evidence unavailable: '+str(exc))
    return result


def write(root, folder, record):
    from .report import html_report
    (folder/'report.html').write_text(html_report(record, inspection=collect(root, record)), encoding='utf-8')
