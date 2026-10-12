"""Run `python editor.py` to tune Orion Reach without editing Python source."""
from pathlib import Path
import argparse
import os


def main():
    parser=argparse.ArgumentParser(description='Orion Reach balance and research-tree editor')
    parser.add_argument('--profile',type=Path,help='JSON profile to edit; defaults to balance.json beside main.py')
    parser.add_argument('--validate',type=Path,metavar='PROFILE',help='validate a profile and exit without opening a window')
    parser.add_argument('--export-defaults',type=Path,metavar='PROFILE',help='write the built-in balance to JSON and exit')
    parser.add_argument('--headless',action='store_true',help='use dummy display/audio drivers for preview capture')
    parser.add_argument('--screenshot',type=Path,help='render the editor once to PNG and exit')
    parser.add_argument('--tree',action='store_true',help='open the research-tree view')
    args=parser.parse_args()
    from orion import balance
    try:
        if args.validate:
            profile=balance.read_profile(args.validate)
            print(f'Valid: {profile["name"]} ({sum(map(len,profile["data"].values()))} entries)')
            return
        if args.export_defaults:
            balance.write_profile(args.export_defaults,balance.default_profile())
            print(f'Default balance written to {args.export_defaults}')
            return
        os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
        if args.headless:
            os.environ['SDL_VIDEODRIVER']='dummy'
            os.environ['SDL_AUDIODRIVER']='dummy'
        try:
            import pygame as pg
        except ImportError:
            raise SystemExit('Install the game dependency: python -m pip install -r requirements.txt')
        from orion.balance_editor import BalanceEditor
        editor=BalanceEditor(args.profile or balance.DEFAULT_PATH)
        try:
            if args.tree: editor.tree_mode()
            if args.screenshot:
                editor.draw()
                args.screenshot.parent.mkdir(parents=True,exist_ok=True)
                pg.image.save(editor.canvas,args.screenshot)
            else: editor.run()
        finally:
            pg.quit()
    except (balance.BalanceError,OSError) as exc:
        raise SystemExit(f'Editor: {exc}') from exc


if __name__=='__main__':
    main()
