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

function openModal(id) { 
    document.getElementById(id).classList.add('open'); 
}

function closeModal(id) { 
    document.getElementById(id).classList.remove('open'); 
}

function filterComps() {
    var s = document.getElementById('comp-search').value.toLowerCase();
    document.querySelectorAll('.comp-row').forEach(function(r) {
        r.style.display = r.dataset.name.toLowerCase().includes(s) ? '' : 'none';
    });
}

function filterChanges() {
    var s = document.getElementById('ch-search').value.toLowerCase();
    document.querySelectorAll('.change-row').forEach(function(r) {
        var match = r.dataset.comp.toLowerCase().includes(s) ||
                    r.dataset.desc.toLowerCase().includes(s);
        r.style.display = match ? '' : 'none';
    });
}

function makeTypeSelect(selected) {
    var fg = document.createElement('div');
    fg.className = 'fg';
    var lbl = document.createElement('label');
    lbl.textContent = 'Type *';
    var sel = document.createElement('select');
    sel.className = 'p-type';
    sel.required = true;
    ['pricing', 'features', 'blog', 'other'].forEach(function(v) {
        var opt = document.createElement('option');
        opt.value = v;
        opt.textContent = v.charAt(0).toUpperCase() + v.slice(1);
        if (v === selected) opt.selected = true;
        sel.appendChild(opt);
    });
    fg.appendChild(lbl);
    fg.appendChild(sel);
    return fg;
}

function addPageBlock(containerId) {
    var c = document.getElementById(containerId);
    var n = c.querySelectorAll('.page-block').length + 1;
    var block = document.createElement('div');
    block.className = 'page-block';

    var header = document.createElement('div');
    header.className = 'page-block-header';

    var title = document.createElement('span');
    title.textContent = 'Page ' + n;
    header.appendChild(title);

    var removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn sm red';
    removeBtn.textContent = 'Remove';
    removeBtn.onclick = function() { block.remove(); };
    header.appendChild(removeBtn);
    block.appendChild(header);

    var urlFg = document.createElement('div');
    urlFg.className = 'fg';
    urlFg.innerHTML = '<label>URL *</label>';
    var urlInp = document.createElement('input');
    urlInp.type = 'url';
    urlInp.className = 'p-url';
    urlInp.placeholder = 'https://example.com/pricing';
    urlInp.required = true;
    urlFg.appendChild(urlInp);
    block.appendChild(urlFg);

    block.appendChild(makeTypeSelect('pricing'));

    var selFg = document.createElement('div');
    selFg.className = 'fg';
    selFg.innerHTML = '<label>CSS Selector (optional)</label>';
    var selInp = document.createElement('input');
    selInp.type = 'text';
    selInp.className = 'p-sel';
    selInp.placeholder = 'Leave empty for automatic detection';
    selFg.appendChild(selInp);
    block.appendChild(selFg);

    c.appendChild(block);
}

function readPages(containerId) {
    var pages = [];
    document.querySelectorAll('#' + containerId + ' .page-block').forEach(function(b) {
        var urlEl = b.querySelector('.p-url');
        var typeEl = b.querySelector('.p-type');
        var selEl = b.querySelector('.p-sel');
        if (urlEl && urlEl.value) {
            pages.push({
                url: urlEl.value,
                type: typeEl ? typeEl.value : 'other',
                selector: selEl ? selEl.value : ''
            });
        }
    });
    return pages;
}

function addComp(e) {
    e.preventDefault();
    var payload = {
        name: document.getElementById('c-name').value,
        website: document.getElementById('c-website').value,
        pages: readPages('add-pages')
    };
    fetch('/api/competitors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        var el = document.getElementById('add-msg');
        el.textContent = d.message;
        el.className = 'alert ' + (d.success ? 'ok' : 'err');
        if (d.success) setTimeout(function() { location.reload(); }, 1200);
    })
    .catch(function() { toast('Request failed'); });
}

function viewComp(name) {
    fetch('/api/competitor?name=' + encodeURIComponent(name))
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.error) { toast('Error: ' + d.error); return; }
        var body = document.getElementById('view-body');
        body.innerHTML = '';

        var site = document.createElement('p');
        site.style.cssText = 'margin-bottom:1rem;color:#666';
        var siteLink = document.createElement('a');
        siteLink.href = d.website || '#';
        siteLink.target = '_blank';
        siteLink.style.color = '#667eea';
        siteLink.textContent = d.website || 'Not set';
        site.appendChild(document.createTextNode('Website: '));
        site.appendChild(siteLink);
        body.appendChild(site);

        var h = document.createElement('h3');
        h.textContent = 'Tracked Pages';
        h.style.marginBottom = '.75rem';
        body.appendChild(h);

        (d.pages || []).forEach(function(p) {
            var block = document.createElement('div');
            block.style.cssText = 'background:#f8f9fa;padding:.75rem 1rem;border-radius:6px;margin-bottom:.5rem';

            var badge = document.createElement('span');
            badge.className = 'badge ' + p.type;
            badge.textContent = p.type;
            block.appendChild(badge);

            var link = document.createElement('a');
            link.href = p.url;
            link.target = '_blank';
            link.style.cssText = 'color:#667eea;font-size:.88rem;word-break:break-all';
            link.textContent = ' ' + p.url;
            block.appendChild(link);

            if (p.selector) {
                var sd = document.createElement('div');
                sd.style.cssText = 'font-size:.78rem;color:#999;margin-top:.25rem';
                sd.textContent = 'Selector: ' + p.selector;
                block.appendChild(sd);
            }
            body.appendChild(block);
        });

        openModal('view-overlay');
    })
    .catch(function() { toast('Error loading details'); });
}

