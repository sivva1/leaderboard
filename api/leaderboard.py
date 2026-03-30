"""
GlobalBoard API — Multi-tenant leaderboard backend
Vercel Serverless Python | No Firebase | /tmp JSON storage

Actions (POST ?action=... or GET ?action=get):
  create          - new board banao (board_id + password)
  submit          - score add/update (public, no password needed)
  get             - leaderboard fetch (public)
  delete_player   - player remove (password required)
  clear           - all scores clear (password required)
  delete_board    - board delete (password required)
  update_settings - title/password change (password required)
  verify          - password check karo
"""

import json, os, hashlib, re, time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DATA_DIR = "/tmp/globalboard"

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}

# ─── helpers ──────────────────────────────────────────────────────────────────

def _mkdir():
    os.makedirs(DATA_DIR, exist_ok=True)

def _sid(bid):
    return re.sub(r"[^a-zA-Z0-9_-]", "", bid)[:40]

def _path(bid):
    return os.path.join(DATA_DIR, f"{_sid(bid)}.json")

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _load(bid):
    p = _path(bid)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)

def _save(bid, data):
    _mkdir()
    with open(_path(bid), "w") as f:
        json.dump(data, f)

def _flag(code):
    if not code or code == "??":
        return "🏳️"
    try:
        return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper()[:2])
    except:
        return "🏳️"

def _rank(scores, limit=100, country=None, search=None):
    pl = list(scores.values())
    if country:
        pl = [p for p in pl if p.get("country","").upper() == country.upper()]
    if search:
        pl = [p for p in pl if search.lower() in p.get("name","").lower()]
    pl.sort(key=lambda p: p["score"], reverse=True)
    total = len(pl)
    pl = pl[:limit]
    for i, p in enumerate(pl):
        p["rank"] = i + 1
        p["flag"] = _flag(p.get("country","??"))
    return pl, total

def ok(body, status=200):
    return status, body

def er(msg, status=400):
    return status, {"success": False, "error": msg}

# ─── actions ──────────────────────────────────────────────────────────────────

def a_create(b):
    bid = (b.get("board_id") or "").strip()
    pw  = (b.get("password") or "").strip()
    ttl = (b.get("title") or "My Leaderboard").strip()[:80]
    dsc = (b.get("description") or "").strip()[:200]
    if not bid:
        return er("board_id is required")
    if not re.match(r"^[a-zA-Z0-9_-]{3,40}$", bid):
        return er("board_id must be 3-40 chars (letters, numbers, _ or -)")
    if len(pw) < 4:
        return er("Password must be at least 4 characters")
    if _load(bid):
        return er("Board ID already taken. Choose another.", 409)
    _save(bid, {
        "board_id": bid, "title": ttl, "description": dsc,
        "password_hash": _hash(pw),
        "created_at": time.time(), "scores": {}
    })
    return ok({"success": True, "message": "Leaderboard created!", "board_id": bid})

def a_submit(b):
    bid  = (b.get("board_id") or "").strip()
    name = (b.get("name") or "").strip()[:50]
    sc   = b.get("score")
    ctr  = (b.get("country") or "??").strip().upper()[:2]
    meta = b.get("meta") or {}
    if not bid or not name:
        return er("board_id and name are required")
    if sc is None:
        return er("score is required")
    try:
        sc = float(sc)
    except:
        return er("score must be a number")
    data = _load(bid)
    if not data:
        return er("Board not found", 404)
    key  = name.lower()
    prev = data["scores"].get(key)
    is_new    = prev is None
    is_higher = prev and sc > prev["score"]
    if is_new or is_higher:
        data["scores"][key] = {
            "name": name, "score": sc, "country": ctr,
            "meta": meta, "submitted_at": time.time()
        }
        _save(bid, data)
    pl, total = _rank(data["scores"])
    rank = next((p["rank"] for p in pl if p["name"].lower() == key), total)
    return ok({
        "success": True,
        "message": "Score submitted!" if is_new else ("Score updated!" if is_higher else "Score unchanged (not higher than existing)."),
        "rank": rank, "total": total,
        "is_new_record": bool(is_higher),
        "previous_score": prev["score"] if prev else None
    })

def a_get(params):
    bid    = (params.get("board_id", [""])[0]).strip()
    limit  = min(int(params.get("limit", ["50"])[0]), 500)
    country= params.get("country", [None])[0]
    search = params.get("search", [None])[0]
    if not bid:
        return er("board_id is required")
    data = _load(bid)
    if not data:
        return er("Board not found", 404)
    pl, total = _rank(data["scores"], limit, country, search)
    return ok({
        "success": True,
        "board_id": bid,
        "title": data.get("title","Leaderboard"),
        "description": data.get("description",""),
        "total": total,
        "players": pl
    })

def _auth(b):
    bid = (b.get("board_id") or "").strip()
    pw  = (b.get("password") or "").strip()
    data = _load(bid)
    if not data:
        return None, er("Board not found", 404)
    if data["password_hash"] != _hash(pw):
        return None, er("Wrong password", 403)
    return data, None

def a_verify(b):
    data, e = _auth(b)
    if e:
        return e
    return ok({"success": True, "title": data["title"], "description": data.get("description",""),
                "board_id": data["board_id"], "player_count": len(data["scores"])})

def a_delete_player(b):
    data, e = _auth(b)
    if e:
        return e
    name = (b.get("name") or "").strip()
    key  = name.lower()
    if key not in data["scores"]:
        return er("Player not found", 404)
    del data["scores"][key]
    _save(data["board_id"], data)
    return ok({"success": True, "message": f"Player '{name}' removed."})

def a_clear(b):
    data, e = _auth(b)
    if e:
        return e
    data["scores"] = {}
    _save(data["board_id"], data)
    return ok({"success": True, "message": "All scores cleared."})

def a_delete_board(b):
    data, e = _auth(b)
    if e:
        return e
    p = _path(data["board_id"])
    if os.path.exists(p):
        os.remove(p)
    return ok({"success": True, "message": "Board deleted permanently."})

def a_update(b):
    data, e = _auth(b)
    if e:
        return e
    ttl  = (b.get("title") or "").strip()[:80]
    dsc  = (b.get("description") or "").strip()[:200]
    npw  = (b.get("new_password") or "").strip()
    if ttl:
        data["title"] = ttl
    data["description"] = dsc
    if npw:
        if len(npw) < 4:
            return er("New password must be at least 4 characters")
        data["password_hash"] = _hash(npw)
    _save(data["board_id"], data)
    return ok({"success": True, "message": "Settings updated."})

# ─── Vercel HTTP handler ───────────────────────────────────────────────────────

DISPATCH_POST = {
    "create":          a_create,
    "submit":          a_submit,
    "verify":          a_verify,
    "delete_player":   a_delete_player,
    "clear":           a_clear,
    "delete_board":    a_delete_board,
    "update_settings": a_update,
}

class handler(BaseHTTPRequestHandler):

    def _send(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        if n == 0:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        action = q.get("action", ["get"])[0]
        if action == "get":
            self._send(*a_get(q))
        else:
            self._send(*er(f"Unknown GET action: {action}"))

    def do_POST(self):
        q      = parse_qs(urlparse(self.path).query)
        action = q.get("action", ["submit"])[0]
        b      = self._body()
        fn = DISPATCH_POST.get(action)
        if not fn:
            self._send(*er(f"Unknown action: {action}"))
        else:
            self._send(*fn(b))

    def do_DELETE(self):
        self._send(*a_delete_board(self._body()))

    def log_message(self, *a):
        pass
