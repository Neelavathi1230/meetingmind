import os, sqlite3, hashlib, secrets, json
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
import nlp
BASE = os.path.dirname(os.path.abspath(__file__)); DB = os.path.join(BASE, "..", "database", "meetingmind.db"); UP = os.path.join(BASE, "uploads")
ALLOWED = {".mp3", ".wav", ".m4a", ".webm", ".ogg"}; MAX_MB = 100
app = FastAPI(title="MeetingMind")
def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
with db() as c:
    c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,password_hash TEXT);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INT);
    CREATE TABLE IF NOT EXISTS meetings(id INTEGER PRIMARY KEY,user_id INT,title TEXT,transcript TEXT,source TEXT,analysis TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")
def hp(pw, salt=None):
    salt = salt or secrets.token_hex(8); return salt + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000).hex()
def user(authorization: str = Header(None)):
    r = db().execute("SELECT user_id FROM sessions WHERE token=?", ((authorization or "").replace("Bearer ", ""),)).fetchone()
    if not r: raise HTTPException(401, "Please log in to continue.")
    return r[0]
def own(mid, uid):
    r = db().execute("SELECT * FROM meetings WHERE id=? AND user_id=?", (mid, uid)).fetchone()
    if not r: raise HTTPException(404, "Meeting not found.")
    return r
class Reg(BaseModel): name: str; email: EmailStr; password: str
class Log(BaseModel): email: EmailStr; password: str
class Edit(BaseModel): title: str | None = None; transcript: str | None = None; actions: list | None = None

@app.post("/api/auth/register")
def register(b: Reg):
    if len(b.password) < 8: raise HTTPException(400, "Password must be at least 8 characters.")
    try:
        with db() as c: c.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?)", (b.name.strip(), b.email.lower(), hp(b.password)))
    except sqlite3.IntegrityError: raise HTTPException(400, "An account with this email already exists.")
    return {"ok": True}
@app.post("/api/auth/login")
def login(b: Log):
    r = db().execute("SELECT * FROM users WHERE email=?", (b.email.lower(),)).fetchone()
    if not r or hp(b.password, r["password_hash"].split("$")[0]) != r["password_hash"]: raise HTTPException(401, "Incorrect email or password.")
    t = secrets.token_urlsafe(32)
    with db() as c: c.execute("INSERT INTO sessions VALUES(?,?)", (t, r["id"]))
    return {"token": t, "name": r["name"]}
@app.post("/api/auth/logout")
def logout(authorization: str = Header(None)):
    with db() as c: c.execute("DELETE FROM sessions WHERE token=?", ((authorization or "").replace("Bearer ", ""),))
    return {"ok": True}

DEMO = """Priya: Thanks everyone for joining. Today we need to finalize the launch plan for the mobile app.
Arjun: The backend is mostly ready, but the payment integration is delayed by a week. That is a risk for the launch date.
Priya: Okay. Can you confirm the new timeline with the payment vendor by Friday?
Arjun: Yes, I'll email the vendor tomorrow and share their answer with the team.
Meera: On the design side, the onboarding screens are done. I will send the final assets to engineering by Wednesday.
Priya: Great progress. We have decided to move the launch from the 15th to the 22nd of next month.
Karthik: Should we also delay the marketing campaign?
Priya: Yes, agreed. Karthik, please update the campaign schedule and share it by end of week.
Meera: We need to fix the login bug on Android before the beta release.
Arjun: I'll take care of that this sprint. Anything else? No. Then let's wrap up."""
def transcribe(path):
    try: from faster_whisper import WhisperModel
    except ImportError: return DEMO, "demo"
    segs, _ = WhisperModel("base", compute_type="int8").transcribe(path)
    txt = "\n".join(f"{int(s.start)//60:02d}:{int(s.start)%60:02d} {s.text.strip()}" for s in segs)
    if not txt.strip(): raise ValueError("no speech")
    return txt, "whisper"

@app.post("/api/meetings")
async def create(title: str = Form("Untitled meeting"), transcript: str = Form(""), file: UploadFile | None = File(None), uid: int = Depends(user)):
    src = "text"
    if not transcript.strip():
        if not file: raise HTTPException(400, "Upload a meeting recording or paste a transcript.")
        ext = os.path.splitext(file.filename or "")[1].lower(); data = await file.read()
        if ext not in ALLOWED: raise HTTPException(400, "Unable to process the audio file. Please upload MP3, WAV, M4A, OGG or WEBM.")
        if not data: raise HTTPException(400, "The audio file is empty.")
        if len(data) > MAX_MB * 1048576: raise HTTPException(400, f"File is too large (max {MAX_MB} MB).")
        path = os.path.join(UP, secrets.token_hex(8) + ext); open(path, "wb").write(data)
        try: transcript, src = transcribe(path)
        except Exception: raise HTTPException(500, "Speech could not be detected clearly. Please try a recording with better audio quality.")
        finally:
            try: os.remove(path)
            except OSError: pass
    try: a = nlp.analyze(transcript)
    except Exception: raise HTTPException(500, "Meeting analysis failed. Please try again.")
    with db() as c:
        mid = c.execute("INSERT INTO meetings(user_id,title,transcript,source,analysis) VALUES(?,?,?,?,?)", (uid, title[:200], transcript, src, json.dumps(a))).lastrowid
    return {"id": mid}
@app.get("/api/meetings")
def lst(uid: int = Depends(user)):
    out = []
    for r in db().execute("SELECT * FROM meetings WHERE user_id=? ORDER BY id DESC", (uid,)):
        a = json.loads(r["analysis"]); out.append({"id": r["id"], "title": r["title"], "source": r["source"], "created_at": r["created_at"], "decisions": len(a["decisions"]), "actions": len(a["actions"]), "open": sum(not x["done"] for x in a["actions"])})
    return out
@app.get("/api/meetings/{mid}")
def get(mid: int, uid: int = Depends(user)):
    r = own(mid, uid); return {"id": mid, "title": r["title"], "transcript": r["transcript"], "source": r["source"], "created_at": r["created_at"], "analysis": json.loads(r["analysis"])}
@app.put("/api/meetings/{mid}")
def edit(mid: int, b: Edit, uid: int = Depends(user)):
    r = own(mid, uid); a = json.loads(r["analysis"])
    with db() as c:
        if b.title: c.execute("UPDATE meetings SET title=? WHERE id=?", (b.title[:200], mid))
        if b.transcript: a = nlp.analyze(b.transcript); c.execute("UPDATE meetings SET transcript=? WHERE id=?", (b.transcript, mid))
        if b.actions is not None: a["actions"] = b.actions
        c.execute("UPDATE meetings SET analysis=? WHERE id=?", (json.dumps(a), mid))
    return {"ok": True}
@app.delete("/api/meetings/{mid}")
def delete(mid: int, uid: int = Depends(user)):
    own(mid, uid)
    with db() as c: c.execute("DELETE FROM meetings WHERE id=?", (mid,))
    return {"ok": True}
@app.get("/api/demo-transcript")
def demo(): return {"text": DEMO}
app.mount("/", StaticFiles(directory=os.path.join(BASE, "..", "frontend"), html=True))
