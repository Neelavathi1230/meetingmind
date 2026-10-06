"""Meeting NLP: speakers, summary, decisions, action items, questions, topics (replaceable, local)."""
import re, math
from collections import Counter, defaultdict
STOP = set("a an the and or but if of to in on at for with by from as is are was were be been it its this that these those i we you they he she our your their there so than then not no do does did have has had will would can could should may might about into also just very more some what which who how when where why yes yeah okay ok right think need going want let us".split())
LINE = re.compile(r"^\s*(?:\[?(\d{1,2}:\d{2})\]?\s*)?([A-Z][A-Za-z.' -]{0,30}?)\s*:\s*(.+)$")
DECISION = re.compile(r"\b(we(?:'ve| have)? decided|decision is|we(?:'ll| will) go with|let'?s go with|agreed|we agree|approved|final call|settled on|going forward we)\b", re.I)
ACTION = re.compile(r"\b(action item|will (?:send|prepare|share|review|update|follow|check|create|draft|schedule|finish|fix|write|build|call|email)|i'?ll |i will |needs? to|need to|should |can you|could you|please (?:send|prepare|share|review|update|check)|responsible for|take care of|todo|to-do)\b", re.I)
DEADLINE = re.compile(r"\b(by (?:end of (?:day|week|month)|eod|eow|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|next \w+|\d{1,2}(?:st|nd|rd|th)?(?: of)? \w+|\w+ \d{1,2}(?:st|nd|rd|th)?)|(?:next|this) (?:week|month|monday|tuesday|wednesday|thursday|friday|sprint)|tomorrow|today|tonight|end of (?:day|week|month)|within \d+ \w+)\b", re.I)
POS = set("great good excellent happy agree progress success well love perfect improved".split()); NEG = set("problem issue delay delayed blocked risk concern fail failed bug worry late behind difficult".split())

def parse(text):
    """-> [{time, speaker, text}]. Unlabeled lines get speaker 'Unknown'."""
    out = []
    for ln in text.splitlines():
        if not ln.strip(): continue
        m = LINE.match(ln)
        if m and len(m.group(2).split()) <= 4: out.append({"time": m.group(1), "speaker": m.group(2).strip(), "text": m.group(3).strip()})
        else: out += [{"time": None, "speaker": "Unknown", "text": s} for s in re.split(r"(?<=[.!?])\s+", ln.strip()) if s]
    return out
def toks(t): return [w for w in re.findall(r"[a-z][a-z'-]+", t.lower()) if w not in STOP and len(w) > 2]
def split_sents(u): return [(x["speaker"], s.strip()) for x in u for s in re.split(r"(?<=[.!?])\s+", x["text"]) if len(s.split()) >= 3]

def keywords(text, n=10):
    t = toks(text); c = Counter(t); c.update({f"{a} {b}": v * 1.8 for (a, b), v in Counter(zip(t, t[1:])).items() if v >= 2})
    return [w for w, _ in c.most_common(n)]
def summary(u, k=4):
    ss = [x for x in split_sents(u) if not x[1].endswith("?") and len(x[1].split()) >= 6]; kw = Counter(toks(" ".join(s for _, s in ss)))
    sc = sorted(((sum(kw[w] for w in toks(s)) / math.sqrt(len(s.split())), i) for i, (_, s) in enumerate(ss)), reverse=True)[:k]
    return " ".join(ss[i][1] for _, i in sorted(sc, key=lambda x: x[1]))
def decisions(u): return [{"text": s, "by": sp} for sp, s in split_sents(u) if DECISION.search(s)]

def action_items(u, speakers):
    names = [s for s in speakers if s != "Unknown"]; out = []; prev = None
    for x in u:
        for s in re.split(r"(?<=[.!?])\s+", x["text"]):
            sp = x["speaker"]
            if len(s.split()) < 3 or s.lower().startswith("today we") or not ACTION.search(s): continue
            ask = re.search(r"can you|could you|please", s, re.I)
            if s.endswith("?") and not ask: continue
            if DECISION.search(s) and not re.search(r"\bwill\b|need", s, re.I): continue
            named = next((n for n in names if re.search(rf"\b{re.escape(n.split()[0])}\b", s)), None)
            if re.search(r"\bI(?:'ll| will)\b", s): owner = sp
            elif named: owner = named
            elif ask and prev and prev != sp: owner = prev
            else: owner = sp
            d = DEADLINE.search(s); out.append({"task": s.strip(), "owner": owner, "deadline": d.group(0) if d else None, "done": False})
        prev = x["speaker"]
    return out
def questions(u): return [s for _, s in split_sents(u) if s.endswith("?")][:8]
def speaking(u):
    w = defaultdict(int)
    for x in u: w[x["speaker"]] += len(x["text"].split())
    tot = sum(w.values()) or 1; return [{"speaker": k, "words": v, "share": round(v * 100 / tot)} for k, v in sorted(w.items(), key=lambda x: -x[1])]
def sentiment(text):
    t = re.findall(r"[a-z]+", text.lower()); p, n = sum(w in POS for w in t), sum(w in NEG for w in t)
    return "Positive" if p > n + 1 else "Concerned" if n > p + 1 else "Neutral"
def analyze(text):
    u = parse(text); sp = speaking(u); full = " ".join(x["text"] for x in u)
    return {"summary": summary(u), "decisions": decisions(u), "actions": action_items(u, [s["speaker"] for s in sp]), "questions": questions(u),
            "topics": keywords(full), "speakers": sp, "sentiment": sentiment(full), "words": len(full.split())}
