"""Test 1: AST parser verification"""
import sys
sys.path.insert(0, r"D:\Projects\cascade\cascade\backend")

from core.graph.ast_parser import parse_file
r = parse_file(r"D:\Projects\cascade\cascade\backend\main.py")
print("Functions:", len(r["functions"]))
print("Imports:", len(r["imports"]))
print("Error:", r["error"])
for fn in r["functions"][:5]:
    print(" -", fn["name"], "line", fn["line_start"])
