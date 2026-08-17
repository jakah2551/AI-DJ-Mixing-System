"""Local Web UI for the AI DJ Mixing System.

Run with:
    python webui.py
Then open http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file
from werkzeug.utils import secure_filename

from run_pipeline import run_pipeline

BASE_DIR = Path(__file__).resolve().parent
SONGS_DIR = BASE_DIR / "songs"
OUTPUT_DIR = BASE_DIR / "output"
SONGS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"mp3", "wav", "flac", "m4a", "ogg", "aac"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

state = {
    "running": False,
    "stage": "idle",
    "message": "Ready",
    "started_at": None,
    "error": None,
}
state_lock = threading.Lock()


def allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_tracks():
    tracks = []
    for path in sorted(SONGS_DIR.iterdir(), key=lambda p: p.name.lower()):
        if path.is_file() and allowed(path.name):
            tracks.append({
                "name": path.name,
                "size": path.stat().st_size,
            })
    return tracks


def run_job(prompt: str):
    with state_lock:
        state.update(running=True, stage="running", message="Starting AI DJ pipeline…", started_at=time.time(), error=None)
    try:
        run_pipeline(prompt)
        with state_lock:
            state.update(running=False, stage="complete", message="Mix generated successfully", error=None)
    except Exception as exc:
        with state_lock:
            state.update(running=False, stage="error", message="Generation failed", error=str(exc))


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI DJ Mixer</title>
<style>
:root{--bg:#09090b;--panel:#111114;--panel2:#18181c;--line:#29292f;--text:#f5f5f5;--muted:#a1a1aa;--accent:#b8ff3d;--danger:#ff5c7a}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#1d2a12 0,transparent 30%),var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}
.wrap{max-width:1180px;margin:auto;padding:34px 22px 60px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}.brand{font-weight:800;font-size:24px;letter-spacing:-.04em}.badge{font-size:12px;color:var(--accent);border:1px solid #465b22;padding:7px 10px;border-radius:999px;background:#11180a}
.grid{display:grid;grid-template-columns:1.2fr .8fr;gap:18px}.card{background:rgba(17,17,20,.92);border:1px solid var(--line);border-radius:18px;padding:20px;box-shadow:0 18px 50px #0005}.wide{grid-column:1/-1}.label{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin-bottom:10px}.drop{border:1px dashed #52525b;border-radius:14px;padding:28px;text-align:center;cursor:pointer;background:#0e0e11;transition:.15s}.drop:hover,.drop.drag{border-color:var(--accent);background:#14190d}.drop strong{display:block;font-size:17px;margin-bottom:7px}.drop span{color:var(--muted);font-size:13px}.files{margin-top:14px;display:flex;flex-direction:column;gap:8px;max-height:260px;overflow:auto}.file{display:flex;justify-content:space-between;gap:10px;padding:10px 12px;border-radius:10px;background:var(--panel2);font-size:13px}.file small{color:var(--muted)}textarea{width:100%;min-height:135px;resize:vertical;background:#0b0b0e;color:var(--text);border:1px solid var(--line);border-radius:12px;padding:14px;font:inherit;outline:none}textarea:focus{border-color:#6f8f35}.actions{display:flex;gap:10px;align-items:center;margin-top:14px}button{border:0;border-radius:11px;padding:12px 17px;font-weight:750;cursor:pointer;background:var(--accent);color:#101400}button.secondary{background:#242429;color:var(--text);border:1px solid var(--line)}button:disabled{opacity:.45;cursor:not-allowed}.status{display:flex;gap:12px;align-items:center}.dot{width:9px;height:9px;border-radius:50%;background:#71717a}.dot.live{background:var(--accent);box-shadow:0 0 14px var(--accent)}.meter{height:8px;background:#25252a;border-radius:99px;overflow:hidden;margin-top:18px}.bar{height:100%;width:0;background:var(--accent);transition:width .4s}.mix{display:none}.mix audio{width:100%;margin-top:12px}.download{display:inline-block;margin-top:12px;text-decoration:none;color:#111;background:var(--accent);padding:11px 15px;border-radius:10px;font-weight:750}.hint{color:var(--muted);font-size:12px;line-height:1.5}.error{color:var(--danger);white-space:pre-wrap;font-size:12px;margin-top:12px}.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:5px 9px;font-size:11px;color:var(--muted)}@media(max-width:800px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
</head>
<body><div class="wrap">
<div class="top"><div class="brand">🎧 AI DJ Mixer</div><div class="badge">LOCAL WEB UI</div></div>
<div class="grid">
<section class="card">
<div class="label">Music library</div>
<div id="drop" class="drop"><strong>Drop your tracks here</strong><span>MP3, WAV, FLAC, M4A, OGG, AAC · multiple files supported</span><input id="files" type="file" multiple accept="audio/*" hidden></div>
<div id="filesList" class="files"></div>
<div class="actions"><button class="secondary" id="refresh">Refresh library</button><span class="pill" id="count">0 tracks</span></div>
</section>
<section class="card">
<div class="label">DJ request</div>
<textarea id="prompt" placeholder="Create an energetic 10-song set. Start smooth, build the energy progressively and finish with the biggest track."></textarea>
<p class="hint">The prompt is passed to the existing AI DJ pipeline. You can name specific tracks, request genres, BPM progression, energy curves, or say “mix all songs”.</p>
<div class="actions"><button id="generate">🔥 Generate DJ set</button></div>
</section>
<section class="card wide">
<div class="label">Pipeline status</div>
<div class="status"><span id="dot" class="dot"></span><strong id="status">Ready</strong><span id="elapsed" class="pill">—</span></div>
<div class="meter"><div id="bar" class="bar"></div></div>
<div id="error" class="error"></div>
</section>
<section id="mix" class="card wide mix">
<div class="label">Final mix</div>
<strong>mix.mp3</strong>
<audio id="player" controls></audio>
<a class="download" href="/api/download">⬇ Download mix.mp3</a>
</section>
</div></div>
<script>
const $=id=>document.getElementById(id);const drop=$('drop'), input=$('files');
drop.onclick=()=>input.click();['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',e=>upload(e.dataTransfer.files));input.onchange=e=>upload(e.target.files);$('refresh').onclick=load;
async function upload(files){if(!files.length)return;let fd=new FormData();[...files].forEach(f=>fd.append('files',f));$('status').textContent='Uploading tracks…';let r=await fetch('/api/upload',{method:'POST',body:fd});let j=await r.json();if(!r.ok)alert(j.error||'Upload failed');load()}
function fmt(n){if(n<1024)return n+' B';if(n<1048576)return (n/1024).toFixed(1)+' KB';return (n/1048576).toFixed(1)+' MB'}
async function load(){let j=await (await fetch('/api/tracks')).json();$('count').textContent=j.tracks.length+' track'+(j.tracks.length===1?'':'s');$('filesList').innerHTML=j.tracks.map(t=>`<div class="file"><span>${escapeHtml(t.name)}</span><small>${fmt(t.size)}</small></div>`).join('')}
function escapeHtml(s){return s.replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
$('generate').onclick=async()=>{let prompt=$('prompt').value.trim()||'Mix all songs';let r=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt})});let j=await r.json();if(!r.ok){alert(j.error||'Could not start generation');return} $('generate').disabled=true;poll()};
async function poll(){let j=await (await fetch('/api/status')).json();$('status').textContent=j.message;$('dot').className='dot '+(j.running?'live':'');$('error').textContent=j.error||'';let p=j.running?55:(j.stage==='complete'?100:0);$('bar').style.width=p+'%';if(j.started_at)$('elapsed').textContent=Math.max(0,Math.floor(Date.now()/1000-j.started_at))+'s';if(j.stage==='complete'){ $('mix').style.display='block';$('player').src='/api/download?t='+Date.now();$('generate').disabled=false} else if(j.stage==='error')$('generate').disabled=false;else setTimeout(poll,1200)}
load();setInterval(()=>{if(!$('generate').disabled)load()},5000);
</script></body></html>'''


@app.get("/")
def index():
    return render_template_string(HTML)


@app.get("/api/tracks")
def tracks():
    return jsonify({"tracks": get_tracks()})


@app.post("/api/upload")
def upload():
    files = request.files.getlist("files")
    saved = 0
    for file in files:
        if not file.filename or not allowed(file.filename):
            continue
        filename = secure_filename(file.filename)
        if not filename:
            continue
        file.save(SONGS_DIR / filename)
        saved += 1
    if not saved:
        return jsonify({"error": "No supported audio files were uploaded."}), 400
    return jsonify({"saved": saved, "tracks": get_tracks()})


@app.post("/api/generate")
def generate():
    with state_lock:
        if state["running"]:
            return jsonify({"error": "A DJ set is already being generated."}), 409
    data = request.get_json(silent=True) or {}
    prompt = str(data.get("prompt") or "Mix all songs").strip()
    if not get_tracks():
        return jsonify({"error": "Upload at least one audio track first."}), 400
    threading.Thread(target=run_job, args=(prompt,), daemon=True).start()
    return jsonify({"started": True})


@app.get("/api/status")
def status():
    with state_lock:
        return jsonify(dict(state))


@app.get("/api/download")
def download():
    mix = OUTPUT_DIR / "mix.mp3"
    if not mix.exists():
        return jsonify({"error": "No mix has been generated yet."}), 404
    return send_file(mix, as_attachment=True, download_name="mix.mp3", mimetype="audio/mpeg")


if __name__ == "__main__":
    print("\n🎧 AI DJ WebUI")
    print("Open http://127.0.0.1:5000 in your browser.\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
