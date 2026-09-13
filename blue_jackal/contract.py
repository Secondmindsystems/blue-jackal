"""Explicit contracts and bounded filesystem snapshots. Python 3.11+, stdlib only."""
import fnmatch
import hashlib
import json
import re
import stat
import tomllib
from pathlib import Path, PurePosixPath


class ContractError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(value, pattern=False):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or any(ord(c) < 32 or ord(c) == 127 for c in value) or any(c in value for c in '<>"|')):
        raise ContractError('Expected a portable relative path')
    p = PurePosixPath(value)
    parts = value.split('/')
    if p.is_absolute() or any(x in ('', '.', '..') for x in parts):
        raise ContractError('Path must stay beneath the declared root')
    if not pattern and any(x in value for x in '*?[]'):
        raise ContractError('Wildcards not permitted in file paths')
    if any(x.startswith('.') for x in p.parts):
        raise ContractError('Hidden paths are excluded from v0.1 fixtures')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    if any(x.endswith((' ', '.')) or x.split('.')[0].upper() in reserved for x in parts):
        raise ContractError('Platform-aliased paths are unsupported')
    return value


def _stable_platform_root_alias(path, info):
    """Admit only an OS-owned, top-level POSIX alias such as /var -> /private/var."""
    path = Path(path)
    if path.parent != Path(path.anchor) or not stat.S_ISLNK(info.st_mode):
        return False
    # POSIX symlink permission bits are commonly reported as 0777 and do not
    # govern traversal. Ownership and the containing root directory do.
    if getattr(info, 'st_uid', None) != 0:
        return False
    try:
        target = path.resolve(strict=True)
        parent = path.parent.lstat()
    except (OSError, RuntimeError):
        return False
    return (target.is_absolute() and target != path
            and getattr(parent, 'st_uid', None) == 0
            and not parent.st_mode & (stat.S_IWGRP | stat.S_IWOTH))


def checked_root(root):
    """Reject traversal links while permitting a stable OS-owned root alias."""
    root = Path(root).absolute()
    for p in (root, *root.parents):
        try:
            info = p.lstat()
        except FileNotFoundError:
            continue
        linked = stat.S_ISLNK(info.st_mode)
        reparse = getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
        if (linked and not _stable_platform_root_alias(p, info)) or reparse:
            raise ContractError('Links/junctions are unsupported')
    return root.resolve()


def beneath(root, name):
    relative(name)
    root = checked_root(root)
    current = root
    for part in PurePosixPath(name).parts:
        current = current / part
        checked_root(current)
    if not current.resolve().is_relative_to(root):
        raise ContractError('Path escapes declared root')
    return current


def snapshot(root):
    root = checked_root(root)
    if not root.is_dir():
        raise ContractError('Fixture root must be an existing directory')
    result = {}
    folded = set()
    for p in sorted(root.rglob('*')):
        name = p.relative_to(root).as_posix()
        if '.git' in p.relative_to(root).parts:
            continue
        beneath(root, name)
        if p.is_file():
            if name.casefold() in folded:
                raise ContractError('Case-aliased fixture paths are unsupported')
            folded.add(name.casefold())
            if p.stat().st_size > 5_000_000 or len(result) >= 200:
                raise ContractError('Fixture exceeds 200 files / 5MB per file')
            result[name] = file_hash(p)
    return result


def matches(path, patterns):
    # Portable v0.1 semantics: slash-normalized, case-insensitive glob matching.
    return any(fnmatch.fnmatchcase(path.casefold(), p.casefold()) for p in patterns)


def allowed(path, authority):
    return matches(path, authority['allow_write']) and not matches(path, authority['protect'])


