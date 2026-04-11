#!/usr/bin/env python3
"""
GTNH Mod Installer
A GUI application for installing additional mods, scripts, and configs for GTNH
"""
import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import MainWindow


def main():
    """Main entry point"""
    app = MainWindow()
    app.run()


if __name__ == '__main__':
    main()
