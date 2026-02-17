"""
Competitor Intelligence Dashboard - FIXED VERSION
Fixes:
  1. get_connection() used correctly as context manager
  2. JS served inline (no external app.js file needed)
  3. HTML template fully populated
  4. PDF generation working
  5. Removed flask_wtf CSRF (optional dep causing issues)
"""

from flask import Flask, render_template_string, jsonify, request, Response
import yaml
import io
import os
import secrets
import logging
from logging.handlers import RotatingFileHandler
from database import CompetitorDB
from scraper import CompetitorScraper
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from urllib.parse import urlparse
import re

# ============================================================
# LOGGING
# ============================================================
def setup_logging():
    logger = logging.getLogger('competitor_dashboard')
    logger.setLevel(logging.INFO)
    os.makedirs('logs', exist_ok=True)
    fh = RotatingFileHandler('logs/dashboard.log', maxBytes=10*1024*1024, backupCount=5)
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(fmt); ch.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(ch)
    return logger

logger = setup_logging()

# ============================================================
# APP SETUP
# ============================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

config_path = os.environ.get('CONFIG_PATH', 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
logger.info(f"Configuration loaded from {config_path}")

db = CompetitorDB()
scraper = CompetitorScraper()
logger.info("Database and scraper initialized successfully")

# ============================================================
# CONSTANTS & VALIDATION
# ============================================================
DEFAULT_CHANGE_LIMIT = 50
DEFAULT_DAYS_LOOKBACK = 30
MAX_PAGES_PER_COMPETITOR = 50

def validate_url(url):
    if not url or not isinstance(url, str): return False
    try:
        r = urlparse(url)
        return all([r.scheme in ['http', 'https'], r.netloc, len(url) <= 2048])
    except: return False

def validate_competitor_name(name):
    if not name or not isinstance(name, str): return False
    if len(name) < 2 or len(name) > 100: return False
    return bool(re.match(r'^[a-zA-Z0-9\s\.\-&\(\)]+$', name))

def validate_page_type(t):
    return t in ['pricing', 'features', 'blog', 'other']

def sanitize_string(s, max_length=1000):
    return str(s).strip()[:max_length] if s else ''


# ============================================================
# JAVASCRIPT - raw string, zero escaping issues
# ============================================================
APP_JS = r"""
function showPane(id, btn) {
    document.querySelectorAll('.pane').forEach(function(p) { p.classList.remove('active'); });
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    document.getElementById(id).classList.add('active');
    if (btn) btn.classList.add('active');
}
function toast(msg, dur) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(function() { t.classList.remove('show'); }, dur || 3000);
}
function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }
function filterComps() {
    var s = document.getElementById('comp-search').value.toLowerCase();
    document.querySelectorAll('.comp-row').forEach(function(r) {
        r.style.display = r.dataset.name.toLowerCase().includes(s) ? '' : 'none';
    });
}
function filterChanges() {
    var s = document.getElementById('ch-search').value.toLowerCase();
    document.querySelectorAll('.change-row').forEach(function(r) {
        var match = r.dataset.comp.toLowerCase().includes(s) || r.dataset.desc.toLowerCase().includes(s);
        r.style.display = match ? '' : 'none';
    });
}
function makeTypeSelect(selected) {
    var fg = document.createElement('div'); fg.className = 'fg';
    var lbl = document.createElement('label'); lbl.textContent = 'Type *';
    var sel = document.createElement('select'); sel.className = 'p-type'; sel.required = true;
    ['pricing','features','blog','other'].forEach(function(v) {
        var opt = document.createElement('option');
        opt.value = v; opt.textContent = v.charAt(0).toUpperCase()+v.slice(1);
        if (v === selected) opt.selected = true;
        sel.appendChild(opt);
    });
    fg.appendChild(lbl); fg.appendChild(sel); return fg;
}
function addPageBlock(containerId) {
    var c = document.getElementById(containerId);
    var n = c.querySelectorAll('.page-block').length + 1;
    var block = document.createElement('div'); block.className = 'page-block';
    var header = document.createElement('div'); header.className = 'page-block-header';
    var title = document.createElement('span'); title.textContent = 'Page ' + n;
    header.appendChild(title);
    var rb = document.createElement('button'); rb.type = 'button'; rb.className = 'btn sm red'; rb.textContent = 'Remove';
    rb.onclick = function() { block.remove(); };
    header.appendChild(rb); block.appendChild(header);
    var urlFg = document.createElement('div'); urlFg.className = 'fg'; urlFg.innerHTML = '<label>URL *</label>';
    var urlInp = document.createElement('input'); urlInp.type = 'url'; urlInp.className = 'p-url';
    urlInp.placeholder = 'https://example.com/pricing'; urlInp.required = true;
    urlFg.appendChild(urlInp); block.appendChild(urlFg);
    block.appendChild(makeTypeSelect('pricing'));
    var selFg = document.createElement('div'); selFg.className = 'fg'; selFg.innerHTML = '<label>CSS Selector (optional)</label>';
    var selInp = document.createElement('input'); selInp.type = 'text'; selInp.className = 'p-sel';
    selInp.placeholder = 'Leave empty for automatic';
    selFg.appendChild(selInp); block.appendChild(selFg);
    c.appendChild(block);
}
function readPages(containerId) {
    var pages = [];
    document.querySelectorAll('#' + containerId + ' .page-block').forEach(function(b) {
        var urlEl = b.querySelector('.p-url'), typeEl = b.querySelector('.p-type'), selEl = b.querySelector('.p-sel');
        if (urlEl && urlEl.value) pages.push({ url:urlEl.value, type:typeEl?typeEl.value:'other', selector:selEl?selEl.value:'' });
    });
    return pages;
}
function addComp(e) {
    e.preventDefault();
    fetch('/api/competitors', { method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ name:document.getElementById('c-name').value, website:document.getElementById('c-website').value, pages:readPages('add-pages') })
    }).then(function(r){return r.json()}).then(function(d){
        var el = document.getElementById('add-msg');
        el.textContent = d.message; el.className = 'alert ' + (d.success?'ok':'err');
        if (d.success) setTimeout(function(){location.reload();},1200);
    }).catch(function(){toast('Request failed');});
}
function viewComp(name) {
    fetch('/api/competitor?name='+encodeURIComponent(name)).then(function(r){return r.json()}).then(function(d){
        if (d.error) { toast('Error: '+d.error); return; }
        var body = document.getElementById('view-body'); body.innerHTML = '';
        var site = document.createElement('p'); site.style.cssText='margin-bottom:1rem;color:#666';
        site.innerHTML = 'Website: <a href="'+(d.website||'#')+'" target="_blank" style="color:#667eea">'+(d.website||'Not set')+'</a>';
        body.appendChild(site);
        var h = document.createElement('h3'); h.textContent='Tracked Pages'; h.style.marginBottom='.75rem';
        body.appendChild(h);
        (d.pages||[]).forEach(function(p) {
            var block = document.createElement('div');
            block.style.cssText='background:#f8f9fa;padding:.75rem 1rem;border-radius:6px;margin-bottom:.5rem';
            var badge = document.createElement('span'); badge.className='badge '+(p.type||'other'); badge.textContent=p.type||'other';
            block.appendChild(badge);
            var link = document.createElement('a'); link.href=p.url; link.target='_blank';
            link.style.cssText='color:#667eea;font-size:.88rem;word-break:break-all'; link.textContent=' '+p.url;
            block.appendChild(link);
            if (p.selector) { var sd=document.createElement('div'); sd.style.cssText='font-size:.78rem;color:#999;margin-top:.25rem'; sd.textContent='Selector: '+p.selector; block.appendChild(sd); }
            body.appendChild(block);
        });
        openModal('view-overlay');
    }).catch(function(){toast('Error loading details');});
}
function editComp(name) {
    fetch('/api/competitor?name='+encodeURIComponent(name)).then(function(r){return r.json()}).then(function(d){
        if (d.error) { toast('Error: '+d.error); return; }
        document.getElementById('e-orig').value = name;
        document.getElementById('e-name').value = d.name;
        document.getElementById('e-website').value = d.website||'';
        var container = document.getElementById('edit-pages'); container.innerHTML='';
        (d.pages||[]).forEach(function(p,i){
            var block=document.createElement('div'); block.className='page-block';
            var header=document.createElement('div'); header.className='page-block-header';
            var title=document.createElement('span'); title.textContent='Page '+(i+1); header.appendChild(title);
            if (i>0) { var rb=document.createElement('button'); rb.type='button'; rb.className='btn sm red'; rb.textContent='Remove'; rb.onclick=function(){block.remove();}; header.appendChild(rb); }
            block.appendChild(header);
            var urlFg=document.createElement('div'); urlFg.className='fg'; urlFg.innerHTML='<label>URL *</label>';
            var urlInp=document.createElement('input'); urlInp.type='url'; urlInp.className='p-url'; urlInp.value=p.url||''; urlInp.required=true;
            urlFg.appendChild(urlInp); block.appendChild(urlFg);
            block.appendChild(makeTypeSelect(p.type));
            var selFg=document.createElement('div'); selFg.className='fg'; selFg.innerHTML='<label>CSS Selector (optional)</label>';
            var selInp=document.createElement('input'); selInp.type='text'; selInp.className='p-sel'; selInp.value=p.selector||''; selInp.placeholder='Leave empty for automatic';
            selFg.appendChild(selInp); block.appendChild(selFg);
            container.appendChild(block);
        });
        openModal('edit-overlay');
    }).catch(function(){toast('Error loading competitor');});
}
function saveEdit(e) {
    e.preventDefault();
    var orig=document.getElementById('e-orig').value;
    fetch('/api/competitor?name='+encodeURIComponent(orig), { method:'PUT', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({ original_name:orig, name:document.getElementById('e-name').value, website:document.getElementById('e-website').value, pages:readPages('edit-pages') })
    }).then(function(r){return r.json()}).then(function(d){
        toast(d.message);
        if (d.success) { closeModal('edit-overlay'); setTimeout(function(){location.reload();},900); }
    }).catch(function(){toast('Error saving');});
}
var _delTarget=null;
function confirmDelete(name) { _delTarget=name; document.getElementById('del-name').textContent='"'+name+'"'; openModal('del-overlay'); }
document.addEventListener('DOMContentLoaded',function(){
    document.getElementById('del-confirm-btn').addEventListener('click',function(){
        if (!_delTarget) return;
        var n=_delTarget, btn=this;
        btn.textContent='Deleting...'; btn.disabled=true;
        fetch('/api/competitor?name='+encodeURIComponent(n),{method:'DELETE'}).then(function(r){return r.json()}).then(function(d){
            closeModal('del-overlay'); toast(d.message);
            if (d.success) setTimeout(function(){location.reload();},900);
        }).catch(function(){toast('Error deleting');}).finally(function(){btn.textContent='Delete';btn.disabled=false;_delTarget=null;});
    });
});
function runScraper(btn) {
    btn.disabled=true; btn.textContent='Running...'; toast('Scraper started...',5000);
    fetch('/api/scrape',{method:'POST'}).then(function(r){return r.json()}).then(function(d){
        toast('Done! '+d.changes_detected+' change(s)',4000);
        var b=document.getElementById('scrape-banner'); b.textContent='Scraping complete - '+d.changes_detected+' change(s) detected.'; b.classList.add('show');
        btn.textContent='Done!'; setTimeout(function(){location.reload();},2000);
    }).catch(function(){toast('Scraper error');btn.disabled=false;btn.textContent='Run Scraper Now';});
}
"""

# ============================================================
# HTML TEMPLATE
# ============================================================
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<title>Competitor Intelligence Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f7fa;color:#2c3e50}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:2rem}
.header h1{font-size:1.8rem;margin-bottom:.25rem}
.header p{opacity:.85;font-size:.95rem}
.tabs{background:#fff;display:flex;box-shadow:0 2px 4px rgba(0,0,0,.1);position:sticky;top:0;z-index:100}
.tab{padding:1rem 2rem;cursor:pointer;border:none;background:#fff;color:#7f8c8d;font-size:.95rem;font-weight:600;border-bottom:3px solid transparent;transition:.2s}
.tab:hover{background:#f8f9fa;color:#667eea}
.tab.active{color:#667eea;border-bottom-color:#667eea}
.container{max-width:1100px;margin:0 auto;padding:2rem}
.pane{display:none}.pane.active{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1.5rem;margin-bottom:2rem}
.card{background:#fff;padding:1.5rem;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.07)}
.card h3{font-size:.8rem;color:#95a5a6;text-transform:uppercase;letter-spacing:.5px;margin-bottom:.5rem}
.card .val{font-size:2.2rem;font-weight:700;color:#667eea}
.card .val.sm{font-size:1.2rem;padding-top:.4rem}
.box{background:#fff;border-radius:12px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.07)}
.box h2{margin-bottom:1.25rem;font-size:1.3rem}
.actions{display:flex;gap:.75rem;flex-wrap:wrap;margin-bottom:1.25rem}
.btn{display:inline-block;background:#667eea;color:#fff;border:none;padding:.65rem 1.3rem;border-radius:8px;font-size:.9rem;font-weight:600;cursor:pointer;transition:.2s;text-decoration:none}
.btn:hover{background:#5568d3}
.btn.sm{padding:.4rem .85rem;font-size:.82rem}
.btn.red{background:#e74c3c}.btn.red:hover{background:#c0392b}
.btn.grey{background:#95a5a6}.btn.grey:hover{background:#7f8c8d}
.btn.green{background:#27ae60}.btn.green:hover{background:#219a52}
.btn:disabled{opacity:.6;cursor:not-allowed}
input,select{width:100%;padding:.7rem .9rem;border:2px solid #e0e0e0;border-radius:8px;font-size:.95rem;font-family:inherit;transition:.2s}
input:focus,select:focus{outline:none;border-color:#667eea}
label{display:block;font-weight:600;font-size:.88rem;margin-bottom:.4rem;color:#555}
.fg{margin-bottom:1.2rem}
.page-block{background:#f8f9fa;border:1px solid #e8e8e8;border-radius:8px;padding:1rem;margin-bottom:1rem}
.page-block-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem;font-weight:600;font-size:.9rem}
.comp-row{background:#f8f9fa;border-left:4px solid #667eea;border-radius:8px;padding:1.25rem;margin-bottom:.85rem;display:flex;justify-content:space-between;align-items:center;gap:1rem;transition:.2s}
.comp-row:hover{box-shadow:0 3px 10px rgba(0,0,0,.08)}
.comp-info h3{font-size:1.05rem;margin-bottom:.35rem}
.comp-meta{display:flex;gap:1.2rem;font-size:.82rem;color:#888;flex-wrap:wrap}
.btn-group{display:flex;gap:.5rem;flex-shrink:0}
.change-row{border-left:4px solid #667eea;padding:1rem 1.25rem;margin-bottom:.85rem;background:#f8f9fa;border-radius:0 8px 8px 0}
.ch-header{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;margin-bottom:.4rem;flex-wrap:wrap}
.ch-name{font-weight:700;font-size:1rem}
.ch-time{font-size:.78rem;color:#95a5a6;white-space:nowrap}
.badge{display:inline-block;padding:.2rem .6rem;border-radius:20px;font-size:.72rem;font-weight:700;text-transform:uppercase;margin-right:.4rem}
.badge.pricing{background:#e8f5e9;color:#27ae60}
.badge.features{background:#e3f2fd;color:#1565c0}
.badge.blog{background:#fff3e0;color:#e65100}
.badge.other{background:#f3e5f5;color:#6a1b9a}
.ch-desc{font-size:.9rem;color:#444;margin-bottom:.35rem}
.ch-url{font-size:.8rem;color:#667eea;text-decoration:none}
.ch-url:hover{text-decoration:underline}
.search-bar{padding:.7rem 1rem;border:2px solid #e0e0e0;border-radius:8px;font-size:.95rem;width:100%;margin-bottom:1rem}
.search-bar:focus{outline:none;border-color:#667eea}
.empty{text-align:center;padding:3rem;color:#bbb;font-size:.95rem}
.alert{padding:.9rem 1.1rem;border-radius:8px;margin-bottom:1rem;font-size:.9rem;display:none}
.alert.ok{background:#d4edda;color:#155724;border:1px solid #c3e6cb;display:block}
.alert.err{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;display:block}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:500;align-items:center;justify-content:center}
.overlay.open{display:flex}
.modal{background:#fff;border-radius:14px;padding:2rem;width:92%;max-width:680px;max-height:88vh;overflow-y:auto;position:relative}
.modal h2{margin-bottom:1.5rem;font-size:1.25rem}
.modal-close{position:absolute;top:1rem;right:1.25rem;font-size:1.5rem;cursor:pointer;color:#aaa;background:none;border:none;line-height:1}
.modal-close:hover{color:#333}
.toast{position:fixed;bottom:2rem;left:50%;transform:translateX(-50%);background:#1a1a2e;color:#fff;padding:.85rem 1.8rem;border-radius:10px;font-size:.9rem;z-index:9999;opacity:0;transition:opacity .3s;pointer-events:none}
.toast.show{opacity:1}
.banner{padding:1rem 1.25rem;border-radius:8px;margin-bottom:1rem;font-size:.9rem;background:#e8f5e9;color:#1b5e20;border:1px solid #a5d6a7;display:none}
.banner.show{display:block}
</style>
</head>
<body>
<div class="header"><div class="container"><h1>Competitor Intelligence</h1><p>SaaS tracker &mdash; Pricing &middot; Features &middot; Blog</p></div></div>
<div class="tabs">
  <button class="tab active" onclick="showPane('overview',this)">Overview</button>
  <button class="tab" onclick="showPane('competitors',this)">Competitors</button>
  <button class="tab" onclick="showPane('changes',this)">Changes</button>
</div>
<div class="container">
  <div id="overview" class="pane active">
    <div class="grid">
      <div class="card"><h3>Competitors</h3><div class="val">{{ stats.total_competitors }}</div></div>
      <div class="card"><h3>Total Changes</h3><div class="val">{{ stats.total_changes }}</div></div>
      <div class="card"><h3>Last 7 Days</h3><div class="val">{{ stats.recent_changes }}</div></div>
      <div class="card"><h3>Most Active</h3><div class="val sm">{{ stats.most_active_competitor or 'N/A' }}</div></div>
    </div>
    <div class="box"><h2>Actions</h2>
      <div id="scrape-banner" class="banner"></div>
      <div class="actions">
        <button class="btn" onclick="runScraper(this)">Run Scraper Now</button>
        <button class="btn" onclick="window.open('/api/report?days=30')">Download PDF Report</button>
        <button class="btn grey" onclick="location.reload()">Refresh</button>
      </div>
    </div>
  </div>
  <div id="competitors" class="pane">
    <div class="box"><h2>Add Competitor</h2>
      <div id="add-msg" class="alert"></div>
      <form onsubmit="addComp(event)">
        <div class="fg"><label>Competitor Name *</label><input type="text" id="c-name" required placeholder="e.g. Acme Corp"></div>
        <div class="fg"><label>Website</label><input type="url" id="c-website" placeholder="https://example.com"></div>
        <div id="add-pages">
          <div class="page-block">
            <div class="page-block-header"><span>Page 1</span></div>
            <div class="fg"><label>URL *</label><input type="url" class="p-url" required placeholder="https://example.com/pricing"></div>
            <div class="fg"><label>Type *</label><select class="p-type"><option value="pricing">Pricing</option><option value="features">Features</option><option value="blog">Blog</option><option value="other">Other</option></select></div>
            <div class="fg"><label>CSS Selector (optional)</label><input type="text" class="p-sel" placeholder="Leave empty for automatic detection"></div>
          </div>
        </div>
        <div class="actions">
          <button type="button" class="btn grey sm" onclick="addPageBlock('add-pages')">+ Add Page</button>
          <button type="submit" class="btn green">Save Competitor</button>
        </div>
      </form>
    </div>
    <div class="box"><h2>Your Competitors</h2>
      <input class="search-bar" id="comp-search" placeholder="Search competitors..." oninput="filterComps()">
      <div id="comp-list">
        {% if competitors %}
          {% for c in competitors %}
          <div class="comp-row" data-name="{{ c.name }}">
            <div class="comp-info">
              <h3>{{ c.name }}</h3>
              <div class="comp-meta">
                <span>{{ c.page_count }} pages</span>
                <span>{{ c.change_count }} changes</span>
                {% if c.last_scraped %}<span>Last: {{ c.last_scraped[:16] }}</span>{% endif %}
              </div>
            </div>
            <div class="btn-group">
              <button class="btn sm" onclick="viewComp(this.dataset.name)" data-name="{{ c.name }}">View</button>
              <button class="btn sm grey" onclick="editComp(this.dataset.name)" data-name="{{ c.name }}">Edit</button>
              <button class="btn sm red" onclick="confirmDelete(this.dataset.name)" data-name="{{ c.name }}">Delete</button>
            </div>
          </div>
          {% endfor %}
        {% else %}<div class="empty">No competitors yet &mdash; add your first one above!</div>
        {% endif %}
      </div>
    </div>
  </div>
  <div id="changes" class="pane">
    <div class="box"><h2>Recent Changes</h2>
      <input class="search-bar" id="ch-search" placeholder="Search by competitor or description..." oninput="filterChanges()">
      <div id="ch-list">
        {% if changes %}
          {% for ch in changes %}
          <div class="change-row" data-comp="{{ ch.competitor_name }}" data-desc="{{ ch.change_description }}">
            <div class="ch-header">
              <div><span class="ch-name">{{ ch.competitor_name }}</span><span class="badge {{ ch.page_type }}">{{ ch.page_type }}</span></div>
              <span class="ch-time">{{ ch.detected_at[:16] if ch.detected_at else '' }}</span>
            </div>
            <div class="ch-desc">{{ ch.change_description }}</div>
            <a class="ch-url" href="{{ ch.page_url }}" target="_blank">{{ ch.page_url }}</a>
          </div>
          {% endfor %}
        {% else %}<div class="empty">No changes yet &mdash; run the scraper!</div>
        {% endif %}
      </div>
    </div>
  </div>
</div>
<div class="overlay" id="view-overlay">
  <div class="modal"><button class="modal-close" onclick="closeModal('view-overlay')">&times;</button><h2>Competitor Details</h2><div id="view-body"></div></div>
</div>
<div class="overlay" id="edit-overlay">
  <div class="modal"><button class="modal-close" onclick="closeModal('edit-overlay')">&times;</button><h2>Edit Competitor</h2>
    <form onsubmit="saveEdit(event)">
      <input type="hidden" id="e-orig">
      <div class="fg"><label>Name *</label><input type="text" id="e-name" required></div>
      <div class="fg"><label>Website</label><input type="url" id="e-website"></div>
      <div id="edit-pages"></div>
      <div class="actions">
        <button type="button" class="btn grey sm" onclick="addPageBlock('edit-pages')">+ Add Page</button>
        <button type="submit" class="btn green">Save Changes</button>
        <button type="button" class="btn grey sm" onclick="closeModal('edit-overlay')">Cancel</button>
      </div>
    </form>
  </div>
</div>
<div class="overlay" id="del-overlay">
  <div class="modal" style="max-width:400px;text-align:center">
    <button class="modal-close" onclick="closeModal('del-overlay')">&times;</button>
    <h2 style="color:#e74c3c">Delete Competitor</h2>
    <p style="margin:1rem 0 2rem;color:#666">Permanently delete <strong id="del-name"></strong> and all its data.</p>
    <div class="actions" style="justify-content:center">
      <button class="btn grey" onclick="closeModal('del-overlay')">Cancel</button>
      <button class="btn red" id="del-confirm-btn">Delete</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script src="/static/app.js"></script>
</body>
</html>"""


# ============================================================
# ROUTES
# ============================================================
@app.route('/')
def index():
    try:
        stats = db.get_competitor_stats()
        changes = db.get_recent_changes(limit=DEFAULT_CHANGE_LIMIT, days=DEFAULT_DAYS_LOOKBACK)
        try:
            competitors_raw = db.get_all_competitors_from_db()
            competitors = []
            for comp in competitors_raw:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT MAX(scraped_at) FROM snapshots WHERE competitor_name = ?', (comp['name'],))
                    last_scraped = cursor.fetchone()[0]
                    cursor.execute('SELECT COUNT(*) FROM changes WHERE competitor_name = ?', (comp['name'],))
                    change_count = cursor.fetchone()[0]
                competitors.append({'name': comp['name'], 'page_count': len(comp.get('pages', [])), 'last_scraped': last_scraped, 'change_count': change_count})
        except Exception as e:
            logger.warning(f"Using fallback competitors list: {e}")
            competitors = db.get_all_competitors()
        return render_template_string(HTML, stats=stats, changes=changes, competitors=competitors)
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        return f"<h2>Error loading dashboard</h2><pre>{e}</pre>", 500


@app.route('/static/app.js')
def serve_js():
    return Response(APP_JS, mimetype='application/javascript')


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    try:
        n = scraper.scrape_all_competitors()
        return jsonify({'success': True, 'changes_detected': n})
    except Exception as e:
        logger.error(f"Scraping error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e), 'changes_detected': 0}), 500


@app.route('/api/report')
def api_report():
    try:
        days = request.args.get('days', DEFAULT_DAYS_LOOKBACK, type=int)
        if days < 1 or days > 365:
            return "Invalid days parameter", 400
        changes = db.get_recent_changes(limit=200, days=days)
        pdf_bytes = generate_pdf_report(changes, days)
        return Response(pdf_bytes, mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=competitor-report-{datetime.now().strftime("%Y-%m-%d")}.pdf'})
    except Exception as e:
        logger.error(f"Report error: {e}", exc_info=True)
        return "Failed to generate report", 500


@app.route('/api/competitors', methods=['POST'])
def api_add():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        name = sanitize_string(data.get('name', '')).strip()
        if not validate_competitor_name(name):
            return jsonify({'success': False, 'message': 'Invalid competitor name (2-100 chars)'}), 400
        website = sanitize_string(data.get('website', '')).strip()
        if website and not validate_url(website):
            return jsonify({'success': False, 'message': 'Invalid website URL'}), 400
        pages = data.get('pages', [])
        if not isinstance(pages, list) or len(pages) == 0:
            return jsonify({'success': False, 'message': 'At least one page is required'}), 400
        validated_pages = []
        for idx, page in enumerate(pages):
            page_url = sanitize_string(page.get('url', '')).strip()
            if not validate_url(page_url):
                return jsonify({'success': False, 'message': f'Invalid URL for page {idx+1}'}), 400
            page_type = page.get('type', 'other')
            if not validate_page_type(page_type):
                return jsonify({'success': False, 'message': f'Invalid page type for page {idx+1}'}), 400
            validated_pages.append({'url': page_url, 'type': page_type, 'selector': sanitize_string(page.get('selector', ''), max_length=500)})
        success = db.add_competitor(name, website, validated_pages)
        if success:
            return jsonify({'success': True, 'message': f'"{name}" added successfully!'})
        else:
            return jsonify({'success': False, 'message': f'"{name}" already exists'})
    except Exception as e:
        logger.error(f"Error adding competitor: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/api/competitor')
def api_get():
    name = request.args.get('name', '')
    if not name:
        return jsonify({'error': 'Name parameter required'}), 400
    try:
        comp = db.get_competitor_by_name(name)
        if comp:
            return jsonify(comp)
        pages = db.get_competitor_pages(name)
        return jsonify({'name': name, 'website': '', 'pages': pages})
    except Exception as e:
        logger.error(f"Error getting competitor {name}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/competitor', methods=['PUT'])
def api_update():
    name = request.args.get('name', '')
    if not name:
        return jsonify({'success': False, 'message': 'Name parameter required'}), 400
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        orig = sanitize_string(data.get('original_name', name))
        new_name = sanitize_string(data.get('name', '')).strip()
        if not validate_competitor_name(new_name):
            return jsonify({'success': False, 'message': 'Invalid competitor name'}), 400
        website = sanitize_string(data.get('website', '')).strip()
        if website and not validate_url(website):
            return jsonify({'success': False, 'message': 'Invalid website URL'}), 400
        pages = data.get('pages', [])
        if not isinstance(pages, list) or len(pages) == 0:
            return jsonify({'success': False, 'message': 'At least one page required'}), 400
        validated_pages = []
        for page in pages:
            if not validate_url(page.get('url', '')):
                return jsonify({'success': False, 'message': 'Invalid page URL'}), 400
            if not validate_page_type(page.get('type', '')):
                return jsonify({'success': False, 'message': 'Invalid page type'}), 400
            validated_pages.append({'url': page['url'], 'type': page['type'], 'selector': sanitize_string(page.get('selector', ''), max_length=500)})
        success = db.update_competitor(orig, new_name, website, validated_pages)
        if success:
            return jsonify({'success': True, 'message': f'"{new_name}" updated!'})
        else:
            return jsonify({'success': False, 'message': 'Competitor not found'})
    except Exception as e:
        logger.error(f"Error updating competitor: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/api/competitor', methods=['DELETE'])
def api_delete():
    name = request.args.get('name', '')
    if not name:
        return jsonify({'success': False, 'message': 'Name parameter required'}), 400
    try:
        success = db.delete_competitor_from_db(name)
        if success:
            return jsonify({'success': True, 'message': f'"{name}" deleted.'})
        else:
            return jsonify({'success': False, 'message': f'"{name}" not found.'})
    except Exception as e:
        logger.error(f"Error deleting competitor: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Internal server error'}), 500


@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})


@app.errorhandler(404)
def not_found(e): return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(e): return jsonify({'error': 'Internal server error'}), 500


# ============================================================
# PDF GENERATION
# ============================================================
def generate_pdf_report(changes, days=30):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch)
    PURPLE = colors.HexColor('#667eea')
    LIGHT  = colors.HexColor('#f0f2ff')
    GREY   = colors.HexColor('#e0e0e0')
    LINE   = colors.HexColor('#f0f0f0')
    TYPE_COLORS = {
        'pricing':  ('#e8f5e9', '#27ae60'),
        'features': ('#e3f2fd', '#1565c0'),
        'blog':     ('#fff3e0', '#e65100'),
        'other':    ('#f3e5f5', '#6a1b9a'),
    }
    mk = lambda **kw: ParagraphStyle('_', **kw)
    title_st   = mk(fontSize=22, fontName='Helvetica-Bold', textColor=PURPLE, spaceAfter=4)
    sub_st     = mk(fontSize=10, fontName='Helvetica', textColor=colors.HexColor('#7f8c8d'), spaceAfter=16)
    section_st = mk(fontSize=13, fontName='Helvetica-Bold', textColor=colors.HexColor('#2c3e50'), spaceBefore=16, spaceAfter=8)
    desc_st    = mk(fontSize=10, fontName='Helvetica', textColor=colors.HexColor('#2c3e50'), leading=15)
    url_st     = mk(fontSize=8, fontName='Helvetica', textColor=PURPLE)
    footer_st  = mk(fontSize=8, textColor=colors.HexColor('#bbbbbb'), alignment=TA_CENTER)
    count_st   = mk(fontSize=10, fontName='Helvetica', textColor=colors.HexColor('#7f8c8d'), alignment=TA_RIGHT)
    comp_st    = mk(fontSize=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#2c3e50'))
    time_st    = mk(fontSize=8, fontName='Helvetica', textColor=colors.HexColor('#95a5a6'), alignment=TA_RIGHT)
    story = []
    story.append(Paragraph("Competitor Intelligence Report", title_st))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}  |  Period: Last {days} days", sub_st))
    story.append(HRFlowable(width="100%", thickness=2, color=PURPLE, spaceAfter=20))
    if not changes:
        story.append(Paragraph(f"No changes detected in the last {days} days.", mk(fontSize=11, fontName='Helvetica')))
        doc.build(story); return buffer.getvalue()
    by_competitor = {}
    by_type = {}
    for ch in changes:
        by_competitor.setdefault(ch['competitor_name'], []).append(ch)
        by_type[ch['page_type']] = by_type.get(ch['page_type'], 0) + 1
    story.append(Paragraph("Summary", section_st))
    sum_data = [
        ['Total Changes', 'Competitors', 'Pricing', 'Features', 'Blog'],
        [str(len(changes)), str(len(by_competitor)), str(by_type.get('pricing',0)), str(by_type.get('features',0)), str(by_type.get('blog',0))]
    ]
    sum_tbl = Table(sum_data, colWidths=[1.34*inch]*5)
    sum_tbl.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),PURPLE),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,0),8),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('FONTNAME',(0,1),(-1,-1),'Helvetica-Bold'),('FONTSIZE',(0,1),(-1,-1),17),
        ('TEXTCOLOR',(0,1),(-1,-1),colors.HexColor('#2c3e50')),
        ('BACKGROUND',(0,1),(-1,-1),colors.HexColor('#f8f9fa')),
        ('GRID',(0,0),(-1,-1),0.5,GREY),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10),
    ]))
    story.append(sum_tbl); story.append(Spacer(1,20))
    story.append(Paragraph("Detailed Changes", section_st))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY, spaceAfter=12))
    for comp_name, comp_changes in by_competitor.items():
        hdr = Table([[Paragraph(comp_name, comp_st), Paragraph(f"{len(comp_changes)} change{'s' if len(comp_changes)>1 else ''}", count_st)]], colWidths=[5*inch, 2*inch])
        hdr.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('LINEBELOW',(0,0),(-1,-1),2,PURPLE)]))
        story.append(hdr)
        for ch in comp_changes:
            ptype = ch.get('page_type','other')
            bg, fg = TYPE_COLORS.get(ptype, TYPE_COLORS['other'])
            badge = Table([[Paragraph(ptype.upper(), mk(fontSize=7, fontName='Helvetica-Bold', textColor=colors.HexColor(fg)))]],
                colWidths=[0.7*inch], style=TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor(bg)),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
            row = Table([[badge, Paragraph(ch.get('change_description',''), desc_st), Paragraph(str(ch.get('detected_at',''))[:16], time_st)]], colWidths=[0.8*inch, 5*inch, 1.2*inch])
            row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),4),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12)]))
            story.append(row)
            url_row = Table([[Paragraph('',desc_st), Paragraph(ch.get('page_url',''), url_st), Paragraph('',desc_st)]], colWidths=[0.8*inch, 5*inch, 1.2*inch])
            url_row.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),12),('LINEBELOW',(0,0),(-1,-1),0.5,LINE)]))
            story.append(url_row)
        story.append(Spacer(1,14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY, spaceBefore=10))
    story.append(Paragraph("Generated by Competitor Intelligence Dashboard", footer_st))
    doc.build(story)
    return buffer.getvalue()


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    host = config['dashboard'].get('host', '0.0.0.0')
    port = config['dashboard'].get('port', 5000)
    debug = config['dashboard'].get('debug', False)
    logger.info(f"Starting dashboard on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)
