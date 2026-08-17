"""Local Web UI for the AI DJ Mixing System.

Run with:
    python webui.py
Then open http://127.0.0.1:5000
"""
from __future__ import annotations

import json
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
state = {"running": False, "stage": "idle", "message": "Ready", "started_at": None, "error": None, "progress": 0}
state_lock = threading.Lock()


def allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_tracks():
    return [
        {"name": p.name, "size": p.stat().st_size}
        for p in sorted(SONGS_DIR.iterdir(), key=lambda p: p.name.lower())
        if p.is_file() and allowed(p.name)
    ]


def pipeline_progress(percent, stage, message):
    with state_lock:
        state.update(progress=percent, stage=stage, message=message)


def run_job(prompt: str):
    with state_lock:
        state.update(running=True, stage="starting", message="Starting AI DJ pipeline…", started_at=time.time(), error=None, progress=0)
    try:
        run_pipeline(prompt, progress_callback=pipeline_progress)
        with state_lock:
            state.update(running=False, stage="complete", message="Mix generated successfully", error=None, progress=100)
    except Exception as exc:
        with state_lock:
            state.update(running=False, stage="error", message="Generation failed", error=str(exc), progress=0)


def read_json(name):
    path = OUTPUT_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI DJ Mixer</title>
<style>
:root{--bg:#08090b;--panel:#111318;--panel2:#181b21;--line:#292d35;--text:#f7f7f8;--muted:#9299a6;--accent:#b8ff3d;--danger:#ff647c;--blue:#7dd3fc}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#243513 0,transparent 28%),var(--bg);color:var(--text);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}.wrap{max-width:1240px;margin:auto;padding:32px 20px 70px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}.brand{font-weight:850;font-size:25px;letter-spacing:-.05em}.badge,.pill{font-size:11px;color:var(--accent);border:1px solid #40531f;padding:6px 9px;border-radius:999px;background:#11170b}.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}.card{background:rgba(17,19,24,.94);border:1px solid var(--line);border-radius:18px;padding:19px;box-shadow:0 20px 60px #0006}.wide{grid-column:1/-1}.label{font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);margin-bottom:11px}.drop{border:1px dashed #555b66;border-radius:14px;padding:28px;text-align:center;cursor:pointer;background:#0d0f12}.drop.drag{border-color:var(--accent);background:#14190d}.drop strong{display:block;font-size:17px;margin-bottom:7px}.drop span,.hint{color:var(--muted);font-size:12px}.files{margin-top:12px;display:flex;flex-direction:column;gap:7px;max-height:250px;overflow:auto}.file{display:flex;justify-content:space-between;padding:10px 12px;border-radius:10px;background:var(--panel2);font-size:13px}.file small{color:var(--muted)}textarea{width:100%;min-height:135px;resize:vertical;background:#0b0d10;color:var(--text);border:1px solid var(--line);border-radius:12px;padding:14px;font:inherit;outline:0}textarea:focus{border-color:#6f8f35}.actions{display:flex;gap:9px;align-items:center;margin-top:13px}button{border:0;border-radius:10px;padding:12px 16px;font-weight:800;cursor:pointer;background:var(--accent);color:#101400}button.secondary{background:#24272e;color:var(--text);border:1px solid var(--line)}button:disabled{opacity:.45;cursor:not-allowed}.status{display:flex;gap:10px;align-items:center}.dot{width:9px;height:9px;border-radius:50%;background:#626873}.dot.live{background:var(--accent);box-shadow:0 0 15px var(--accent)}.meter{height:9px;background:#252931;border-radius:99px;overflow:hidden;margin-top:17px}.bar{height:100%;width:0;background:var(--accent);transition:width .35s}.error{color:var(--danger);white-space:pre-wrap;font-size:12px;margin-top:12px}.result{display:none}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:14px 0}.stat{background:var(--panel2);padding:12px;border-radius:11px}.stat b{display:block;font-size:18px}.stat span{font-size:10px;color:var(--muted);text-transform:uppercase}.tracklist{display:flex;flex-direction:column;gap:6px;max-height:320px;overflow:auto;margin-top:10px}.track{display:grid;grid-template-columns:34px 1fr auto auto;gap:10px;align-items:center;background:#0d0f13;border:1px solid #20242b;border-radius:10px;padding:9px 11px;font-size:12px}.track .num{color:var(--muted)}.track .meta{color:var(--muted)}audio{width:100%;margin-top:14px}.download{display:inline-block;margin-top:12px;text-decoration:none;color:#111;background:var(--accent);padding:11px 15px;border-radius:10px;font-weight:800}@media(max-width:820px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}.summary{grid-template-columns:repeat(2,1fr)}.track{grid-template-columns:28px 1fr auto}}
</style></head><body><div class="wrap">
<div class="top"><div class="brand">🎧 AI DJ Mixer</div><div class="badge">LOCAL WEB UI</div></div>
<div class="grid">
<section class="card"><div class="label">Music library</div><div id="drop" class="drop"><strong>Drop your tracks here</strong><span>MP3, WAV, FLAC, M4A, OGG, AAC · multiple files</span><input id="files" type="file" multiple accept="audio/*" hidden></div><div id="filesList" class="files"></div><div class="actions"><button class="secondary" id="refresh">Refresh library</button><span class="pill" id="count">0 tracks</span></div></section>
<section class="card"><div class="label">DJ request</div><textarea id="prompt" placeholder="Create an energetic 10-song set. Start smooth, build progressively and finish with the biggest track."></textarea><p class="hint">Describe the set naturally: tracks, artists, genre, BPM, energy, ordering or “mix all songs”.</p><div class="actions"><button id="generate">🔥 Generate DJ set</button></div></section>
<section class="card wide"><div class="label">Pipeline</div><div class="status"><span id="dot" class="dot"></span><strong id="status">Ready</strong><span id="elapsed" class="pill">—</span></div><div class="meter"><div id="bar" class="bar"></div></div><div id="stage" class="hint" style="margin-top:9px"></div><div id="error" class="error"></div></section>
<section id="result" class="card wide result"><div class="label">Mix analysis</div><div class="summary"><div class="stat"><b id="songs">—</b><span>tracks</span></div><div class="stat"><b id="duration">—</b><span>mix duration</span></div><div class="stat"><b id="bpm">—</b><span>BPM range</span></div><div class="stat"><b id="key">—</b><span>keys</span></div></div><div class="label" style="margin-top:18px">Setlist & transition plan</div><div id="tracklist" class="tracklist"></div></section>
<section id="mix" class="card wide result"><div class="label">Final mix</div><strong>mix.mp3</strong><audio id="player" controls></audio><a class="download" href="/api/download">⬇ Download mix.mp3</a></section>
</div></div>
<script>
const $=id=>document.getElementById(id),drop=$('drop'),input=$('files');drop.onclick=()=>input.click();['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));drop.addEventListener('drop',e=>upload(e.dataTransfer.files));input.onchange=e=>upload(e.target.files);$('refresh').onclick=load;
async function upload(files){if(!files.length)return;let fd=new FormData();[...files].forEach(f=>fd.append('files',f));$('status').textContent='Uploading tracks…';let r=await fetch('/api/upload',{method:'POST',body:fd});let j=await r.json();if(!r.ok)alert(j.error||'Upload failed');load()}
function fmt(n){if(n<1024)return n+' B';if(n<1048576)return(n/1024).toFixed(1)+' KB';return(n/1048576).toFixed(1)+' MB'}
function esc(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
async function load(){let j=await(await fetch('/api/tracks')).json();$('count').textContent=j.tracks.length+' track'+(j.tracks.length===1?'':'s');$('filesList').innerHTML=j.tracks.map(t=>`<div class="file"><span>${esc(t.name)}</span><small>${fmt(t.size)}</small></div>`).join('')}
$('generate').onclick=async()=>{let prompt=$('prompt').value.trim()||'Mix all songs';let r=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt})});let j=await r.json();if(!r.ok){alert(j.error||'Could not start generation');return}$('generate').disabled=true;poll()};
async function poll(){let j=await(await fetch('/api/status')).json();$('status').textContent=j.message;$('stage').textContent=j.stage;$('dot').className='dot '+(j.running?'live':'');$('bar').style.width=(j.progress||0)+'%';$('error').textContent=j.error||'';if(j.started_at)$('elapsed').textContent=Math.max(0,Math.floor(Date.now()/1000-j.started_at))+'s';if(j.stage==='complete'){await loadResults();$('generate').disabled=false}else if(j.stage==='error')$('generate').disabled=false;else setTimeout(poll,900)}
async function loadResults(){let j=await(await fetch('/api/results')).json();if(!j.ready)return;$('result').style.display='block';$('mix').style.display='block';$('player').src='/api/stream?t='+Date.now();$('songs').textContent=j.summary.tracks;$('duration').textContent=j.summary.duration;$('bpm').textContent=j.summary.bpm;$('key').textContent=j.summary.keys;$('tracklist').innerHTML=j.tracks.map((t,i)=>`<div class="track"><span class="num">${i+1}</span><strong>${esc(t.title||t.name||'Unknown')}</strong><span class="meta">${esc(t.bpm?Math.round(t.bpm)+' BPM':'')}</span><span class="meta">${esc(t.key||t.genre||'')}</span></div>`).join('')}
load();</script></body></html>'''


@app.get('/')
def index(): return render_template_string(HTML)

@app.get('/api/tracks')
def tracks(): return jsonify({'tracks': get_tracks()})

@app.post('/api/upload')
def upload():
    files=request.files.getlist('files'); saved=0
    for file in files:
        if not file.filename or not allowed(file.filename): continue
        filename=secure_filename(file.filename)
        if filename: file.save(SONGS_DIR/filename); saved+=1
    if not saved: return jsonify({'error':'No supported audio files were uploaded.'}),400
    return jsonify({'saved':saved,'tracks':get_tracks()})

@app.post('/api/generate')
def generate():
    with state_lock:
        if state['running']: return jsonify({'error':'A DJ set is already being generated.'}),409
    data=request.get_json(silent=True) or {}; prompt=str(data.get('prompt') or 'Mix all songs').strip()
    if not get_tracks(): return jsonify({'error':'Upload at least one audio track first.'}),400
    threading.Thread(target=run_job,args=(prompt,),daemon=True).start(); return jsonify({'started':True})

@app.get('/api/status')
def status():
    with state_lock: return jsonify(dict(state))

@app.get('/api/results')
def results():
    basic=read_json('basic_setlist.json') or {}
    analyzed=read_json('analyzed_setlist.json') or {}
    plan=read_json('mixing_plan.json') or {}
    data=basic.get('basic_setlist', basic.get('tracks', basic.get('analyzed_setlist', [])))
    if not isinstance(data,list): data=[]
    if not data and isinstance(analyzed.get('analyzed_setlist'),list): data=analyzed['analyzed_setlist']
    tracks=[]
    for item in data:
        if not isinstance(item,dict): continue
        tracks.append({'title':item.get('title') or item.get('name') or item.get('file'),'name':item.get('file'),'bpm':item.get('bpm'),'key':item.get('key'),'genre':item.get('genre')})
    bpms=[float(t['bpm']) for t in tracks if isinstance(t.get('bpm'),(int,float))]
    keys=[str(t['key']) for t in tracks if t.get('key')]
    mix=OUTPUT_DIR/'mix.mp3'
    if not mix.exists(): return jsonify({'ready':False})
    duration='—'
    try:
        import wave
        if mix.suffix.lower()=='.wav': duration=f'{wave.open(str(mix)).getnframes()/wave.open(str(mix)).getframerate():.0f}s'
    except Exception: pass
    return jsonify({'ready':True,'summary':{'tracks':len(tracks),'duration':duration,'bpm':f'{min(bpms):.0f}–{max(bpms):.0f}' if bpms else '—','keys':len(set(keys)) if keys else '—'},'tracks':tracks,'plan':plan})

@app.get('/api/stream')
def stream():
    mix=OUTPUT_DIR/'mix.mp3'
    if not mix.exists(): return jsonify({'error':'No mix has been generated yet.'}),404
    return send_file(mix,as_attachment=False,mimetype='audio/mpeg')

@app.get('/api/download')
def download():
    mix=OUTPUT_DIR/'mix.mp3'
    if not mix.exists(): return jsonify({'error':'No mix has been generated yet.'}),404
    return send_file(mix,as_attachment=True,download_name='mix.mp3',mimetype='audio/mpeg')

if __name__=='__main__':
    print('\n🎧 AI DJ WebUI\nOpen http://127.0.0.1:5000 in your browser.\n')
    app.run(host='127.0.0.1',port=5000,debug=False)
