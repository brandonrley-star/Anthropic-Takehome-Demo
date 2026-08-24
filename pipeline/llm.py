"""
Pluggable model backend with cost and wall-clock accounting.

Three backends:
  anthropic  live API calls. The production path.
  authored   replays responses from demo/reference_run/authored/<stage>.jsonl.
             Used to ship a committed reference run without credentials.
  rules      deterministic stand-in, Stage 1 only. Labelled everywhere it is used.

CACHE KEYING. Entries are keyed by a SEMANTIC id (wo_id, candidate_id), never by
a hash of the prompt text. Prompt-hash keying means every wording tweak silently
invalidates a body of authored work — the same desynchronisation failure that
cost this project a full corpus regeneration once already. Semantic keys survive
prompt edits.
"""

import json, os, time, hashlib, threading
from concurrent.futures import ThreadPoolExecutor
from . import paths

# $ per million tokens, from the Anthropic pricing table.
PRICING = {
    "claude-opus-5":    {"in": 5.00, "out": 25.00},
    "claude-sonnet-5":  {"in": 3.00, "out": 15.00},
    "claude-haiku-4-5": {"in": 1.00, "out": 5.00},
}
CACHE_READ_MULT = 0.10
CACHE_WRITE_MULT = 1.25

DEFAULT_MODEL = "claude-opus-5"


class Accounting:
    def __init__(self):
        self.stages = {}
        self._lock = threading.Lock()

    def record(self, stage, *, model=None, tin=0, tout=0, tcache_read=0,
               tcache_write=0, calls=0, cache_hits=0, seconds=0.0):
        with self._lock:
            s = self.stages.setdefault(stage, dict(
                model=model, calls=0, cache_hits=0, input_tokens=0,
                output_tokens=0, cache_read_tokens=0, cache_write_tokens=0,
                usd=0.0, seconds=0.0))
            if model:
                s["model"] = model
            s["calls"] += calls
            s["cache_hits"] += cache_hits
            s["input_tokens"] += tin
            s["output_tokens"] += tout
            s["cache_read_tokens"] += tcache_read
            s["cache_write_tokens"] += tcache_write
            s["seconds"] += seconds
            p = PRICING.get(model or s["model"] or DEFAULT_MODEL, PRICING[DEFAULT_MODEL])
            s["usd"] += (tin * p["in"] + tout * p["out"]
                         + tcache_read * p["in"] * CACHE_READ_MULT
                         + tcache_write * p["in"] * CACHE_WRITE_MULT) / 1_000_000

    def add_seconds(self, stage, seconds):
        with self._lock:
            self.stages.setdefault(stage, dict(
                model=None, calls=0, cache_hits=0, input_tokens=0, output_tokens=0,
                cache_read_tokens=0, cache_write_tokens=0, usd=0.0, seconds=0.0))
            self.stages[stage]["seconds"] += seconds

    def summary(self):
        tot_usd = sum(s["usd"] for s in self.stages.values())
        tot_s = sum(s["seconds"] for s in self.stages.values())
        return {"stages": self.stages, "total_usd": round(tot_usd, 4),
                "total_seconds": round(tot_s, 1)}

    def render(self):
        w = f"{'stage':<26}{'model':<18}{'calls':>7}{'cached':>8}{'in tok':>10}{'out tok':>9}{'USD':>9}{'sec':>8}"
        lines = [w, "-" * len(w)]
        for name, s in self.stages.items():
            lines.append(f"{name:<26}{(s['model'] or '-'):<18}{s['calls']:>7}"
                         f"{s['cache_hits']:>8}{s['input_tokens']+s['cache_read_tokens']:>10}"
                         f"{s['output_tokens']:>9}{s['usd']:>9.3f}{s['seconds']:>8.1f}")
        t = self.summary()
        lines.append("-" * len(w))
        lines.append(f"{'TOTAL':<26}{'':<18}{'':>7}{'':>8}{'':>10}{'':>9}"
                     f"{t['total_usd']:>9.3f}{t['total_seconds']:>8.1f}")
        return "\n".join(lines)


class BadModelResponse(Exception):
    """A live call returned something we could not turn into a record.

    Carries why, so run.py can fall back for THAT ticket instead of losing the
    whole run. Truncation is called out separately from malformed JSON: they
    have different fixes (raise max_tokens vs tighten the prompt).
    """
    def __init__(self, stage, key, reason, text=""):
        super().__init__(f"{stage}/{key}: {reason}")
        self.stage, self.key, self.reason, self.text = stage, key, reason, text


class MissingAuthoredResponse(Exception):
    def __init__(self, stage, key, system, user):
        super().__init__(f"no authored response for {stage}/{key}")
        self.stage, self.key, self.system, self.user = stage, key, system, user


