# 🏆 GlobalBoard — Self-Hosted Leaderboard System

No Firebase. No database. No backend setup. Just deploy to Vercel and go.

---

## 📁 File Structure

```
globalboard/
├── api/
│   └── leaderboard.py   ← Python serverless backend
├── index.html           ← Dashboard (create & manage boards)
├── widget.html          ← Public embeddable widget
├── vercel.json          ← Vercel routing config
├── requirements.txt     ← (empty, no deps needed)
└── README.md
```

---

## 🚀 Deploy to Vercel (5 minutes)

### Option A — Vercel CLI
```bash
npm i -g vercel
cd globalboard
vercel
# Follow prompts → your URL will be e.g. https://globalboard.vercel.app
```

### Option B — GitHub + Vercel Dashboard
1. Push this folder to a GitHub repo
2. Go to https://vercel.com → New Project → Import repo
3. Framework: **Other**
4. Click Deploy ✅

### After deploy — update API URL in index.html
The `API` variable at the top of `index.html` and `widget.html` scripts auto-uses
`window.location.origin` so **no changes needed** after deploy.

---

## 🔌 How It Works

| Layer | Tech |
|-------|------|
| Backend | Python `BaseHTTPRequestHandler` (Vercel serverless) |
| Storage | `/tmp/*.json` files on Vercel (per-request, ephemeral note below) |
| Frontend | Vanilla HTML/CSS/JS, no frameworks |
| Auth | SHA-256 password hash per board |

> ⚠️ **Storage Note:** Vercel's `/tmp` is ephemeral — data persists between warm 
> invocations but may reset on cold starts or redeployments. For persistent storage,
> swap `_load`/`_save` in `leaderboard.py` to use any KV store:
> - **Vercel KV** (Redis) — recommended
> - **PlanetScale** (MySQL)
> - **Supabase** (Postgres)
> The API interface stays identical.

---

## 📡 API Reference

### Create Board (POST)
```
POST /api/leaderboard?action=create
{ board_id, password, title, description }
```

### Submit Score (POST) — public, no password
```
POST /api/leaderboard?action=submit
{ board_id, name, score, country }
```
- Same name → only updates if new score is higher (no duplicates)
- Returns rank on leaderboard

### Get Leaderboard (GET) — public
```
GET /api/leaderboard?action=get&board_id=xxx&limit=50
GET /api/leaderboard?action=get&board_id=xxx&country=IN
GET /api/leaderboard?action=get&board_id=xxx&search=name
```

### Delete Player (POST) — password required
```
POST /api/leaderboard?action=delete_player
{ board_id, password, name }
```

### Clear All Scores (POST) — password required
```
POST /api/leaderboard?action=clear
{ board_id, password }
```

### Delete Board (POST) — password required
```
POST /api/leaderboard?action=delete_board
{ board_id, password }
```

### Update Settings (POST) — password required
```
POST /api/leaderboard?action=update_settings
{ board_id, password, title, description, new_password }
```

### Verify Password (POST)
```
POST /api/leaderboard?action=verify
{ board_id, password }
```

---

## 🎮 Embed on Any Website

### iFrame (simplest)
```html
<iframe
  src="https://your-app.vercel.app/widget?board=YOUR_BOARD_ID"
  width="100%" height="500"
  frameborder="0"
  style="border-radius:12px">
</iframe>
```

### JavaScript Score Submit
```javascript
await fetch("https://your-app.vercel.app/api/leaderboard?action=submit", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    board_id: "YOUR_BOARD_ID",
    name:     "PlayerName",
    score:    4200,
    country:  "IN"
  })
});
```

### Python Score Submit
```python
import requests
requests.post("https://your-app.vercel.app/api/leaderboard",
  params={"action": "submit"},
  json={"board_id": "YOUR_BOARD_ID", "name": "Player", "score": 4200, "country": "IN"}
)
```

---

## 🔐 Security Model

- Boards are **public for viewing and score submission**
- Only the password holder can **delete players, clear scores, or delete the board**
- Passwords stored as **SHA-256 hashes** — never plaintext
- Each board_id is sanitized (alphanumeric + `-_` only)

---

## 🔧 Upgrading Storage to Vercel KV (Recommended for Production)

Install: `pip install vercel-kv` or use REST API.

In `leaderboard.py`, replace `_load` and `_save`:

```python
import os, json, requests

KV_URL   = os.environ["KV_REST_API_URL"]
KV_TOKEN = os.environ["KV_REST_API_TOKEN"]

def _load(bid):
    r = requests.get(f"{KV_URL}/get/{_sid(bid)}", headers={"Authorization": f"Bearer {KV_TOKEN}"})
    val = r.json().get("result")
    return json.loads(val) if val else None

def _save(bid, data):
    requests.post(f"{KV_URL}/set/{_sid(bid)}", 
        headers={"Authorization": f"Bearer {KV_TOKEN)"},
        json={"value": json.dumps(data)})
```

Set `KV_REST_API_URL` and `KV_REST_API_TOKEN` in Vercel environment variables.

---

Built with ❤️ — No Firebase, No Backend Hassle.
