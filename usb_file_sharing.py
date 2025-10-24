import os
import threading
import time
import shutil
from flask import Flask, send_from_directory, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
USB_DRIVE_LETTER = None

def find_usb_drive():
    global USB_DRIVE_LETTER
    while True:
        for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
            d = f"{letter}:/"
            if os.path.isdir(d):
                USB_DRIVE_LETTER = letter
                print(f"Detected USB at {USB_DRIVE_LETTER}:/")  
                return
        time.sleep(2)

@app.route('/')
def index():
    return render_template_string(r'''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>USB File Sharing</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
  <style>
    :root {
      --primary: #ff6a00;
      --primary-hover: #e05d00;
      --secondary: #0971b3;
      --secondary-hover: #08619d;
      --bg-dark: #000000;
      --bg-light: #1a1a1a;
      --bg-lighter: #2a2a2a;
      --text-light: #ffffff;
      --text-muted: #aaaaaa;
    }
    
    body { 
      background: #121212; 
      color: var(--text-light);
      min-height: 100vh;
    }
    
    /* Updated table styles */
    .table thead th {
      background-color: #2a2a2a;
      color: #fff;
      border-bottom: 1px solid #444;
    }
    
    .table tbody tr {
      background-color: #2a2a2a;
      color: #fff;
    }
    
    .table tbody tr:hover {
      background-color: #333333;
    }
    
    .folder-link { 
      cursor: pointer; 
      color: var(--primary);
    }
    
    .folder-link:hover { 
      text-decoration: underline;
      color: var(--primary-hover);
    }
    
    .modal-body textarea { 
      height: 300px; 
      font-family: monospace;
      background-color: var(--bg-lighter);
      color: var(--text-light);
    }
    
    .breadcrumb {
      background-color: var(--bg-light);
      padding: 0.75rem 1rem;
      border-radius: 0.5rem;
    }
    
    .breadcrumb-item a {
      color: var(--primary);
    }
    
    .breadcrumb-item.active {
      color: var(--text-light);
    }
    
    .form-control {
      background-color: var(--bg-lighter);
      color: var(--text-light);
      border-color: #444444;
    }
    
    .form-control:focus {
      background-color: var(--bg-lighter);
      color: var(--text-light);
      border-color: var(--primary);
      box-shadow: 0 0 0 0.25rem rgba(255, 106, 0, 0.25);
    }
    
    .modal-content {
      background-color: var(--bg-light);
      color: var(--text-light);
    }
    
    .btn-close {
      filter: invert(1);
    }
    
    .btn-primary {
      background-color: var(--primary);
      border-color: var(--primary);
    }
    
    .btn-primary:hover {
      background-color: var(--primary-hover);
      border-color: var(--primary-hover);
    }
    
    .btn-secondary {
      background-color: var(--secondary);
      border-color: var(--secondary);
    }
    
    .btn-secondary:hover {
      background-color: var(--secondary-hover);
      border-color: var(--secondary-hover);
    }
    
    .container {
      max-width: 1200px;
    }
    
    .file-icon {
      margin-right: 8px;
      font-size: 1.2rem;
    }
    
    .action-buttons {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    
    .file-item {
      display: flex;
      align-items: center;
    }
    
    .table tbody td {
    background-color: #2a2a2a;
    color: #fff;
  }

  .table tbody tr:hover td {
   background-color: #333333;
  </style>
</head>
<body>
  <div class="container">
    <nav aria-label="breadcrumb"><ol class="breadcrumb" id="breadcrumb"></ol></nav>
    <div class="d-flex mb-3 gap-2 flex-wrap">
      <input type="file" id="fileUpload" class="form-control w-auto d-none">
      <button class="btn btn-primary" onclick="document.getElementById('fileUpload').click()">
        <i class="bi bi-upload"></i> Upload
      </button>
      <button class="btn btn-secondary" onclick="goUp()">
        <i class="bi bi-arrow-up"></i> Up
      </button>
      <input type="text" id="newFolderName" placeholder="Folder name" class="form-control w-auto">
      <button class="btn btn-success" onclick="mkdir()">
        <i class="bi bi-folder-plus"></i> New Folder
      </button>
      <input type="text" id="newFileName" placeholder="File name" class="form-control w-auto">
      <button class="btn btn-info" onclick="touch()">
        <i class="bi bi-file-earmark-plus"></i> New File
      </button>
    </div>
    <table class="table table-hover">        
      <thead>
        <tr>
          <th><i class="bi bi-folder-fill"></i> Name</th>
          <th style="width:260px"><i class="bi bi-gear-fill"></i> Actions</th>
        </tr>
      </thead>
      <tbody id="fileList"></tbody>
    </table>
  </div>

  <!-- Edit Modal -->
  <div class="modal fade" id="editModal" tabindex="-1">
    <div class="modal-dialog modal-lg"><div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Edit File: <span id="editName"></span></h5>
        <button type="button" class="btn-close" onclick="closeEditModal()"></button>
      </div>
      <div class="modal-body">
        <textarea id="editArea" class="form-control" spellcheck="false"></textarea>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeEditModal()">
          <i class="bi bi-x-circle"></i> Cancel
        </button>
        <button class="btn btn-primary" onclick="saveEdit()">
          <i class="bi bi-save"></i> Save
        </button>
      </div>
    </div></div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    let cwd = "", editPath = "";

    function setBreadcrumb() {
      const bc = document.getElementById("breadcrumb");
      bc.innerHTML = '';
      const parts = cwd.split("/").filter(x => x);
      bc.innerHTML = `<li class="breadcrumb-item"><a href="#" onclick="cd('')"><i class="bi bi-usb-drive"></i> USB</a></li>`;
      let acc = "";
      parts.forEach((p, i) => {
        acc += (i > 0 ? '/' : '') + p;
        bc.innerHTML += `
          <li class="breadcrumb-item${i===parts.length-1?' active':''}"${i===parts.length-1?' aria-current="page"':''}>
            ${i===parts.length-1?p:`<a href="#" onclick="cd('${acc}')"><i class="bi bi-folder"></i> ${p}</a>`}
          </li>`;
      });
    }

    function getFileIcon(name, isFolder) {
      if (isFolder) return '<i class="bi bi-folder-fill text-warning file-icon"></i>';
      
      const ext = name.split('.').pop().toLowerCase();
      const icons = {
        txt: 'file-text',
        md: 'file-text',
        pdf: 'file-pdf',
        doc: 'file-word',
        docx: 'file-word',
        xls: 'file-excel',
        xlsx: 'file-excel',
        ppt: 'file-ppt',
        pptx: 'file-ppt',
        jpg: 'file-image',
        jpeg: 'file-image',
        png: 'file-image',
        gif: 'file-image',
        mp3: 'file-music',
        mp4: 'file-play',
        zip: 'file-zip',
        exe: 'file-binary',
        py: 'file-code',
        js: 'file-code',
        html: 'file-code',
        css: 'file-code'
      };
      
      return `<i class="bi bi-${icons[ext] || 'file-earmark'} text-info file-icon"></i>`;
    }

    async function load() {
      setBreadcrumb();
      const r = await fetch('/list?path=' + encodeURIComponent(cwd));
      if (!r.ok) return alert("USB not ready.");
      const files = await r.json();
      const tb = document.getElementById("fileList");
      tb.innerHTML = "";
      files.sort((a,b) => a.is_folder === b.is_folder ? a.name.localeCompare(b.name) : a.is_folder ? -1 : 1);
      files.forEach(f => {
        const tr = document.createElement("tr");
        const nameTd = document.createElement("td");
        nameTd.innerHTML = f.is_folder
          ? `<div class="file-item"><span class="folder-link" onclick="cd('${f.name}')">${getFileIcon(f.name, true)} ${f.name}</span></div>`
          : `<div class="file-item">${getFileIcon(f.name, false)} ${f.name}</div>`;
        
        const actionsTd = document.createElement("td");
        actionsTd.innerHTML = `
          <div class="action-buttons">
            ${!f.is_folder ? `<button class="btn btn-sm btn-success" onclick="download('${f.name}')"><i class="bi bi-download"></i></button>` : ''}
            ${!f.is_folder && /\.(txt|md|log|py|js|html|css)$/i.test(f.name) ? `<button class="btn btn-sm btn-warning" onclick="openEditModal('${f.name}')"><i class="bi bi-pencil"></i></button>` : ''}
            <button class="btn btn-sm btn-danger" onclick="rm('${f.name}',${f.is_folder})"><i class="bi bi-trash"></i></button>
          </div>`;
        
        tr.append(nameTd, actionsTd);
        tb.append(tr);
      });
    }

    function cd(path) { cwd = path; load(); }
    function goUp() { cwd = cwd.split('/').slice(0,-1).join('/'); load(); }

    function download(name) {
      window.open('/download/' + encodeURIComponent((cwd?cwd+"/":"") + name));
    }

    async function upload() {
      const inp = document.getElementById("fileUpload");        
      if (!inp.files.length) return;
      
      const fd = new FormData(); 
      fd.append('file', inp.files[0]); 
      fd.append('path', cwd);
      
      const r = await fetch('/upload', { method: 'POST', body: fd });
      if (!r.ok) return alert("Upload failed");
      
      alert(`${inp.files[0].name} uploaded successfully!`);
      inp.value = ""; 
      load();
    }

    document.getElementById('fileUpload').addEventListener('change', upload);

    async function mkdir() {
      const n = document.getElementById("newFolderName").value.trim(); 
      if (!n) return;
      
      await fetch('/mkdir', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ path: cwd, name: n })
      });
      
      alert(`Folder "${n}" created successfully!`);
      document.getElementById("newFolderName").value = ""; 
      load();
    }

    async function touch() {
      const n = document.getElementById("newFileName").value.trim(); 
      if (!n) return;
      
      await fetch('/touch', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ path: cwd, name: n })
      });
      
      alert(`File "${n}" created successfully!`);
      document.getElementById("newFileName").value = ""; 
      load();
    }

    async function rm(name, isFolder) {
      if (!confirm(`Are you sure you want to delete "${name}"?`)) return;
      
      const r = await fetch('/delete', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ path: (cwd?cwd+"/":"")+name, is_folder: isFolder })
      });
      
      if (!r.ok) return r.text().then(alert);
      alert(`"${name}" has been deleted`);
      load();
    }

    async function openEditModal(name) {
      editPath = (cwd?cwd + "/":"") + name;
      document.getElementById("editName").textContent = name;
      
      const r = await fetch('/read_file?path=' + encodeURIComponent(editPath));
      if (!r.ok) return alert("Failed to load file");
      
      const data = await r.json();
      document.getElementById("editArea").value = data.content || "";
      new bootstrap.Modal('#editModal').show();
    }

    function closeEditModal() {
      editPath = "";
      bootstrap.Modal.getInstance(document.getElementById('editModal'))?.hide();
    }

    async function saveEdit() {
      const content = document.getElementById("editArea").value;
      const r = await fetch('/write_file', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ path: editPath, content })
      });
      
      if (!r.ok) return alert("Save failed");
      alert(`Changes to "${editPath}" saved successfully!`);
      closeEditModal();
      load();
    }

    load();
  </script>
</body>
</html>
''')

