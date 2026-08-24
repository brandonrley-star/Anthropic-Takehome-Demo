"""
Structural and lexical leakage audit.

Question: can a planted work order be told apart from a comparable routine one
WITHOUT understanding what it says? Comparisons are against MATCHED controls -
background work of the same type on the same class of asset in the same regions -
because comparing thermal inverter tickets against vegetation tickets would
show a difference that means nothing.
"""
import sys, collections
import numpy as np
from scipy import stats
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from _common import load

INV = {"cm_inv_dcgf", "cm_inv_acfault", "cm_inv_part", "cm_inv_cooling",
       "wty_inverter", "pm_inverter"}
HOT = {"ERCOT_WEST", "ERCOT_SOUTH", "CAISO_CV", "CAISO_MOJAVE"}


def summarize(name, rows):
    lh = [w["labor_hours"] for w in rows]
    nw = [len(w["narrative"].split()) for w in rows]
    print(f"  {name:26s} n={len(rows):4d}  hours med={np.median(lh):5.1f} "
          f"| words med={np.median(nw):5.0f} mean={np.mean(nw):6.1f} "
          f"| parts {np.mean([bool(w['parts_used']) for w in rows]):4.0%} "
          f"| lost {np.mean([w['estimated_lost_production_mwh'] is not None for w in rows]):4.0%} "
          f"| open {np.mean([w['date_closed'] is None for w in rows]):4.0%}")


def main():
    sites, assets, techs, wos = load()
    print("=" * 78)
    print("STRUCTURAL AND LEXICAL LEAKAGE AUDIT")
    print("=" * 78)

    s1 = [w for w in wos if w["_cls"] == "signal_1"]
    ctl = [w for w in wos if w["_cls"] == "background"
           and w.get("_theme_key") in INV and w["region"] in HOT
           and w["wo_type"] in {x["wo_type"] for x in s1}]

    print("\nSignal 1 vs matched controls (hot-region inverter corrective work):")
    summarize("signal_1", s1)
    summarize("matched controls", ctl)

    print("\n  distribution tests (a low p-value means the two are separable):")
    for label, f in [("labor_hours", lambda w: w["labor_hours"]),
                     ("narrative word count", lambda w: len(w["narrative"].split()))]:
        a = [f(w) for w in s1]; b = [f(w) for w in ctl]
        ks = stats.ks_2samp(a, b)
        mw = stats.mannwhitneyu(a, b)
        verdict = "SEPARABLE" if ks.pvalue < 0.05 else "not separable"
        print(f"    {label:22s} KS p={ks.pvalue:.3f}  MW p={mw.pvalue:.3f}  -> {verdict}")

    print("\n  field completeness (share of records with the field populated):")
    for f in ["parts_used", "asset_id"]:
        a = np.mean([bool(w[f]) for w in s1]); b = np.mean([bool(w[f]) for w in ctl])
        print(f"    {f:22s} signal {a:5.0%}   control {b:5.0%}   delta {a-b:+.0%}")
    for f, g in [("lost_production", lambda w: w["estimated_lost_production_mwh"] is not None),
                 ("still open", lambda w: w["date_closed"] is None)]:
        a = np.mean([g(w) for w in s1]); b = np.mean([g(w) for w in ctl])
        print(f"    {f:22s} signal {a:5.0%}   control {b:5.0%}   delta {a-b:+.0%}")

    print("\n  technician register mix:")
    for nm, rows in [("signal_1", s1), ("controls", ctl)]:
        c = collections.Counter(w["_register"] for w in rows)
        print(f"    {nm:12s} " + "  ".join(f"{k}={v/len(rows):.0%}" for k, v in sorted(c.items())))

    print("\n  wo_id ordering: does the identifier sequence carry plant information?")
    idx = sorted(int(w["wo_id"][-5:]) for w in s1)
    allid = sorted(int(w["wo_id"][-5:]) for w in wos)
    print(f"    signal_1 ids span {idx[0]}-{idx[-1]}, mean gap {np.mean(np.diff(idx)):.1f} "
          f"vs corpus mean gap {np.mean(np.diff(allid)):.2f} -> "
          f"{'CLUSTERED' if np.mean(np.diff(idx)) < 5 else 'not clustered'}")

    # ---------------- lexical -----------------------------------------------
    print("\n  LEXICAL")
    X = [w["narrative"] for w in s1 + ctl]
    y = [1] * len(s1) + [0] * len(ctl)
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=6000)
    auc = cross_val_score(LogisticRegression(max_iter=2000, class_weight="balanced"),
                          vec.fit_transform(X), y, cv=5, scoring="roc_auc")
    print(f"    full-text char n-gram AUC {auc.mean():.2f}")
    print("      Expected to be high and NOT a defect: these tickets describe a")
    print("      different failure mode, so their vocabulary differs. A classifier")
    print("      learning that has learned the finding, not an artifact.")

    # The question that matters: does the planted text differ in STYLE - the
    # thing a technician's writing habits produce, independent of subject?
    import re as _re
    FUNCTION = set("""a an the and or but so then if when while after before as at by for
        from in into of off on out over to up with is was were be been being it its this
        that these those there here he she they them we i you not no nor all any both each
        few more most other some such only own same than too very can will just should now
        did does do had has have""".split())

    def style_vec(t):
        words = _re.findall(r"[A-Za-z']+", t)
        n = max(1, len(words))
        low = sum(1 for w in words if w.islower())
        up = sum(1 for w in words if w.isupper() and len(w) > 1)
        return [
            sum(1 for c in t if c == ",") / n,
            sum(1 for c in t if c == ".") / n,
            sum(1 for c in t if c == "/") / n,
            sum(1 for c in t if c == ";") / n,
            low / n, up / n,
            np.mean([len(w) for w in words]) if words else 0,
            1.0 if t[:1].islower() else 0.0,
            1.0 if t.rstrip().endswith(".") else 0.0,
            sum(1 for w in words if w.lower() in FUNCTION) / n,
        ]

    Xs = np.array([style_vec(t) for t in X])
    auc3 = cross_val_score(LogisticRegression(max_iter=3000, class_weight="balanced"),
                           Xs, y, cv=5, scoring="roc_auc")
    print(f"    STYLE-ONLY AUC {auc3.mean():.2f} (+/- {auc3.std():.2f})")
    print("      (punctuation rates, casing, word length, function-word density -")
    print("       no subject-matter vocabulary at all)")
    print(f"    -> {'STYLE LEAK: planted work orders are WRITTEN differently' if auc3.mean() > 0.70 else 'no style leak: planted text is written like the rest of the corpus'}")

    # ---------------- signal 2 ----------------
    s2 = [w for w in wos if w["_cls"] == "signal_2"]
    cap = [w for w in wos if w["site_name"] == "Caprock Mesa" and w["_cls"] == "background"]
    print("\nSignal 2 vs other work at the same site:")
    summarize("signal_2", s2)
    summarize("Caprock Mesa background", cap)
    a = [len(w["narrative"].split()) for w in s2]
    b = [len(w["narrative"].split()) for w in cap]
    print(f"  narrative length KS p={stats.ks_2samp(a, b).pvalue:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
