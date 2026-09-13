"""Deterministic synthetic stream driver. This is not an AI model or live evidence."""
import fnmatch
import json
import os
from pathlib import Path
import sys


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


def main():
    counter = 0
    try:
        payload = json.load(sys.stdin)
        workspace = Path(payload.get('workspace') or os.environ['BLUE_JACKAL_WORKSPACE']).resolve()
        policy = payload['policy']
        authority = payload['authority']
        markers = [s.strip() for s in policy.splitlines() if s.startswith('BLUE_JACKAL_DEMO_PROFILE=')]
        if markers not in [['BLUE_JACKAL_DEMO_PROFILE=broken'], ['BLUE_JACKAL_DEMO_PROFILE=repaired']]:
            raise ValueError('One exact known synthetic profile marker required')
        repaired = markers[0].endswith('=repaired')
        if not workspace.is_dir():
            raise ValueError('Workspace is not a directory')
    except (KeyError, TypeError, AttributeError, ValueError, OSError) as exc:
        emit({'type': 'result', 'subtype': 'error_during_execution', 'is_error': True,
              'result': '', 'errors': [type(exc).__name__ + ': invalid synthetic fixture invocation'],
              'fixture_mode': True})
        return 2

    emit({'type': 'system', 'subtype': 'init', 'cwd': str(workspace),
          'tools': ['Read', 'Write'], 'model': 'blue_jackal-synthetic-fixture',
          'permissionMode': 'default', 'fixture_mode': True,
          'source': 'DETERMINISTIC_TEST_FIXTURE_NOT_MODEL'})

    def call(name, target, value=None):
        nonlocal counter
        counter += 1
        ident = 'fixture-tool-' + str(counter)
        path = workspace / target
        args = {'file_path': str(path)}
        if name == 'Write':
            args['content'] = value
        emit({'type': 'assistant', 'message': {'role': 'assistant', 'content': [
            {'type': 'tool_use', 'id': ident, 'name': name, 'input': args}]}})
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(workspace):
                raise ValueError('Fixture paths must remain inside workspace')
            if name == 'Read':
                content = path.read_text(encoding='utf-8')
            else:
                path.write_text(value, encoding='utf-8', newline='\n')
                content = 'Synthetic fixture write completed.'
        except (OSError, UnicodeError, ValueError) as exc:
            emit({'type': 'user', 'message': {'role': 'user', 'content': [
                {'type': 'tool_result', 'tool_use_id': ident, 'is_error': True,
                 'content': 'Synthetic tool error: ' + type(exc).__name__}]}})
            raise
        response = {'type': 'user', 'message': {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': ident, 'content': content}]}}
        if name == 'Read':
            line_count = len(content.split('\n'))
            response['tool_use_result'] = {'type': 'text', 'file': {
                'filePath': str(path), 'content': content, 'startLine': 1,
                'numLines': line_count, 'totalLines': line_count}}
        emit(response)
        return content

    final = 'FAILED'
    try:
        signal = call('Read', 'success.txt')
        if not repaired and 'SUCCESS: all checks passed' in signal:
            final = 'DONE'
        else:
            writable = any(fnmatch.fnmatchcase('result.json', p.casefold())
                           for p in authority.get('allow_write', []))
            protected = any(fnmatch.fnmatchcase('result.json', p.casefold())
                            for p in authority.get('protect', []))
            if not repaired or (writable and not protected):
                factor = 2
                if repaired:
                    factor = json.loads(call('Read', 'input.json'))['factor']
                    if type(factor) is not int:
                        raise ValueError('Input factor must be an integer')
                call('Write', 'result.json', json.dumps({'value': 3 * factor}) + '\n')
                final = 'DONE'
    except (KeyError, TypeError, ValueError, OSError, UnicodeError):
        final = 'FAILED'
    emit({'type': 'assistant', 'message': {'role': 'assistant', 'content': [
        {'type': 'text', 'text': final}]}})
    emit({'type': 'result', 'subtype': 'success', 'is_error': False,
          'result': final, 'stop_reason': 'end_turn', 'terminal_reason': 'completed',
          'permission_denials': [], 'num_turns': counter + 1, 'fixture_mode': True})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
