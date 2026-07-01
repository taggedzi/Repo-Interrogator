"""Optional local semantic embedding support.

Everything in this package is inert unless the `semantic` extra
(onnxruntime + tokenizers) is installed and a cached model is present.
Importing this package itself never requires the extra; importing
`repo_mcp.semantic.embedder` does, and raises a clear ImportError if it's
missing.
"""

from __future__ import annotations
