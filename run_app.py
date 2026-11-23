#!/usr/bin/env python3
"""
Main launcher script for TileSet Map Maker.
"""
import sys
import os

# Add current workspace directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tileset_map_maker.main import main

if __name__ == "__main__":
    raise SystemExit(main())
