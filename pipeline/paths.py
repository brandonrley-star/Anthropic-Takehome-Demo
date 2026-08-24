"""Path resolution. Everything is relative to the repo root, never absolute."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "corpus")          # the ONLY corpus directory we read
PIPELINE = os.path.join(ROOT, "pipeline")
DEMO = os.path.join(ROOT, "demo")
REFERENCE_RUN = os.path.join(DEMO, "reference_run")
CACHE = os.path.join(ROOT, ".pipeline_cache")

# eval/ holds the answer key. Nothing in this package may read it. run.py asserts
# that no path handed to a loader resolves inside it.
FORBIDDEN = os.path.join(ROOT, "eval")


def guard(path):
    p = os.path.abspath(path)
    if p == FORBIDDEN or p.startswith(FORBIDDEN + os.sep):
        raise PermissionError(f"pipeline may not read eval/: {path}")
    return p


def corpus_file(name):
    return guard(os.path.join(CORPUS, name))
