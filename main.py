#!/usr/bin/env python3
"""
Onikuma CW935 Mouse Driver & Configuration Tool
================================================
Entry point launcher. Starts Desktop GUI by default, or CLI if --cli flag is passed.
"""

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Onikuma CW935 Mouse Controller")
    parser.add_argument("--cli", action="store_true", help="Launch terminal CLI mode instead of GUI")
    args = parser.parse_args()

    if args.cli:
        from onikuma.cli import main as cli_main
        cli_main()
    else:
        from onikuma.gui import main as gui_main
        gui_main()

if __name__ == "__main__":
    main()
