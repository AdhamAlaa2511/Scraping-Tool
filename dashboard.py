"""
WORKING Dashboard - ALL BUGS FIXED
"""

from flask import Flask, render_template_string, jsonify, request
import yaml
from database import CompetitorDB
from scraper import CompetitorScraper
from datetime import datetime

app = Flask(__name__)

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

db = CompetitorDB()
scraper = CompetitorScraper()

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Competitor Intelligence Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; color: #2c3e50; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header h1 { margin-bottom: 0.5rem; }
        .nav-tabs { background: white; display: flex; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .nav-tab { padding: 1rem 2rem; cursor: pointer; border: none; background: white; color: #7f8c8d; font-size: 1rem; font-weight: 600; transition: all 0.3s; border-bottom: 3px solid transparent; }
        .nav-tab:hover { background: #f8f9fa; }
        .nav-tab.active { color: #667eea; border-bottom-color: #667eea; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .stat-card h3 { font-size: 0.875rem; color: #7f8c8d; text-transform: uppercase; margin-bottom: 0.5rem; }
        .stat-card .value { font-size: 2.5rem; font-weight: 700; color: #667eea; }
        .section { background: white; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .section h2 { margin-bottom: 1rem; color: #2c3e50; font-size: 1.5rem; }
        .search-input { width: 100%; padding: 0.75rem 1rem; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1rem; margin-bottom: 1rem; }
        .search-input:focus { outline: none; border-color: #667eea; }
        .competitor-card { background: #f8f9fa; padding: 1.5rem; margin-bottom: 1rem; border-radius: 8px; border-left: 4px solid #667eea; display: flex; justify-content: space-between; align-items: center; }
        .competitor-info h3 { color: #2c3e50; margin-bottom: 0.5rem; }
        .competitor-meta { display: flex; gap: 1rem; font-size: 0.875rem; color: #7f8c8d; }
        .competitor-actions { display: flex; gap: 0.5rem; }
        .button { background: #667eea; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 600; }
        .button:hover { background: #5568d3; }
        .button-small { padding: 0.5rem 1rem; font-size: 0.875rem; }
        .button-danger { background: #e74c3c; }
        .button-danger:hover { background: #c0392b; }
        .form-group { margin-bottom: 1.5rem; }
        .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 600; }
        .form-group input, .form-group select { width: 100%; padding: 0.75rem; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 1rem; }
        .page-entry { background: #f8f9fa; padding: 1rem; margin-bottom: 1rem; border-radius: 8px; }
        .page-entry-header { display: flex; justify-content: space-between; margin-bottom: 1rem; }
        .actions { display: flex; gap: 1rem; margin-bottom: 1rem; }
        .alert { padding: 1rem; border-radius: 8px; margin-bottom: 1rem; }
        .alert-success { background: #d4edda; color: #155724; }
        .alert-error { background: #f8d7da; color: #721c24; }
        .hidden { display: none; }
        .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.5); }
        .modal-content { background-color: white; margin: 5% auto; padding: 2rem; border-radius: 12px; width: 90%; max-width: 800px; max-height: 80vh; overflow-y: auto; }
        .modal-header { display: flex; justify-content: space-between; margin-bottom: 1.5rem; }
        .close { color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close:hover { color: #000; }
        .change-item { border-left: 4px solid #667eea; padding: 1rem; margin-bottom: 1rem; background: #f8f9fa; border-radius: 4px; }
        .toast {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(30, 30, 40, 0.95);
            color: white;
            padding: 1.5rem 2.5rem;
            border-radius: 12px;
            z-index: 2000;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            transition: all 0.3s ease;
            opacity: 0;
            visibility: hidden;
            font-weight: 500;
            min-width: 300px;
        }
        .toast.visible { opacity: 1; visibility: visible; transform: translate(-50%, -50%) scale(1); }
        .toast.success { border-bottom: 4px solid #2ecc71; }
        .toast.error { border-bottom: 4px solid #e74c3c; }
        .toast.info { border-bottom: 4px solid #3498db; }
        .view-content-item { margin-bottom: 0.5rem; border-bottom: 1px solid #eee; padding-bottom: 0.5rem; }
        .view-label { font-weight: 600; color: #7f8c8d; width: 100px; display: inline-block; }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>🔍 Competitor Intelligence Dashboard</h1>
            <p>Track and analyze competitor changes</p>
        </div>
    </div>
    
    <div class="nav-tabs">
        <button class="nav-tab active" onclick="switchTab('overview', this)">📊 Overview</button>
        <button class="nav-tab" onclick="switchTab('competitors', this)">👥 Competitors</button>
        <button class="nav-tab" onclick="switchTab('changes', this)">🔄 Changes</button>
    </div>
    
    <div class="container">
        <div id="overview-tab" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card"><h3>Competitors</h3><div class="value">{{ stats.total_competitors }}</div></div>
                <div class="stat-card"><h3>Changes</h3><div class="value">{{ stats.total_changes }}</div></div>
                <div class="stat-card"><h3>Last 7 Days</h3><div class="value">{{ stats.recent_changes }}</div></div>
                <div class="stat-card"><h3>Most Active</h3><div class="value" style="font-size:1.2rem">{{ stats.most_active_competitor or 'N/A' }}</div></div>
            </div>
            <div class="section">
                <h2>Quick Actions</h2>
                <div class="actions">
                    <button class="button" onclick="runScraper(this)">🔄 Run Scraper</button>
                    <button class="button" onclick="window.open('/api/report?days=30')">📊 Download Report</button>
                    <button class="button" onclick="location.reload()">🔃 Refresh</button>
                </div>
            </div>
        </div>
        
        <div id="competitors-tab" class="tab-content">
            <div class="section">
                <h2>Add Competitor</h2>
                <div id="add-alert" class="hidden"></div>
                <form onsubmit="addCompetitor(event)">
                    <div class="form-group"><label>Name *</label><input type="text" id="comp-name" required></div>
                    <div class="form-group"><label>Website</label><input type="url" id="comp-website"></div>
                    <div id="pages-container">
                        <div class="page-entry">
                            <div class="page-entry-header"><strong>Page 1</strong></div>
                            <div class="form-group"><label>URL *</label><input type="url" class="page-url" required></div>
                            <div class="form-group"><label>Type *</label><select class="page-type"><option value="features">Features</option><option value="pricing">Pricing</option><option value="blog">Blog</option><option value="products">Products</option></select></div>
                            <div class="form-group"><label>CSS Selector (optional)</label><input type="text" class="page-selector" placeholder="Leave empty for auto"></div>
                        </div>
                    </div>
                    <div class="actions">
                        <button type="button" class="button button-small" onclick="addPage()">➕ Add Page</button>
                        <button type="submit" class="button">✅ Save</button>
                    </div>
                </form>
            </div>
            <div class="section">
                <h2>Your Competitors</h2>
                <input type="text" class="search-input" id="search-comp" placeholder="🔍 Search..." onkeyup="searchComp()">
                <div id="comp-list">
                    {% if competitors %}
                        {% for comp in competitors %}
                        <div class="competitor-card" data-name="{{ comp.name }}">
                            <div class="competitor-info">
                                <h3>{{ comp.name }}</h3>
                                <div class="competitor-meta">
                                    <span>📄 {{ comp.page_count }} pages</span>
                                    <span>🔄 {{ comp.change_count }} changes</span>
                                </div>
                            </div>
                            <div class="competitor-actions">
                                <button class="button button-small btn-view" data-name="{{ comp.name }}">👁️ View</button>
                                <button class="button button-small btn-edit" data-name="{{ comp.name }}">✏️ Edit</button>
                                <button class="button button-small button-danger btn-del" data-name="{{ comp.name }}">🗑️ Delete</button>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <p>No competitors yet</p>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <div id="changes-tab" class="tab-content">
            <div class="section">
                <h2>Recent Changes</h2>
                <input type="text" class="search-input" id="search-changes" placeholder="🔍 Search..." onkeyup="searchChanges()">
                <div id="changes-list">
                    {% if changes %}
                        {% for change in changes %}
                        <div class="change-item" data-competitor="{{ change.competitor_name }}" data-description="{{ change.change_description }}">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                <div>
                                    <strong>{{ change.competitor_name }}</strong> - {{ change.page_type }}<br>
                                    {{ change.change_description }}<br>
                                    <small>{{ change.detected_at }}</small>
                                </div>
                                <a href="{{ change.page_url }}" target="_blank" class="button button-small" style="text-decoration: none; margin-left: 1rem;">🔗 Visit</a>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <p>No changes detected</p>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
    
    <div id="edit-modal" class="modal" style="z-index: 1050;">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Edit Competitor</h2>
                <span class="close" onclick="closeEdit()">&times;</span>
            </div>
            <form onsubmit="saveEdit(event)">
                <input type="hidden" id="edit-orig">
                <div class="form-group"><label>Name *</label><input type="text" id="edit-name" required></div>
                <div class="form-group"><label>Website</label><input type="url" id="edit-website"></div>
                <div id="edit-pages"></div>
                <div class="actions">
                    <button type="button" class="button button-small" onclick="addEditPage()">➕ Add Page</button>
                    <button type="submit" class="button">💾 Save</button>
                    <button type="button" class="button button-small" onclick="closeEdit()">Cancel</button>
                </div>
            </form>
        </div>
    </div>

    <div id="view-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Competitor Details</h2>
                <span class="close" onclick="closeView()">&times;</span>
            </div>
            <div id="view-content" style="margin-bottom: 2rem;"></div>
            <div class="actions" style="justify-content: flex-end;">
                <button type="button" class="button" onclick="closeView()">Close</button>
            </div>
        </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div id="delete-modal" class="modal" style="z-index: 1100;">
        <div class="modal-content" style="max-width: 400px; text-align: center;">
            <div class="modal-header" style="justify-content: center; border-bottom: none;">
                <h2 style="color: #e74c3c;">⚠️ Delete Competitor</h2>
            </div>
            <p style="margin-bottom: 2rem; font-size: 1.1rem;">Are you sure you want to delete this competitor?<br>This action cannot be undone.</p>
            <div class="actions" style="justify-content: center; gap: 1rem;">
                <button type="button" class="button secondary" onclick="closeDeleteModal()" style="background: #95a5a6;">Cancel</button>
                <button type="button" class="button button-danger" id="confirm-delete-btn">Delete</button>
            </div>
        </div>
    </div>

    <!-- Toast Notification -->
    <div id="toast" class="toast"></div>
    
    <script>
        function switchTab(n,b){
            document.querySelectorAll('.tab-content').forEach(function(t){t.classList.remove('active')});
            document.querySelectorAll('.nav-tab').forEach(function(t){t.classList.remove('active')});
            document.getElementById(n+'-tab').classList.add('active');
            if(b)b.classList.add('active')
        }
        function searchComp(){var s=document.getElementById('search-comp').value.toLowerCase();document.querySelectorAll('.competitor-card').forEach(function(c){c.style.display=c.dataset.name.toLowerCase().includes(s)?'flex':'none'})}
        function searchChanges(){var s=document.getElementById('search-changes').value.toLowerCase();document.querySelectorAll('.change-item').forEach(function(i){var show=i.dataset.competitor.toLowerCase().includes(s)||i.dataset.description.toLowerCase().includes(s);i.style.display=show?'block':'none'})}
        
        var pageN=1;
        function addPage(){pageN++;var d=document.createElement('div');d.className='page-entry';d.innerHTML='<div class="page-entry-header"><strong>Page '+pageN+'</strong><button type="button" class="button button-small button-danger" onclick="this.parentElement.parentElement.remove()">Remove</button></div><div class="form-group"><label>URL *</label><input type="url" class="page-url" required></div><div class="form-group"><label>Type *</label><select class="page-type"><option value="features">Features</option><option value="pricing">Pricing</option><option value="blog">Blog</option><option value="products">Products</option></select></div><div class="form-group"><label>CSS Selector (optional)</label><input type="text" class="page-selector" placeholder="Leave empty for auto"></div>';document.getElementById('pages-container').appendChild(d)}

        // Helper: Show Toast
        function showToast(msg, type) {
            var t = document.getElementById('toast');
            if(!t) return;
            t.textContent = msg;
            t.className = 'toast ' + (type || 'info');
            t.classList.add('visible');
            setTimeout(function() {
                t.classList.remove('visible');
            }, 3000);
        }

        // Add Competitor
        function addCompetitor(e){
            e.preventDefault();
            var name=document.getElementById('comp-name').value;
            var website=document.getElementById('comp-website').value;
            var pages=[];
            document.querySelectorAll('.page-entry').forEach(function(p){
                pages.push({
                    url:p.querySelector('.page-url').value,
                    type:p.querySelector('.page-type').value,
                    selector:p.querySelector('.page-selector').value||''
                })
            });
            fetch('/api/competitors',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({name:name,website:website,pages:pages})
            })
            .then(function(r){return r.json()})
            .then(function(d){
                showToast(d.message, d.success ? 'success' : 'error');
                if(d.success) setTimeout(function(){location.reload()}, 1500);
            })
            .catch(function(e){showToast('Error: '+e, 'error')});
        }

        // Run Scraper
        function runScraper(btn){
            btn.disabled=true;
            btn.textContent='Running...';
            showToast('Scraper started...', 'info');
            fetch('/api/scrape',{method:'POST'})
            .then(function(r){return r.json()})
            .then(function(d){
                showToast('Done! '+d.changes_detected+' changes detected', 'success');
                setTimeout(function(){location.reload()}, 2000);
            })
            .catch(function(e){
                showToast('Error: '+e, 'error');
                btn.disabled=false;
                btn.textContent='Run Scraper';
            });
        }

        // View Competitor (Modal)
        function viewComp(n){
            fetch('/api/competitors/'+encodeURIComponent(n))
            .then(function(r){return r.json()})
            .then(function(d){
                var html = '<div class="view-content-item"><span class="view-label">Name:</span> <strong>'+d.name+'</strong></div>';
                html += '<div class="view-content-item"><span class="view-label">Pages:</span> '+d.pages.length+' tracked</div>';
                html += '<h3>Tracked Pages</h3>';
                d.pages.forEach(function(p){
                    html += '<div style="background:#f8f9fa; padding:0.5rem; margin-bottom:0.5rem; border-radius:4px;">';
                    html += '<div><strong>'+p.type.toUpperCase()+'</strong></div>';
                    html += '<div style="font-size:0.9rem; color:#666; word-break:break-all;">'+p.url+'</div>';
                    if(p.selector) html += '<div style="font-size:0.8rem; color:#888;">Selector: '+p.selector+'</div>';
                    html += '</div>';
                });
                document.getElementById('view-content').innerHTML = html;
                document.getElementById('view-modal').style.display = 'block';
            })
            .catch(function(e){showToast('Error loading details', 'error')});
        }

        function closeView(){document.getElementById('view-modal').style.display='none'}

        // Delete Competitor
        var competitorToDelete = null;

        function deleteComp(n){
            competitorToDelete = n;
            document.getElementById('delete-modal').style.display = 'flex'; // Centered due to flex in CSS
        }

        function closeDeleteModal() {
            document.getElementById('delete-modal').style.display = 'none';
            competitorToDelete = null;
        }

        document.getElementById('confirm-delete-btn').addEventListener('click', function() {
            if (!competitorToDelete) return;
            
            var n = competitorToDelete;
            // visual feedback
            this.textContent = 'Deleting...';
            this.disabled = true;

            fetch('/api/competitors/'+encodeURIComponent(n),{method:'DELETE'})
            .then(function(r){return r.json()})
            .then(function(d){
                closeDeleteModal();
                showToast(d.message, d.success ? 'success' : 'error');
                if(d.success) setTimeout(function(){location.reload()}, 1500);
            })
            .catch(function(e){
                closeDeleteModal();
                showToast('Error: '+e, 'error');
            })
            .finally(function() {
                var btn = document.getElementById('confirm-delete-btn');
                btn.textContent = 'Delete';
                btn.disabled = false;
            });
        });

        // Edit Competitor
        function editComp(n){
            console.log('Editing competitor:', n);
            showToast('Loading ' + n + '...', 'info');
            
            fetch('/api/competitors/'+encodeURIComponent(n)+'/full')
            .then(function(r){
                if (!r.ok) throw new Error('API Error: ' + r.statusText);
                return r.json();
            })
            .then(function(d){
                console.log('Loaded competitor data:', d);
                
                // Populate fields
                document.getElementById('edit-orig').value=n;
                document.getElementById('edit-name').value=d.name;
                document.getElementById('edit-website').value=d.website||'';
                
                // Clear and repopulate pages
                var c=document.getElementById('edit-pages');
                c.innerHTML='';
                
                if (d.pages && d.pages.length > 0) {
                    d.pages.forEach(function(p,i){
                        var e=document.createElement('div');
                        e.className='page-entry';
                        
                        // Use template literals for cleaner HTML construction if supported (assuming modern browser)
                        // But sticking to concatenation for compatibility as per previous style
                        var html = '<div class="page-entry-header"><strong>Page '+(i+1)+'</strong>';
                        if (i > 0) {
                            html += '<button type="button" class="button button-small button-danger" onclick="this.parentElement.parentElement.remove()">Remove</button>';
                        }
                        html += '</div>';
                        
                        html += '<div class="form-group"><label>URL</label><input type="url" class="edit-url" value="'+(p.url || '')+'" required></div>';
                        
                        html += '<div class="form-group"><label>Type</label><select class="edit-type">';
                        ['features', 'pricing', 'blog', 'products'].forEach(function(opt){
                            var sel = (p.type === opt) ? ' selected' : '';
                            html += '<option value="'+opt+'"'+sel+'>'+opt.charAt(0).toUpperCase() + opt.slice(1)+'</option>';
                        });
                        html += '</select></div>';
                        
                        html += '<div class="form-group"><label>Selector</label><input type="text" class="edit-selector" value="'+(p.selector || '')+'"></div>';
                        
                        e.innerHTML = html;
                        c.appendChild(e);
                    });
                } else {
                    // Start with one empty page if none exist (shouldn't happen but safe)
                    addEditPage();
                }
                
                document.getElementById('edit-modal').style.display='block';
            })
            .catch(function(e){
                console.error('Edit Error:', e);
                showToast('Error: '+e.message, 'error');
            });
        }
        function closeEdit(){document.getElementById('edit-modal').style.display='none'}

        function saveEdit(e){
            e.preventDefault();
            var orig=document.getElementById('edit-orig').value;
            var name=document.getElementById('edit-name').value;
            var website=document.getElementById('edit-website').value;
            var pages=[];
            document.querySelectorAll('#edit-pages .page-entry').forEach(function(p){
                pages.push({
                    url:p.querySelector('.edit-url').value,
                    type:p.querySelector('.edit-type').value,
                    selector:p.querySelector('.edit-selector').value||''
                })
            });
            fetch('/api/competitors/'+encodeURIComponent(orig),{
                method:'PUT',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({original_name:orig,name:name,website:website,pages:pages})
            })
            .then(function(r){return r.json()})
            .then(function(d){
                showToast(d.message, d.success ? 'success' : 'error');
                if(d.success) setTimeout(function(){location.reload()}, 1500);
            })
            .catch(function(e){showToast('Error: '+e, 'error')});
        }

        function addEditPage(){var c=document.getElementById('edit-pages'),n=c.querySelectorAll('.page-entry').length+1,e=document.createElement('div');e.className='page-entry';e.innerHTML='<div class="page-entry-header"><strong>Page '+n+'</strong><button type="button" class="button button-small button-danger" onclick="this.parentElement.parentElement.remove()">Remove</button></div><div class="form-group"><label>URL</label><input type="url" class="edit-url" required></div><div class="form-group"><label>Type</label><select class="edit-type"><option value="features">Features</option><option value="pricing">Pricing</option><option value="blog">Blog</option><option value="products">Products</option></select></div><div class="form-group"><label>Selector</label><input type="text" class="edit-selector"></div>';c.appendChild(e)}

        document.addEventListener('DOMContentLoaded',function(){
            document.querySelectorAll('.btn-view').forEach(function(b){b.addEventListener('click',function(){viewComp(this.dataset.name)})});
            document.querySelectorAll('.btn-edit').forEach(function(b){b.addEventListener('click',function(){editComp(this.dataset.name)})});
            document.querySelectorAll('.btn-del').forEach(function(b){b.addEventListener('click',function(){deleteComp(this.dataset.name)})});
        });
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    stats = db.get_competitor_stats()
    changes = db.get_recent_changes(limit=50, days=30)
    competitors = db.get_all_competitors()
    return render_template_string(HTML_TEMPLATE, stats=stats, changes=changes, competitors=competitors)

@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    changes_detected = scraper.scrape_all_competitors()
    return jsonify({'success': True, 'changes_detected': changes_detected})

@app.route('/api/report')
def api_report():
    days = int(request.args.get('days', 7))
    report = scraper.generate_report(days=days)
    return report, 200, {'Content-Type': 'text/plain'}

@app.route('/api/competitors', methods=['POST'])
def api_add():
    try:
        data = request.json
        name = data.get('name')
        website = data.get('website', '')
        pages = data.get('pages', [])
        if not name or not pages:
            return jsonify({'success': False, 'message': 'Name and pages required'})
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
        if any(c['name'] == name for c in cfg['competitors']):
            return jsonify({'success': False, 'message': 'Already exists'})
        cfg['competitors'].append({'name': name, 'website': website, 'pages': pages})
        with open('config.yaml', 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        return jsonify({'success': True, 'message': 'Added!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/competitors/<name>')
def api_get(name):
    try:
        pages = db.get_competitor_pages(name)
        return jsonify({'name': name, 'pages': pages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/competitors/<name>/full')
def api_get_full(name):
    try:
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
        comp = next((c for c in cfg['competitors'] if c['name'] == name), None)
        if comp:
            return jsonify(comp)
        return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/competitors/<name>', methods=['PUT'])
def api_update(name):
    try:
        data = request.json
        orig = data.get('original_name', name)
        new_name = data.get('name')
        website = data.get('website', '')
        pages = data.get('pages', [])
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
        found = False
        for i, c in enumerate(cfg['competitors']):
            if c['name'] == orig:
                cfg['competitors'][i] = {'name': new_name, 'website': website, 'pages': pages}
                found = True
                break
        if not found:
            return jsonify({'success': False, 'message': 'Not found'})
        if orig != new_name:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE snapshots SET competitor_name = ? WHERE competitor_name = ?', (new_name, orig))
            cursor.execute('UPDATE changes SET competitor_name = ? WHERE competitor_name = ?', (new_name, orig))
            conn.commit()
            conn.close()
        with open('config.yaml', 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        return jsonify({'success': True, 'message': 'Updated!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/competitors/<name>', methods=['DELETE'])
def api_del(name):
    try:
        db.delete_competitor(name)
        with open('config.yaml', 'r') as f:
            cfg = yaml.safe_load(f)
        cfg['competitors'] = [c for c in cfg['competitors'] if c['name'] != name]
        with open('config.yaml', 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
        return jsonify({'success': True, 'message': 'Deleted!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host=config['dashboard']['host'], port=config['dashboard']['port'], debug=config['dashboard']['debug'])