function editComp(name) {
    fetch('/api/competitor?name=' + encodeURIComponent(name))
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.error) { toast('Error: ' + d.error); return; }
        document.getElementById('e-orig').value = name;
        document.getElementById('e-name').value = d.name;
        document.getElementById('e-website').value = d.website || '';

        var container = document.getElementById('edit-pages');
        container.innerHTML = '';

        (d.pages || []).forEach(function(p, i) {
            var block = document.createElement('div');
            block.className = 'page-block';

            var header = document.createElement('div');
            header.className = 'page-block-header';

            var title = document.createElement('span');
            title.textContent = 'Page ' + (i + 1);
            header.appendChild(title);

            if (i > 0) {
                var rb = document.createElement('button');
                rb.type = 'button';
                rb.className = 'btn sm red';
                rb.textContent = 'Remove';
                rb.onclick = function() { block.remove(); };
                header.appendChild(rb);
            }
            block.appendChild(header);

            var urlFg = document.createElement('div');
            urlFg.className = 'fg';
            urlFg.innerHTML = '<label>URL *</label>';
            var urlInp = document.createElement('input');
            urlInp.type = 'url';
            urlInp.className = 'p-url';
            urlInp.value = p.url || '';
            urlInp.required = true;
            urlFg.appendChild(urlInp);
            block.appendChild(urlFg);

            block.appendChild(makeTypeSelect(p.type));

            var selFg = document.createElement('div');
            selFg.className = 'fg';
            selFg.innerHTML = '<label>CSS Selector (optional)</label>';
            var selInp = document.createElement('input');
            selInp.type = 'text';
            selInp.className = 'p-sel';
            selInp.value = p.selector || '';
            selInp.placeholder = 'Leave empty for automatic';
            selFg.appendChild(selInp);
            block.appendChild(selFg);

            container.appendChild(block);
        });

        openModal('edit-overlay');
    })
    .catch(function() { toast('Error loading competitor'); });
}

function saveEdit(e) {
    e.preventDefault();
    var orig = document.getElementById('e-orig').value;
    var payload = {
        original_name: orig,
        name: document.getElementById('e-name').value,
        website: document.getElementById('e-website').value,
        pages: readPages('edit-pages')
    };
    fetch('/api/competitor?name=' + encodeURIComponent(orig), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        toast(d.message);
        if (d.success) { 
            closeModal('edit-overlay'); 
            setTimeout(function() { location.reload(); }, 900); 
        }
    })
    .catch(function() { toast('Error saving'); });
}

var _delTarget = null;
function confirmDelete(name) {
    _delTarget = name;
    document.getElementById('del-name').textContent = '"' + name + '"';
    openModal('del-overlay');
}

function runScraper(btn) {
    btn.disabled = true;
    btn.textContent = 'Running...';
    toast('Scraper started...', 5000);
    fetch('/api/scrape', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.success) {
            toast('Done! ' + d.changes_detected + ' change(s) detected', 4000);
            var banner = document.getElementById('scrape-banner');
            banner.textContent = 'Scraping complete - ' + d.changes_detected + ' change(s) detected.';
            banner.classList.add('show');
            btn.textContent = 'Done!';
            setTimeout(function() { location.reload(); }, 2000);
        } else {
            toast('Error: ' + (d.error || 'Scraper failed'), 5000);
            btn.textContent = 'Run Scraper Now';
            btn.disabled = false;
        }
    })
    .catch(function(err) {
        toast('Scraper error: ' + err.message, 5000);
        btn.disabled = false;
        btn.textContent = 'Run Scraper Now';
    });
}

document.addEventListener('DOMContentLoaded', function() {
    var delBtn = document.getElementById('del-confirm-btn');
    if (delBtn) {
        delBtn.addEventListener('click', function() {
            if (!_delTarget) return;
            var n = _delTarget;
            var btn = this;
            btn.textContent = 'Deleting...';
            btn.disabled = true;
            fetch('/api/competitor?name=' + encodeURIComponent(n), { method: 'DELETE' })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                closeModal('del-overlay');
                toast(d.message);
                if (d.success) setTimeout(function() { location.reload(); }, 900);
            })
            .catch(function() { toast('Error deleting'); })
            .finally(function() {
                btn.textContent = 'Delete';
                btn.disabled = false;
                _delTarget = null;
            });
        });
    }
});
