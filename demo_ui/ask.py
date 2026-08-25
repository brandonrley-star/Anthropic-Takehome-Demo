"""
Bounded live Claude Q&A about a single finding.

This is the only place in the UI that calls a model. It does NOT rerun the
pipeline. It assembles one finding, its competing hypotheses, and only the work
orders that finding actually cites, then asks a question against that packet.

If no credentials are present the feature reports itself unavailable and the
rest of the application is unaffected.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from demo_ui import data  # noqa: E402

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
MAX_TOKENS = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "900"))
MAX_QUESTION_CHARS = 400

SYSTEM = """You are assisting an operations analyst reviewing one finding from a \
fleet reliability analysis of solar O&M work orders.

THE ENVIRONMENT IS SYNTHETIC. Every site, equipment manufacturer, technician and \
work order below is fictional demonstration data. Do not present it as real \
operational history for any company.

Rules, all of them strict:
- Answer ONLY from the evidence supplied in this message. You have no other \
information about this fleet.
- Cite work order IDs (for example WO-2026-00571) for every factual claim about \
what a technician observed or recorded.
- Distinguish clearly between what the evidence STATES and what you INFER from it.
- Never invent a work order ID, an asset count, a dollar figure, a date or a site.
- If the supplied evidence does not answer the question, say so plainly and say \
what evidence would be needed.
- Do not produce dollar figures of your own. Financial impact is calculated \
downstream by deterministic code from stated assumptions.
- Do not narrate your reasoning process or show internal deliberation. Give the \
conclusion and the evidence that supports it.
- Write for an operations executive: plain sentences, no jargon, no headers, no \
bullet lists longer than four items. Aim for 120-180 words."""


def status():
    return {"available": bool(os.environ.get("ANTHROPIC_API_KEY")
                              or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
            "model": MODEL}


SUGGESTED = {
    "decline": [
        "Why did you decline this candidate?",
        "What evidence would change your conclusion?",
        "Summarise this for an operations executive.",
        "What should the customer investigate next?",
    ],
    "escalate": [
        "Why is this worth escalating?",
        "What is the strongest evidence for this finding?",
        "What would weaken this conclusion?",
        "Summarise this for an operations executive.",
    ],
    "deprioritize": [
        "Why is this real but not worth acting on now?",
        "What would make this worth escalating?",
        "Summarise this for an operations executive.",
        "What should the customer monitor?",
    ],
}


def suggested_questions(verdict):
    return SUGGESTED.get(verdict, SUGGESTED["escalate"])


def _packet(cid):
    """Bounded evidence packet: one finding, its hypotheses, its cited work orders."""
    d = data.finding_detail(cid)
    if not d:
        return None, None
    cited = d["supporting_wo_ids"]
    wos = data.work_orders(cited)
    lines = [
        f"FINDING {cid}",
        f"Cluster: {d['label']}",
        f"Cluster size: {d['n_work_orders']} work orders",
        f"Verdict reached: {d['verdict'].upper()} (confidence: {d['confidence']})",
        f"Business headline: {d['headline']}",
        f"Recommended action: {d['action']}",
        "",
        "VERIFICATION REASONING (already produced by the analysis):",
        d["reasoning"],
        "",
        "EVIDENCE AGAINST THIS VERDICT (already identified by the analysis):",
        d["contradicting"],
        "",
        f"POPULATION AT RISK: {d['population_detail'].get('count', 0)} — "
        f"{d['population_detail'].get('description', '')}",
        f"Basis: {d['population_detail'].get('basis', '')}",
        "",
        "COMPETING HYPOTHESES THAT WERE CONSIDERED:",
    ]
    for h in d["hypotheses"]:
        mark = "SELECTED" if h.get("id") == d["selected_hypothesis"] else "rejected"
        lines.append(f"  [{mark}] {h.get('id')} ({h.get('type')}): {h.get('statement')}")
    lines += ["", f"CITED WORK ORDERS ({len(wos)}) — full technician narratives:"]
    for w in wos:
        lines.append(
            f"\n{w['wo_id']} | {w['site']} | {w['date']} | asset {w['asset_id']}"
            f" | {w['labor_hours']}h | resolution {w['resolution_code']}"
            f"\n  \"{w['narrative']}\"")
    return "\n".join(lines), d


def stream(cid, question, emit):
    """Same bounded packet, streamed. `emit(text)` is called per delta.

    Returns a dict of trailing metadata, or an error dict. The non-streaming
    answer() below stays as the fallback path.
    """
    st = status()
    if not st["available"]:
        return {"error": "Live Claude Q&A unavailable — no API key configured."}
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return {"error": "No question supplied."}
    packet, d = _packet(cid)
    if packet is None:
        return {"error": f"Unknown finding {cid!r}."}
    try:
        import anthropic
    except ImportError:
        return {"error": "The anthropic SDK is not installed in this environment."}
    try:
        client = anthropic.Anthropic()
        with client.messages.stream(
            model=MODEL, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user",
                       "content": f"{packet}\n\n---\n\nQUESTION: {question}"}],
        ) as s:
            for text in s.text_stream:
                emit(text)
            final = s.get_final_message()
        u = final.usage
        return {"done": True, "model": MODEL,
                "evidence_work_orders": d["supporting_wo_ids"],
                "usage": {"input_tokens": u.input_tokens,
                          "output_tokens": u.output_tokens}}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:300]}"}


def answer(cid, question):
    st = status()
    if not st["available"]:
        return {"error": "Live Claude Q&A unavailable — no API key configured."}
    question = (question or "").strip()
    if not question:
        return {"error": "No question supplied."}
    if len(question) > MAX_QUESTION_CHARS:
        question = question[:MAX_QUESTION_CHARS]
    packet, d = _packet(cid)
    if packet is None:
        return {"error": f"Unknown finding {cid!r}."}

    try:
        import anthropic
    except ImportError:
        return {"error": "The anthropic SDK is not installed in this environment."}

    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user",
                       "content": f"{packet}\n\n---\n\nQUESTION: {question}"}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        u = resp.usage
        return {
            "answer": text,
            "model": MODEL,
            "truncated": resp.stop_reason == "max_tokens",
            "evidence_work_orders": d["supporting_wo_ids"],
            "usage": {"input_tokens": u.input_tokens,
                      "output_tokens": u.output_tokens},
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:300]}"}