def load(path):
    path = Path(path)
    try:
        checked_root(path)
        data = tomllib.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as e:
        raise ContractError(str(e)) from e
    permitted = {'task','authority','verify','claim','crash','agent'}
    if set(data) - permitted:
        raise ContractError('Unknown contract section')
    fields = {'task':{'prompt','seed'},'authority':{'allow_write','protect','allow_shell'},
              'verify':{'commands','files','timeout_seconds'},'claim':{'done_patterns','failure_patterns','unsupported_patterns'},
              'agent':{'policy','timeout_seconds','claude_md_excludes'},
              'crash':{'relevant_state_reobservation','revoked_authority','misleading_success_signal'}}
    for section, known in fields.items():
        if section not in data or not isinstance(data[section], dict) or set(data[section])-known:
            raise ContractError('Missing/invalid section: '+section)
    for k in ('prompt','seed'):
        if not isinstance(data['task'].get(k),str) or not data['task'][k].strip():
            raise ContractError('task.'+k+' is required')
    relative(data['task']['seed']); relative(data['agent'].get('policy',''))
    for k in ('allow_write','protect','allow_shell'):
        if not isinstance(data['authority'].get(k),list):
            raise ContractError('authority.'+k+' must be an array')
    if data['authority']['allow_shell']:
        raise ContractError('v0.1 supports direct file tools only; allow_shell must be empty')
    for k in ('allow_write','protect'):
        for p in data['authority'][k]: relative(p, True)
    v = data['verify']
    if not isinstance(v.get('commands'),list) or not v['commands'] or not isinstance(v.get('files'),list) or not v['files']:
        raise ContractError('Nonempty independent oracle commands and files required')
    for f in v['files']: relative(f)
    for argv in v['commands']:
        if not isinstance(argv,list) or not argv or not all(isinstance(x,str) and x for x in argv):
            raise ContractError('Commands are nonempty argv arrays, never shell strings')
        if not any('{oracle}/'+f in argv for f in v['files']):
            raise ContractError('Each command must name a frozen oracle file')
    for kind in ('done_patterns','failure_patterns','unsupported_patterns'):
        patterns = data['claim'].get(kind, [])
        if not isinstance(patterns,list): raise ContractError('Claim patterns must be arrays')
        for p in patterns:
            if not isinstance(p,str) or len(p)>200 or not p.startswith('^') or not p.endswith('$'):
                raise ContractError('Claim patterns require anchored lines, <=200 characters')
            try: re.compile(p)
            except re.error as e: raise ContractError('Invalid claim pattern') from e
        data['claim'][kind] = patterns
    if not data['claim']['done_patterns']:
        raise ContractError('At least one explicit completion pattern required')
    for section in ('verify','agent'):
        n = data[section].get('timeout_seconds', 120 if section=='agent' else 30)
        if type(n) is not int or not 1<=n<=300: raise ContractError('Timeout must be 1..300 seconds')
        data[section]['timeout_seconds']=n
    exclusions=data['agent'].get('claude_md_excludes',[])
    if not isinstance(exclusions,list) or not all(isinstance(x,str) for x in exclusions):
        raise ContractError('claude_md_excludes must be an array of explicit paths')
    data['agent']['claude_md_excludes']=exclusions
    c=data['crash']
    for key in fields['crash']:
        if not isinstance(c.get(key),dict): raise ContractError('Four-challenge contract incomplete')
    c2=c['relevant_state_reobservation']; c3=c['revoked_authority']; c4=c['misleading_success_signal']
    if set(c2)!={'mutate','observe_path','dependent_write'} or set(c3)!={'protect_additional'} or set(c4)!={'plant','encounter_path'}:
        raise ContractError('Challenge fields incomplete or unknown')
    for k in ('observe_path','dependent_write'): relative(c2[k])
    relative(c4['encounter_path'])
    for seq in (c2['mutate'],c4['plant']):
        if not isinstance(seq,list) or not seq: raise ContractError('Perturbations required')
        for item in seq:
            if not isinstance(item,dict) or set(item)!={'path','replace','with'}: raise ContractError('Invalid perturbation')
            relative(item['path'])
            if not isinstance(item['replace'],str) or not item['replace'] or not isinstance(item['with'],str):
                raise ContractError('Perturbation must replace one nonempty exact match')
    if not isinstance(c3['protect_additional'],list) or not c3['protect_additional']:
        raise ContractError('Revocation paths required')
    for p in c3['protect_additional']: relative(p,True)
    return data
