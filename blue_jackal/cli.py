"""The local Blue Jackal command line."""
import argparse
from pathlib import Path
import shutil
import sys

from .contract import ContractError
from . import __version__, challenges, demo, export, report, runner, inspector


def main(argv=None):
    parser = argparse.ArgumentParser(prog='blue-jackal', description='Test what your coding agent actually completed.')
    parser.add_argument('--version',action='version',version=__version__)
    parser.add_argument('--root',type=Path,default=Path.cwd(),help='contract/demo directory (default: current directory)')
    commands = parser.add_subparsers(dest='action',required=True)
    commands.add_parser('init',help='create the engineered demo in an empty directory')
    run = commands.add_parser('run',help='record Claude or the clearly labeled synthetic demo driver')
    run.add_argument('agent',nargs=argparse.REMAINDER)
    inspect = commands.add_parser('inspect',help='read a stored receipt')
    inspect.add_argument('id',nargs='?'); inspect.add_argument('--html',action='store_true')
    crash = commands.add_parser('crash',help='run frozen challenges against a passing baseline')
    crash.add_argument('id',nargs='?'); crash.add_argument('--only',choices=challenges.CHALLENGES)
    verify = commands.add_parser('verify',help='replay all challenges after changing only the agent policy')
    verify.add_argument('--against',required=True)
    exp = commands.add_parser('export',help='write a conservative local allowlist derivative')
    exp.add_argument('id')
    args = parser.parse_args(argv); root = args.root.absolute()
    try:
        if args.action=='init':
            demo.initialize(root)
            print('Blue Jackal demo initialized. Engineered fixture; no model benchmark claim.\n'+str(root))
            return 0
        if args.action=='run':
            agent = args.agent[1:] if args.agent[:1]==['--'] else args.agent
            if agent==['demo']:
                command=[sys.executable,str(Path(__file__).with_name('fixture_driver.py').resolve())]; fixture=True
            elif len(agent)==1 and Path(agent[0]).stem.casefold()=='claude':
                executable=shutil.which(agent[0])
                if not executable: raise ContractError('Claude executable unavailable')
                command=[executable]; fixture=False
            else: raise ContractError('Use run -- claude (live) or run -- demo (synthetic fixture)')
            folder, record = runner.run(root,command,fixture)
        elif args.action=='crash': folder,record = challenges.crash(root,args.id,args.only)
        elif args.action=='verify': folder,record = challenges.verify(root,args.against)
        else: folder,record = runner.find_record(root,args.id)
        if args.action=='export':
            destination=root/'.blue-jackal'/'exports'/record['id']
            value=export.export_run(record,destination)
            print('Blue Jackal local export: '+str(destination)+'\nAllowlist derivative; inspect manifest exclusions before sharing.')
        else:
            print(report.terminal(record))
            if args.action!='inspect' or args.html:
                inspector.write(root, folder, record)
            print('Record: '+str(folder))
        # Success here means the measurement completed, even when a challenge failed.
        # Scriptable acceptance decisions belong to the explicit JSON axes/statuses.
        error = (record.get('work')=='ERROR'
                 or any(c.get('status')=='ERROR' for c in record.get('challenges',[]))
                 or record.get('measurement_error') is True)
        return 2 if error else 0
    except (ContractError,OSError,ValueError,KeyError) as exc:
        print('Blue Jackal ERROR: '+str(exc),file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
