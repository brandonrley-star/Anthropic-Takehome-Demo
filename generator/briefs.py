"""Brief construction for the planted patterns that need progression-aware text."""

import itertools

# Cycle template variants rather than sampling them, so that within a small
# planted group (four ground fault tickets, three cosmetic observations) no two
# work orders end up carrying byte-identical text.
_CYCLES = {}


def _cycle(key, options, rng):
    if key not in _CYCLES:
        opts = list(options)
        rng.shuffle(opts)
        _CYCLES[key] = itertools.cycle(opts)
    return next(_CYCLES[key])


def reset_cycles():
    _CYCLES.clear()

# ---------------------------------------------------------------------------
# SIGNAL 2 - Caprock Mesa. The diagnosis is never stated. What varies over the
# window is the RETURN on cleaning, which is the thing inconsistent with a
# soiling explanation. Everything else is written the way a crew that believes
# it is a soiling problem would write it.
# ---------------------------------------------------------------------------

def signal2_brief(rng, kind, block, prog):
    if kind == "wash":
        if prog < 0.28:
            pct = _cycle("wash_e", ["about 4", "just over 4", "close to 5", "3.5"], rng)
            return ("PM", ["CLEANED"], _cycle("wash_early", [
                f"Washed {block}. Dust was heavy on the lower rows. Checked the strings against the "
                f"ref cells the next clear day, output up {pct}% and holding.",
                f"{block} wash done. Crew started at the west end. Next clear day the block was up "
                f"{pct}% on the reference, about what we expected.",
            ], rng))
        if prog < 0.58:
            pct = _cycle("wash_m", ["about 2", "a bit over 2", "2.5", "under 2"], rng)
            return ("PM", ["CLEANED"], _cycle("wash_mid", [
                f"Wash crew finished {block}. Got {pct}% back on the next clear day. Less than the "
                f"last round on this block but the panels looked clean when we left.",
                f"{block} washed. Only {pct}% recovery this cycle. Down on where this block used to "
                f"come back to. Water pressure and coverage were fine.",
            ], rng))
        if prog < 0.82:
            pct = _cycle("wash_l", ["maybe 1", "about 1", "1.2", "under 1.5"], rng)
            return ("PM", ["CLEANED", "OTHER"], _cycle("wash_late", [
                f"Washed {block} again. Only picked up {pct}% this time. Asked the crew to go back "
                f"over two rows in case they rushed it, same result. Panels are clean.",
                f"{block} wash complete. {pct}% on the next clear day, which is barely worth the "
                f"truck. Walked it myself afterward, glass is clean.",
            ], rng))
        return ("PM", ["CLEANED", "OTHER", "NO-FAULT-FOUND"], _cycle("wash_end", [
            f"{block} wash complete. Honestly not seeing much change in the numbers, maybe half a "
            f"percent. Modules look clean when you walk them. Not sure the wash interval is doing "
            f"what we think on this block.",
            f"Washed {block}. Ref cells barely moved afterward. Third cycle running where this block "
            f"does not respond like the newer ones do. Flagging it, someone might want to look at "
            f"whether we are washing this section for nothing.",
        ], rng))

    if kind == "scada":
        n = rng.randint(3, 11)
        nxt = f"B{min(8, int(block[1:]) + 4):02d}"
        return ("CM", ["NO-FAULT-FOUND", "ADJUSTED", "OTHER", "ESCALATED"], _cycle("scada", [
            f"SCADA flagged {n} strings low in {block}. Walked every one, no blown fuses, connectors "
            f"tight, nothing open. Currents are just down across the board. Reset the alarm threshold.",
            f"Underperformance alarm {block}. Compared against {nxt} which is on the same inverter "
            f"and it is fine. Nothing found on the low side.",
            f"{n} strings in {block} reading soft again. Meggered two of them, insulation ok. No "
            f"fault to clear. Left it.",
            f"Low string alarm {block}. Third or fourth time on this block. IV traces look flat "
            f"rather than stepped, so not a broken string. Nothing to replace.",
            f"{block} flagged low again. Checked the same strings as last month, no change either "
            f"way. Widened the alarm band so it stops paging.",
        ], rng))

    if kind == "ir":
        n = rng.randint(6, 22)
        return ("Inspection", ["NO-FAULT-FOUND", "OTHER"], _cycle("ir", [
            f"IR scan {block}. {n} warm cells scattered across the block, nothing clustered and "
            f"nothing above the threshold. Unremarkable, no action.",
            f"Thermal survey of {block}, {n} hot cells noted. Spread out, no pattern to them. Filed "
            f"the imagery, nothing to action.",
            f"Flew {block} for IR. Scattered cell level warm spots, {n} of them. Below the reporting "
            f"limit individually so closing this out.",
            f"IR on {block}. {n} warm cells, more than the last flight but still scattered and still "
            f"under threshold. Nothing that meets the criteria for a ticket.",
        ], rng))

    if kind == "cosmetic":
        return _cycle("cosmetic", [
            ("Inspection", ["OTHER", "NO-FAULT-FOUND"],
             f"Punch list walk {block}. Noted some of the older modules have gone chalky white on the "
             f"back sheet, more on the west facing rows. Cosmetic, no cracking, output not affected as "
             f"far as I can tell. Also two cracked glass to replace, ticketed those."),
            ("CM", ["NO-FAULT-FOUND", "OTHER"],
             f"Checked a low string in {block}, nothing wrong electrically. While I was under there a "
             f"fair few backsheets look discoloured and a bit dry, sort of yellowed. Cosmetic only. "
             f"Closed, no action."),
            ("Inspection", ["OTHER"],
             f"Walked {block} with the owner's rep. He asked about the chalky look on the back of the "
             f"panels in the old sections. Told him it is cosmetic on this vintage. Nothing else to "
             f"report."),
        ], rng)

    # ground fault - tone escalates but never becomes a diagnosis
    if prog < 0.4:
        return ("CM", ["ADJUSTED", "NO-FAULT-FOUND"],
                f"Ground fault reading elevated on the {block} combiner. Reseated the string "
                f"connections and it came back into range. Nothing visibly wrong.")
    if prog < 0.75:
        return ("CM", ["ADJUSTED", "NO-FAULT-FOUND", "OTHER"],
                f"GF reading up again in {block}, second time on this one. Reseated connections, "
                f"cleared. Damp morning, might be that.")
    return ("CM", ["ESCALATED", "ADJUSTED", "OTHER"], _cycle("gf_late", [
        f"{block} ground fault reading elevated, third or fourth time on this block now. Reseated "
        f"and it came down but it keeps coming back. Meggered the two worst strings, readings are "
        f"low side of normal. Passing it up, someone should look at this properly.",
        f"GF alarm {block} again. Reseating gets it back in range for a week or two and then it "
        f"drifts up. Insulation resistance on the older strings is not what it used to be. Not "
        f"failing, just lower than I would like.",
        f"Another ground fault on {block}. I have stopped counting. Same fix, same result. Whatever "
        f"is going on it is not the connections, they are clean every time I open them up.",
    ], rng))