class LLMClient:
    def __init__(self, backend="authored", model=DEFAULT_MODEL, accounting=None,
                 authored_dir=None, cache_dir=None, concurrency=16, verbose=False):
        self.backend = backend
        self.model = model
        self.acct = accounting or Accounting()
        self.authored_dir = authored_dir or os.path.join(paths.REFERENCE_RUN, "authored")
        self.cache_dir = cache_dir or paths.CACHE
        self.concurrency = concurrency
        self.verbose = verbose
        self._authored = {}
        self._cache = {}
        self._pending = []
        self._failures = []
        self._truncations = 0
        self._lock = threading.Lock()
        self._client = None
        os.makedirs(self.cache_dir, exist_ok=True)

    # ---------------------------------------------------------------- storage
    def _load_jsonl(self, path):
        out = {}
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        r = json.loads(line)
                        out[r["key"]] = r["response"]
        return out

    def load_stage(self, stage):
        if stage not in self._authored:
            self._authored[stage] = self._load_jsonl(
                os.path.join(self.authored_dir, f"{stage}.jsonl"))
        if stage not in self._cache:
            self._cache[stage] = self._load_jsonl(
                os.path.join(self.cache_dir, f"{stage}.jsonl"))

    def _append_cache(self, stage, key, response):
        with self._lock:
            self._cache[stage][key] = response
            with open(os.path.join(self.cache_dir, f"{stage}.jsonl"), "a") as f:
                f.write(json.dumps({"key": key, "response": response},
                                   ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ calls
    def complete(self, stage, key, system, user, max_tokens=2000):
        """Return a parsed JSON object for (stage, key)."""
        self.load_stage(stage)
        if key in self._cache[stage]:
            self.acct.record(stage, model=self.model, cache_hits=1)
            return self._cache[stage][key]
        if self.backend == "authored":
            if key in self._authored[stage]:
                self.acct.record(stage, model=self.model, cache_hits=1)
                return self._authored[stage][key]
            with self._lock:
                self._pending.append({"stage": stage, "key": key,
                                      "system": system, "user": user})
            raise MissingAuthoredResponse(stage, key, system, user)
        if self.backend == "anthropic":
            return self._call_anthropic(stage, key, system, user, max_tokens)
        raise ValueError(f"backend {self.backend!r} cannot serve stage {stage}")

    def _call_anthropic(self, stage, key, system, user, max_tokens):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        t0 = time.time()
        # cache_control on the system block: the schema and instructions are
        # identical across every ticket, so it should be a cache hit after the
        # first call. Volatile per-ticket content goes in the user turn.
        text, truncated = "", False
        for attempt, budget in enumerate((max_tokens, max_tokens * 3)):
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=budget,
                system=[{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
            )
            u = resp.usage
            self.acct.record(stage, model=self.model, calls=1,
                             tin=u.input_tokens, tout=u.output_tokens,
                             tcache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
                             tcache_write=getattr(u, "cache_creation_input_tokens", 0) or 0)
            text = "".join(b.text for b in resp.content if b.type == "text")
            truncated = resp.stop_reason == "max_tokens"
            if not truncated:
                break
            with self._lock:
                self._truncations += 1
        self.acct.add_seconds(stage, time.time() - t0)
        if truncated:
            raise BadModelResponse(stage, key,
                                   f"truncated at max_tokens={max_tokens * 3}", text)
        try:
            parsed = _parse_json(text)
        except (json.JSONDecodeError, ValueError) as e:
            raise BadModelResponse(stage, key, f"unparseable JSON: {e}", text)
        if not isinstance(parsed, dict):
            raise BadModelResponse(stage, key, f"expected an object, got {type(parsed).__name__}", text)
        self._append_cache(stage, key, parsed)
        return parsed

    def map(self, stage, items, build_prompt, max_tokens=2000):
        """Run `complete` across items. Returns (results, missing).

        `build_prompt(item) -> (key, system, user)`.
        With the authored backend, everything not yet authored comes back in
        `missing` instead of raising, so a run can report exactly what it needs.
        """
        results, missing = {}, []
        t0 = time.time()

        def one(item):
            k, sysp, usr = build_prompt(item)
            try:
                return k, self.complete(stage, k, sysp, usr, max_tokens), None
            except (MissingAuthoredResponse, BadModelResponse) as e:
                return k, None, e
            except Exception as e:          # network, rate limit, overload
                return k, None, BadModelResponse(stage, k, f"{type(e).__name__}: {e}")

        if self.backend == "anthropic" and self.concurrency > 1:
            with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
                for k, r, err in ex.map(one, items):
                    (results.__setitem__(k, r) if err is None else missing.append(err))
        else:
            for item in items:
                k, r, err = one(item)
                if err is None:
                    results[k] = r
                else:
                    missing.append(err)
        with self._lock:
            self._failures.extend(m for m in missing if isinstance(m, BadModelResponse))
        return results, missing

    def dump_pending(self, path):
        with open(path, "w") as f:
            for p in self._pending:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        return len(self._pending)


def _parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        i, j = text.find("{"), text.rfind("}")
        if i >= 0 and j > i:
            return json.loads(text[i:j + 1])
        raise