@app.route('/list')
def list_files():
    if not USB_DRIVE_LETTER:
        return jsonify([]), 404
    sub = request.args.get('path', '').strip('/')
    base = os.path.join(f"{USB_DRIVE_LETTER}:/", sub)
    entries = [{"name": n, "is_folder": os.path.isdir(os.path.join(base, n))} for n in os.listdir(base)]
    return jsonify(entries)

@app.route('/download/<path:p>')
def download_file(p):
    d = os.path.dirname(p)
    return send_from_directory(f"{USB_DRIVE_LETTER}:/{d}", os.path.basename(p), as_attachment=True)

@app.route('/upload', methods=['POST'])
def upload_file():
    path = request.form.get('path', '').strip('/')
    f = request.files['file']
    dst = os.path.join(f"{USB_DRIVE_LETTER}:/", path, f.filename)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    f.save(dst)
    return "OK"

@app.route('/mkdir', methods=['POST'])
def make_folder():
    d = request.json
    os.makedirs(os.path.join(f"{USB_DRIVE_LETTER}:/", d['path'].strip('/'), d['name']), exist_ok=True)
    return "OK"

@app.route('/touch', methods=['POST'])
def make_file():
    d = request.json
    open(os.path.join(f"{USB_DRIVE_LETTER}:/", d['path'].strip('/'), d['name']), 'w').close()
    return "OK"

@app.route('/delete', methods=['POST'])
def delete_item():
    d = request.json
    full = os.path.join(f"{USB_DRIVE_LETTER}:/", d['path'].strip('/'))
    try:
        if d.get('is_folder'):
            shutil.rmtree(full)
        else:
            os.remove(full)
        return "OK"
    except Exception as e:
        return str(e), 500

@app.route('/read_file')
def read_file():
    p = request.args.get('path', '').strip('/')
    with open(os.path.join(f"{USB_DRIVE_LETTER}:/", p), 'r', encoding='utf8') as f:
        return jsonify({"content": f.read()})

@app.route('/write_file', methods=['POST'])
def write_file():
    d = request.json
    with open(os.path.join(f"{USB_DRIVE_LETTER}:/", d['path'].strip('/')), 'w', encoding='utf8') as f:
        f.write(d['content'])
    return "OK"

if __name__ == '__main__':
    threading.Thread(target=find_usb_drive, daemon=True).start()
    from waitress import serve
    serve(app, host='0.0.0.0', port=8081)
