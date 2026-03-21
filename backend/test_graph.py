"""Test 2: Graph builder verification"""
import sys
sys.path.insert(0, r"D:\Projects\cascade\cascade\backend")

from core.graph.graph_builder import GraphBuilder
b = GraphBuilder(
    repo_path=r"D:\Projects\cascade\cascade\backend",
    cache_dir=r"D:\Projects\cascade\cascade\backend\cache"
)
G = b.build()
s = b.get_stats()
print("Nodes:", s["nodes"])
print("Edges:", s["edges"])
print("Files parsed:", s["files_parsed"])
print("Errors:", s["errors"][:3])
import networkx as nx
top = sorted(dict(G.degree()).items(), key=lambda x: x[1], reverse=True)[:5]
for nid, deg in top:
    print(f"  {nid}  degree={deg}")
