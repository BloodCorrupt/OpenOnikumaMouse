"""
PyInstaller Build Script for Onikuma CW935 Mouse Control Panel
==============================================================
Compiles the application into a standalone Windows .exe with embedded assets.
"""

import os
import sys
import subprocess

def build():
    print("Building Onikuma CW935 Executable...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, "assets")
    icon_path = os.path.join(assets_dir, "icon.ico")

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--icon={icon_path}",
        f"--add-data={assets_dir};assets",
        "--name=OnikumaCW935",
        "main.py"
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=base_dir)

    if res.returncode == 0:
        print("\n" + "="*50)
        print("BUILD SUCCESSFUL!")
        print(f"Executable output: {os.path.join(base_dir, 'dist', 'OnikumaCW935', 'OnikumaCW935.exe')}")
        print("="*50)
    else:
        print("\nBUILD FAILED with exit code:", res.returncode)

if __name__ == "__main__":
    build()
