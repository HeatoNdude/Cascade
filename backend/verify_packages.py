"""Quick verification of Phase 2 packages."""
import sys

checks = []

try:
    import tree_sitter
    checks.append(f"[OK] tree-sitter {tree_sitter.__version__}")
except Exception as e:
    checks.append(f"[FAIL] tree-sitter: {e}")

try:
    import networkx
    checks.append(f"[OK] networkx {networkx.__version__}")
except Exception as e:
    checks.append(f"[FAIL] networkx: {e}")

try:
    import git
    checks.append("[OK] gitpython")
except Exception as e:
    checks.append(f"[FAIL] gitpython: {e}")

try:
    import faiss
    checks.append("[OK] faiss")
except Exception as e:
    checks.append(f"[FAIL] faiss: {e}")

try:
    from sentence_transformers import SentenceTransformer
    checks.append("[OK] sentence-transformers")
except Exception as e:
    checks.append(f"[FAIL] sentence-transformers: {e}")

try:
    import watchdog
    checks.append("[OK] watchdog")
except Exception as e:
    checks.append(f"[FAIL] watchdog: {e}")

for c in checks:
    print(c)

fails = [c for c in checks if c.startswith("[FAIL]")]
if fails:
    print(f"\n{len(fails)} FAILED")
    sys.exit(1)
else:
    print("\nAll 6 packages verified OK")