# ---------------------------------------------------------------------------
# DECOY 1 - Sundowner Mesa. Wind event, not hail: the Mojave is a wind and heat
# climate, and the design spec's own regional table lists hail only for West
# Texas. A microburst catching rows mid-stow is the realistic mechanism here.
# ---------------------------------------------------------------------------

PER_ROW = [
    "{asset} damper bent. Straightened and retorqued. Row tracking.",
    "{asset} torque tube out of true at the third bearing. Shimmed and realigned.",
    "{asset} drive coupling sheared. Replaced coupling, row back in service.",
    "{asset} two module clamps pulled through. Replaced clamps, no glass damage.",
    "{asset} not tracking, limit switch bracket bent. Reformed and recalibrated.",
    "{asset} bearing housing cracked. Replaced housing.",
    "{asset} stow pin damaged. Replaced pin and checked the adjacent bays.",
    "{asset} purlin bent on the north end. Straightened, torqued, verified travel.",
]

PER_ZONE = [
    "Worked {asset} today. Six rows with bent dampers, two with torque tube damage. Repaired what "
    "we could, three rows left stowed pending parts.",
    "{asset} repairs. Nine rows needed attention, mostly clamps and dampers. Zone back tracking "
    "except two rows.",
    "Finished the {asset} sweep. Eleven rows touched, four drives replaced. Long couple of days.",
    "{asset} walkdown and repair. Damage concentrated on the west two thirds of the zone.",
]

EVENT_NAMED = [
    "Out at {asset} cleaning up after the microburst that came through on the 14th. Wind gauge at "
    "the met station peaked around 71 mph before it dropped out. Rows caught partway to stow. "
    "Bent dampers and a couple of twisted torque tubes.",
    "{asset}. This is all from the wind event on March 14th, the whole west side got hit at once. "
    "Working through it zone by zone.",
    "Damage assessment continuing at {asset} following the March 14 high wind event. Nothing here "
    "is new damage, it is all from that night.",
]

OBLIQUE = ["Storm damage.", "Post event walkdown.", "More cleanup from the event.",
           "Same as the others this month.", "Continuing the walkdown."]


def decoy1_brief(rng, w):
    if w.get("_names_event"):
        txt = rng.choice(EVENT_NAMED)
    elif w["_mode"] == "per_row":
        txt = rng.choice(PER_ROW)
    else:
        txt = rng.choice(PER_ZONE)
    if w.get("_oblique") and not w.get("_names_event"):
        txt = rng.choice(OBLIQUE) + " " + txt
    if w.get("_claim"):
        txt += (f" Photos and measurements logged against the property claim, ref {w['_claim']}, "
                f"adjuster has the file.")
    return txt


HABIT_BRIEFS = [
    "{asset} drive motor replaced. Row tracking normally.",
    "{asset} controller reset, back online.",
    "{asset} greased and fasteners checked.",
    "{asset} out of alignment with the block. Recalibrated.",
    "{asset} limit switch replaced.",
    "{asset} damper bolt loose, retorqued.",
]
