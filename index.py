# permissions off mais fichier permissions automatique 
from flask import Flask, request, redirect, url_for, send_from_directory, render_template_string, session, abort
from werkzeug.utils import secure_filename
import os, json, mimetypes, socket
from datetime import datetime
from ipaddress import ip_address

app = Flask(__name__)
app.secret_key = "serveur_secret_key"
UPLOAD_FOLDER = 'uploads'
USERS_FILE = 'users.json'
PERMISSIONS_FILE = 'permissions.json'
ADMIN_DIR = os.path.join(UPLOAD_FOLDER, 'admin')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi','mov', 'mp3','apk+','apk', 'wav','html','xlsx','xls','doc','docx','csv','pub','ppt','pptx','psd','ai','js','json','py','webp','zip','vcf','css'}
ACTIVE_SESSIONS = {}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ADMIN_DIR, exist_ok=True)

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, 'w') as f:
        json.dump({"lecryptique": {"password": "shooter", "role": "admin", "ip": "", "last_seen": ""}}, f, indent=4)

if not os.path.exists(PERMISSIONS_FILE):
    with open(PERMISSIONS_FILE, 'w') as f:
        json.dump({}, f)

def load_users():
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_permissions():
    # Initialiser avec un dict vide si le fichier n'existe pas ou est invalide
    if not os.path.exists(PERMISSIONS_FILE):
        with open(PERMISSIONS_FILE, 'w') as f:
            json.dump({}, f)
        return {}

    try:
        with open(PERMISSIONS_FILE, 'r') as f:
            permissions = json.load(f)
    except (json.JSONDecodeError, IOError):
        permissions = {}

    # Vérifier que la structure est valide
    if not isinstance(permissions, dict):
        permissions = {}

    return permissions

def check_permission(path, username, action):
    """Vérifie si l'utilisateur a la permission pour une action donnée"""
    if username == 'lecryptique':  # L'admin a tous les droits
        return True
    
    permissions = load_permissions()
    norm_path = normalize_path(path)
    
    # Permission par défaut si non spécifiée
    default_perms = {
        'download': True,  # Par défaut, le téléchargement est autorisé
        'delete': False    # Par défaut, la suppression est interdite
    }
    
    user_perms = permissions.get(norm_path, {}).get(username, default_perms)
    return user_perms.get(action, default_perms[action])

def save_permissions_to_file(permissions):
    with open(PERMISSIONS_FILE, 'w') as f:
        json.dump(permissions, f, indent=4) 

def normalize_path(p: str) -> str:
    """
    Normalise un chemin pour l'utiliser comme clé unique dans permissions.json
    - remplace backslashes par slashes
    - supprime slash initial s'il existe
    - supprime './' en début
    """
    if p is None:
        return ""
    p = p.replace("\\", "/")
    p = p.strip()
    # enlever les ./ initiaux
    while p.startswith("./"):
        p = p[2:]
    # enlever slash initial
    p = p.lstrip("/")
    return p

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_stats(path):
    total_size, total_files, total_dirs = 0, 0, 0
    for root, dirs, files in os.walk(os.path.join(UPLOAD_FOLDER, path)):
        for f in files:
            total_files += 1
            total_size += os.path.getsize(os.path.join(root, f))
        total_dirs += len(dirs)
    return total_files, total_dirs, round(total_size / 1024 / 1024, 2)

def get_items(current_path, is_admin=False):
    items = []
    full_path = os.path.join(UPLOAD_FOLDER, current_path)
    
    if not os.path.exists(full_path):  
        return items  
          
    for name in os.listdir(full_path):  
        if name == 'admin' and not is_admin:  
            continue  
            
        if name.startswith('.') and name.endswith('.uploader'):
            continue
              
        abs_path = os.path.join(full_path, name)  
        rel_path = os.path.join(current_path, name).replace("\\", "/")  
        is_dir = os.path.isdir(abs_path)
              
        abs_path = os.path.join(full_path, name)  
        rel_path = os.path.join(current_path, name).replace("\\", "/")  
        is_dir = os.path.isdir(abs_path)  
        mime = mimetypes.guess_type(name)[0] or "Fichier"  

        uploader = "System"  
        uploader_path = os.path.join(full_path, f".{name}.uploader")  
        if os.path.exists(uploader_path):  
            try:  
                with open(uploader_path, 'r') as f:  
                    uploader_content = f.read().strip()
                    uploader = uploader_content if uploader_content else "System"
            except Exception as e:  
                uploader = "System"  
        # Pour les dossiers, ne pas afficher "System" 
        elif is_dir:
            uploader = "-" 
      
        preview = ""  
        player_button = ""  
        if not is_dir:  
            ext = name.lower()  
            if ext.endswith(('.png', '.jpg', '.jpeg', '.gif')):  
                preview = f'<img src="/preview/{rel_path}" style="max-height:60px">'  
            elif ext.endswith(('.mp4', '.avi')):  
                preview = f'<video src="/preview/{rel_path}" style="max-height:60px" controls></video>'  
                player_button = f'<a class="btn btn-teal" href="/preview/{rel_path}" target="_blank">Lecture</a>'  
            elif ext.endswith('.pdf'):  
                preview = f'<embed src="/preview/{rel_path}" type="application/pdf" width="100" height="60">'  
            elif ext.endswith(('.mp3', '.wav')):  
                player_button = f'<a class="btn btn-teal" href="/preview/{rel_path}" target="_blank">Lecture</a>'  
        
        items.append({  
            "name": name,   
            "rel_path": rel_path,   
            "type": mime if not is_dir else "Dossier",   
            "is_dir": is_dir,   
            "preview": preview,  
            "player_button": player_button,  
            "uploader": uploader,  
            "is_admin_folder": name == 'admin'  
        })  
    return items

TEMPLATE = """
<html><head><meta charset='utf-8'><title>CRYPTIFILE</title><style>    
body {   
    font-family:sans-serif;   
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);  
    padding:20px;   
    color: #fff;  
}  
.header-brand {  
    text-align: center;  
    margin: 0 auto 25px;  
    padding: 15px;  
    max-width: 80%;  
    background: linear-gradient(to right, rgba(118, 75, 162, 0.05), rgba(103, 65, 142, 0.1));  
    border: 2px solid #764ba2;
    border-radius: 15px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
.server-name {
    color: #764ba2;
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: 1px;
}
.server-slogan {
    color: #6c757d;
    font-size: 1.1rem;
    margin: 5px 0 0;
    font-style: italic;
}
.footer {
    text-align: center;
    background-color: white;
    color: blue;
    border-radius: 10px;
    font-size: 8px;
}
.container {
    background: rgba(255, 255, 255, 0.9);
    max-width:1200px;
    margin:auto;
    padding:25px;
    border-radius:15px;
    box-shadow:0 0 20px rgba(0,0,0,0.2);
    color: #333;
}
.login-container {
    max-width: 500px;
    margin: 50px auto;
    padding: 30px;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 15px;
    box-shadow: 0 0 20px rgba(0,0,0,0.1);
}
input, button {
    padding:12px;
    width:100%;
    margin-bottom:15px;
    border: 1px solid #ddd;
    border-radius: 8px;
    font-size: 16px;
}
button {
    background: linear-gradient(to right, #667eea, #764ba2);
    color: white;
    border: none;
    cursor: pointer;
    transition: all 0.3s;
}
button:hover {
    opacity: 0.9;
    transform: translateY(-2px);
}
table {
    width:100%;
    border-collapse:collapse;
    margin-top:20px;
}
th, td {
    padding:12px;
    border-bottom:1px solid #ddd;
    text-align: left;
    color: #333;
}
th {
    background-color: #764ba2;
    color: white;
}
a.btn {
    padding:8px 15px;
    border-radius:6px;
    text-decoration:none;
    color:white;
    display: inline-block;
    margin: 3px;
    font-size: 14px;
    transition: all 0.3s;
}
a.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}
.btn-green { background:#28a745; }
.btn-orange { background:#fd7e14; }
.btn-yellow { background:#ffc107; color:black; }
.btn-blue { background:#007bff; }
.btn-red { background:#dc3545; }
.btn-purple { background:#6f42c1; }
.btn-teal { background:#20c997; }
.search-box { margin: 20px 0; }
.status-online { color: #28a745; font-weight: bold; }
.status-offline { color: #6c757d; }
.player-btn { margin-top: 5px; }
.disabled-btn {
    background: #6c757d !important;
    cursor: not-allowed;
    opacity: 0.6;
}
</style></head><body>
{% if not session.get('username') %}
<div class='login-container'>    
    <h2 style="text-align:center; color:#764ba2;">Connexion</h2>    
    <form method='post' action='/login'>    
        <input name='username' placeholder="Nom d'utilisateur">    
        <input name='password' type='password' placeholder="Mot de passe">    
        <button>Connexion</button>    
    </form>    
</div>    
<div class='container'>    
{% else %}    
<div class='container'>    
    <div class="header-brand">    
        <h1 class="server-name">EMEKA DISTRIBUTION</h1>    
        <p class="server-slogan">Votre serveur de fichiers sécurisé</p>    
    </div>    
    {% if session.username == 'lecryptique' %}    
    <p>  
        <a href="/admin/users" class="btn btn-red">Gérer les utilisateurs</a>  
        <a href="/register" class="btn btn-teal">Créer un compte</a>  
    </p>    
    {% endif %}    
    <h2>Bienvenue {{ session.username }} {% if session.role=='admin' %}(Admin){% endif %} 
    {% if session.username == 'lecryptique' %}
    <a href='https://mon-contact.vercel.app/' target='_blank' style='float:right;margin-right:1px;color:#764ba2;text-decoration:none;font-size:14px;padding:8px 15px;background:rgba(118, 75, 162, 0.1);border:1px solid #764ba2;border-radius:5px;'>📞 Contacter le développeur</a>
    {% endif %}
    <a href='/logout' style='float:right;color:red'>Déconnexion</a>
</h2>    
    <form method='post' enctype='multipart/form-data' action='/upload?path={{ path }}'>    
        <input type='file' name='file' required>    
        <button type='submit' class='btn-green'>Upload</button>    
    </form>    
    <form method='post' action='/mkdir?path={{ path }}'>    
        <input name='foldername' placeholder='Nom du dossier' required>    
        <button class='btn-orange'>Créer un dossier</button>    
    </form>    
    <form method='post' action='/rename?path={{ path }}'>    
        <input name='oldname' placeholder='Ancien nom' required>    
        <input name='newname' placeholder='Nouveau nom' required>    
        <button class='btn-yellow'>Renommer</button>    
    </form>    
    <p><b>Statistiques :</b> {{ stats[0] }} fichiers, {{ stats[1] }} dossiers, {{ stats[2] }} Mo</p>    
    <table>    
        <tr>    
            <th>Nom</th>    
            <th>Type</th>    
            <th>Déposé par</th>    
            <th>Prévisualisation</th>    
            <th>Actions</th>
            {% if path %}
            <th>Navigation</th>
            {% endif %}    
        </tr>    
        {% for item in items %}    
        <tr>    
            <td>{{ item.name }}</td>    
            <td>{{ item.type }}</td>    
            <td>{{ item.uploader }}</td>    
            <td>    
                {{ item.preview|safe }}    
                {% if item.player_button %}    
                <div class="player-btn">{{ item.player_button|safe }}</div>    
                {% endif %}    
            </td>    
            <td>    
                {% if item.is_dir %}    
                    <a class='btn btn-blue' href='/?path={{ item.rel_path }}'>Ouvrir</a>    
                    {% if session.username == 'lecryptique' or permissions.get(item.rel_path, {}).get(session.username, {}).get('delete', False) %}    
                    <a class='btn btn-red' href='/delete/{{ item.rel_path }}' onclick="return confirm('Supprimer ce dossier ?')">Supprimer</a>    
                    {% else %}    
                    <a class='btn btn-red disabled-btn'>Supprimer</a>    
                    {% endif %}    
                {% else %}    
                    {% if session.username == 'lecryptique' or permissions.get(item.rel_path, {}).get(session.username, {}).get('download', True) %}    
                    <a class='btn btn-blue' href='/download/{{ item.rel_path }}'>Télécharger</a>    
                    {% else %}    
                    <a class='btn btn-blue disabled-btn'>Télécharger</a>    
                    {% endif %}    
                    {% if session.username == 'lecryptique' or permissions.get(item.rel_path, {}).get(session.username, {}).get('delete', False) %}    
                    <a class='btn btn-red' href='/delete/{{ item.rel_path }}' onclick="return confirm('Supprimer ce fichier ?')">Supprimer</a>    
                    {% else %}    
                    <a class='btn btn-red disabled-btn'>Supprimer</a>    
                    {% endif %}    
                {% endif %}    
                {% if session.username == 'lecryptique' %}    
                <a class='btn btn-purple' href='/permissions/{{ item.rel_path }}'>Autorisation</a>    
                {% endif %}    
            </td>
            {% if path %}
            <td>
                <a class='btn btn-yellow' href='/?path={{ parent_path }}'>← Retour</a>
                <a class='btn btn-green' href='/'>🏠 Accueil</a>
            </td>
            {% endif %}    
        </tr>    
        {% endfor %}    
    </table>    
</div>    
{% endif %}    
 <button class="boutton" <a href="https://wa.me/+237677247490">CRYPTIFILE © Tous droit réservés<br> V 2.0.0 <br>Developer par  LECRYPTIQUE. Yaoundé - cameroun</a></boutton></p>    
</body></html>    
"""

@app.before_request
def update_user_activity():
    if 'username' in session:
        users = load_users()
        username = session['username']
        if username in users:
            users[username]['ip'] = request.remote_addr
            users[username]['last_seen'] = datetime.now().isoformat()
            save_users(users)
            ACTIVE_SESSIONS[username] = datetime.now()

@app.route("/")
def index():
    if 'username' not in session:
        return render_template_string(TEMPLATE, permissions={})
    
    current_path = request.args.get("path", "")
    os.makedirs(os.path.join(UPLOAD_FOLDER, current_path), exist_ok=True)
    items = get_items(current_path, session.get("role") == "admin")
    stats = get_stats(current_path)
    permissions = load_permissions()
    
    return render_template_string(TEMPLATE, 
                               session=session, 
                               path=current_path, 
                               items=items, 
                               stats=stats,
                               permissions=permissions)

@app.route("/login", methods=["POST"])
def login():
    users = load_users()
    u, p = request.form['username'], request.form['password']
    if u in users and users[u]['password'] == p:
        session['username'] = u
        session['role'] = users[u].get('role', 'user')
        users[u]['ip'] = request.remote_addr
        users[u]['last_seen'] = datetime.now().isoformat()
        save_users(users)
        ACTIVE_SESSIONS[u] = datetime.now()
        return redirect("/")
    return "Identifiants invalides"

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get('username') != 'lecryptique':
        abort(403)

    if request.method == 'GET':  
        return """  
        <html><head><title>Créer un compte</title>  
        <style>  
            body { font-family:sans-serif; background:#f5f5f5; padding:20px; }  
            .form-container { max-width:500px; margin:50px auto; padding:20px; background:white; border-radius:8px; box-shadow:0 0 10px rgba(0,0,0,0.1); }  
            input, button { width:100%; padding:10px; margin-bottom:15px; border-radius:5px; border:1px solid #ddd; }  
            button { background:#28a745; color:white; border:none; cursor:pointer; }  
        </style></head>  
        <body>  
            <div class='form-container'>  
                <h2 style='text-align:center;color:#764ba2;'>Créer un nouveau compte</h2>  
                <form method='post'>  
                    <input name='new_username' placeholder="Nom d'utilisateur" required>  
                    <input name='new_password' type='password' placeholder="Mot de passe" required>  
                    <button type='submit'>Créer le compte</button>  
                </form>  
                <br><a href='/admin/users'>← Retour</a>  
            </div>  
        </body></html>  
        """  
  
    users = load_users()  
    u = request.form['new_username'].strip()  
    p = request.form['new_password'].strip()  
  
    if not u or not p:  
        return "Nom d'utilisateur et mot de passe requis", 400  
  
    if u in users:  
        return "Ce nom d'utilisateur existe déjà", 400  
  
    users[u] = {  
        "password": p,  
        "role": "user",  
        "ip": request.remote_addr,  
        "last_seen": datetime.now().isoformat()  
    }  
    save_users(users)  
    return redirect("/admin/users")

@app.route("/logout")
def logout():
    if 'username' in session:
        username = session['username']
        if username in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[username]
    session.clear()
    return redirect("/")

@app.route("/upload", methods=["POST"])
def upload():
    if 'username' not in session:
        abort(403)
    path = request.args.get("path", "")
    if 'file' not in request.files:
        return redirect(f"/?path={path}")

    f = request.files['file']  
    if f.filename == '':  
        return redirect(f"/?path={path}")  
          
    if f and allowed_file(f.filename):  
        fn = secure_filename(f.filename)  
        file_path = os.path.join(UPLOAD_FOLDER, path, fn)  
        
        # Vérifier si le fichier existe déjà
        if os.path.exists(file_path):
            # Vérifier si c'est exactement le même fichier (même taille)
            existing_size = os.path.getsize(file_path)
            # Calculer la taille du nouveau fichier
            f.seek(0, 2)  # Aller à la fin du fichier
            new_size = f.tell()
            f.seek(0)  # Revenir au début
            
            if existing_size == new_size:
                return f"<script>alert('Ce fichier existe déjà dans le serveur !'); window.location.href='/?path={path}';</script>", 400
        
        # Sauvegarder le fichier
        f.save(file_path)  

        # Créer le fichier de métadonnées avec l'utilisateur qui a uploadé
        uploader_path = os.path.join(UPLOAD_FOLDER, path, f".{fn}.uploader")  
        with open(uploader_path, 'w') as up_file:  
            up_file.write(session['username'])  
            
        return redirect(f"/?path={path}")  
    return f"<script>alert('Type de fichier non autorisé'); window.location.href='/?path={path}';</script>", 400

@app.route("/mkdir", methods=["POST"])
def mkdir():
    if 'username' not in session:
        abort(403)
    path = request.args.get("path", "")
    foldername = secure_filename(request.form['foldername'])
    
    folder_path = os.path.join(UPLOAD_FOLDER, path, foldername)
    if os.path.exists(folder_path):
        return f"<script>alert('Un dossier avec ce nom existe déjà !'); window.location.href='/?path={path}';</script>", 400
    
    os.makedirs(folder_path, exist_ok=False)  # exist_ok=False pour lever une erreur si le dossier existe
    return redirect(f"/?path={path}")

@app.route("/rename", methods=["POST"])
def rename():
    if 'username' not in session:
        abort(403)
    path = request.args.get("path", "")
    old = request.form['oldname']
    new = request.form['newname']
    
    # Vérifier que le nouveau nom n'existe pas déjà
    new_path = os.path.join(UPLOAD_FOLDER, path, new)
    if os.path.exists(new_path):
        return f"<script>alert('Un fichier ou dossier avec ce nom existe déjà !'); window.location.href='/?path={path}';</script>", 400
    
    old_path = os.path.join(UPLOAD_FOLDER, path, old)
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        
        # Gérer le fichier uploader
        old_uploader = os.path.join(UPLOAD_FOLDER, path, f".{old}.uploader")
        new_uploader = os.path.join(UPLOAD_FOLDER, path, f".{new}.uploader")
        if os.path.exists(old_uploader):
            os.rename(old_uploader, new_uploader)

        # Mise à jour dynamique des permissions lors du renommage
        permissions = load_permissions()
        norm_old = normalize_path(os.path.join(path, old))
        norm_new = normalize_path(os.path.join(path, new))

        # Si une entrée existe exactement pour l'ancienne clé -> déplacer
        if norm_old in permissions:
            permissions[norm_new] = permissions.pop(norm_old)
        # Si on renomme un dossier : il faut déplacer toutes les clés qui commencent par norm_old + '/'
        old_prefix = norm_old + '/'
        keys = list(permissions.keys())
        for k in keys:
            if k.startswith(old_prefix):
                new_k = norm_new + k[len(norm_old):]
                permissions[new_k] = permissions.pop(k)

        save_permissions_to_file(permissions)

    return redirect(f"/?path={path}")

@app.route("/download/<path:path>")
def download(path):
    if 'username' not in session:
        abort(403)
    
    if not check_permission(path, session['username'], 'download'):
        abort(403, "Permission de téléchargement refusée")
    
    return send_from_directory(os.path.join(UPLOAD_FOLDER, os.path.dirname(path)), 
                             os.path.basename(path), 
                             as_attachment=True)

@app.route("/delete/<path:path>")
def delete(path):
    if 'username' not in session:
        abort(403)
    
    if not check_permission(path, session['username'], 'delete'):
        abort(403, "Permission de suppression refusée")
    
    full_path = os.path.join(UPLOAD_FOLDER, path)
    if os.path.isfile(full_path):
        os.remove(full_path)
    elif os.path.isdir(full_path):
        os.rmdir(full_path)

    # Suppression des permissions liées
    permissions = load_permissions()
    norm_path = normalize_path(path)
    if norm_path in permissions:
        del permissions[norm_path]
        save_permissions_to_file(permissions)

    return redirect(f"/?path={os.path.dirname(path)}")

@app.route("/preview/<path:path>")
def preview(path):
    return send_from_directory(UPLOAD_FOLDER, path)

@app.route("/permissions/<path:item_path>")
def manage_permissions(item_path):
    if session.get('username') != 'lecryptique':
        abort(403)
    
    users = load_users()
    permissions = load_permissions()
    norm_path = normalize_path(item_path)
    
    # Récupérer les permissions existantes ou initialiser
    item_permissions = permissions.get(norm_path, {})
    
    user_rows = []
    for username in users:
        if username == 'lecryptique':
            continue
            
        # Permissions par défaut si non définies
        default_perms = {'download': True, 'delete': False}
        user_perms = item_permissions.get(username, default_perms)
        
        user_rows.append(f"""
        <tr>
            <td>{username}</td>
            <td>
                <input type="checkbox" name="{username}_download" 
                       {'checked' if user_perms.get('download', True) else ''}>
            </td>
            <td>
                <input type="checkbox" name="{username}_delete" 
                       {'checked' if user_perms.get('delete', False) else ''}>
            </td>
        </tr>
        """)
    
    return f"""
    <html><head><title>Gestion des permissions</title>
    <style>
        body {{ font-family: sans-serif; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 10px; border: 1px solid #ddd; text-align: left; }}
        th {{ background-color: #764ba2; color: white; }}
        .apply-btn {{ margin-top: 20px; display: block;width: 100%; padding:10px; background:#28a745; color:white; border:none; border-radius:6px; }}
    </style></head>
    <body>
        <div class="container">
            <h2 style="color:#764ba2;">Permissions pour: {item_path}</h2>
            <form method="post" action="/save_permissions/{item_path}">
                <table>
                    <tr>
                        <th>Utilisateur</th>
                        <th>Télécharger</th>
                        <th>Supprimer</th>
                    </tr>
                    {"".join(user_rows)}
                </table>
                <button type="submit" class="apply-btn">Appliquer les permissions</button>
            </form>
            <br>
            <a href="/?path={os.path.dirname(item_path)}" class="btn btn-blue">Retour</a>
        </div>
    </body></html>
    """
    
@app.route("/save_permissions/<path:item_path>", methods=["POST"])
def save_permissions(item_path):
    if session.get("username") != "lecryptique":
        abort(403)

    permissions = load_permissions()
    users = load_users()
    
    # Normaliser le chemin
    norm_path = normalize_path(item_path)
    
    # Initialiser l'entrée si elle n'existe pas
    if norm_path not in permissions:
        permissions[norm_path] = {}

    # Traiter chaque utilisateur (sauf admin)
    for username in users:
        if username == "lecryptique":
            continue
            
        # Récupérer les valeurs des cases à cocher
        can_download = request.form.get(f"{username}_download") == "on"
        can_delete = request.form.get(f"{username}_delete") == "on"
        
        # Mettre à jour les permissions
        if username not in permissions[norm_path]:
            permissions[norm_path][username] = {}
        
        permissions[norm_path][username]["download"] = can_download
        permissions[norm_path][username]["delete"] = can_delete

    # Sauvegarder les modifications
    try:
        with open(PERMISSIONS_FILE, 'w') as f:
            json.dump(permissions, f, indent=4)
    except IOError as e:
        print(f"Erreur lors de l'enregistrement : {e}")
        abort(500, "Erreur lors de l'enregistrement des permissions")

    return redirect(f"/permissions/{item_path}")

@app.route("/admin/users")
def admin_users():
    if session.get('username') != 'lecryptique':
        abort(403)
    
    search_query = request.args.get('search', '').lower()    
    users = load_users()    
      
    if search_query:    
        filtered_users = {u: info for u, info in users.items()     
                         if u != 'lecryptique' and search_query in u.lower()}    
    else:    
        filtered_users = {u: info for u, info in users.items() if u != 'lecryptique'}    
      
    user_rows = []    
    for u, info in filtered_users.items():    
        role = info.get('role', 'user')    
        ip = info.get('ip', 'Inconnue')    
            
        is_online = u in ACTIVE_SESSIONS and (datetime.now() - ACTIVE_SESSIONS[u]).seconds < 1800  # 30 minutes d'inactivité    
        status = '<span class="status-online">En ligne</span>' if is_online else '<span class="status-offline">Déconnecté</span>'    
            
        action_buttons = []    
            
        if role == 'admin':    
            action_buttons.append(f'<a class="btn btn-teal" href="/admin/demote/{u}">Retirer Admin</a>')    
        else:    
            action_buttons.append(f'<a class="btn btn-purple" href="/admin/promote/{u}">Promouvoir</a>')    
            
        action_buttons.append(f'<a class="btn btn-red" href="/admin/delete_user/{u}">Supprimer</a>')    
            
        user_rows.append(f"""    
        <tr>    
            <td>{u}</td>    
            <td>{role}</td>    
            <td>{ip}</td>    
            <td>{status}</td>    
            <td><div class="action-buttons">{" ".join(action_buttons)}</div></td>    
        </tr>    
        """)    
      
    user_rows = "".join(user_rows)    
      
    return f"""    
    <html><head><meta charset='utf-8'><title>Utilisateurs</title>    
    <style>    
    body {{ font-family:sans-serif; background:#f2f2f2; padding:20px; }}    
    .container {{ background:white; padding:20px; border-radius:8px; max-width:1000px; margin:auto; }}    
    table {{ width:100%; border-collapse:collapse; margin-top:20px; }}    
    th, td {{ padding:12px; border-bottom:1px solid #ccc; text-align:left; }}    
    .btn-red {{ background:#dc3545; color:white; padding:5px 10px; border-radius:5px; text-decoration:none; }}    
    .btn-purple {{ background:#6f42c1; color:white; padding:5px 10px; border-radius:5px; text-decoration:none; }}    
    .btn-teal {{ background:#20c997; color:white; padding:5px 10px; border-radius:5px; text-decoration:none; }}    
    .search-box {{ margin-bottom:20px; }}    
    .search-box input {{ width:70%; padding:8px; border:1px solid #ddd; border-radius:4px; }}    
    .search-box button {{ width:25%; padding:8px; background:#007bff; color:white; border:none; border-radius:4px; }}    
    .action-buttons {{ display:flex; gap:5px; }}    
    .status-online {{ color: #28a745; font-weight: bold; }}    
    .status-offline {{ color: #6c757d; }}    
    </style></head><body><div class='container'>    
    <h2>Gestion des utilisateurs</h2>    
    <div class='search-box'>    
        <form method='get' action='/admin/users'>    
            <input type='text' name='search' placeholder='Rechercher un utilisateur...' value='{search_query}'>    
            <button type='submit'>Rechercher</button>    
        </form>    
    </div>    
    <table>    
        <tr><th>Nom</th><th>Rôle</th><th>IP</th><th>Statut</th><th>Actions</th></tr>    
        {user_rows}    
    </table>    
    <br><a href='/' style='text-decoration:none'>← Retour</a>    
    </div></body></html>    
    """

@app.route("/admin/promote/<username>")
def promote_user(username):
    if session.get('username') != 'lecryptique':
        abort(403)
    users = load_users()
    if username in users and username != 'lecryptique':
        users[username]['role'] = 'admin'
        save_users(users)
    return redirect("/admin/users")

@app.route("/admin/demote/<username>")
def demote_user(username):
    if session.get('username') != 'lecryptique':
        abort(403)
    users = load_users()
    if username in users and username != 'lecryptique':
        users[username]['role'] = 'user'
        save_users(users)
    return redirect("/admin/users")

@app.route("/admin/delete_user/<username>")
def delete_user(username):
    if session.get('username') != 'lecryptique':
        abort(403)
    users = load_users()
    if username != 'lecryptique' and username in users:
        users.pop(username)
        save_users(users)
        if username in ACTIVE_SESSIONS:
            del ACTIVE_SESSIONS[username]
    return redirect("/admin/users")
    
def get_all_network_interfaces():
    """Récupère toutes les adresses IP disponibles y compris hotspot"""
    import socket
    import subprocess
    import re
    
    interfaces = {}
    
    try:
        # Méthode 1: Via socket (classique)
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if local_ip != "127.0.0.1":
            interfaces['Local'] = local_ip
    except:
        pass
    
    try:
        # Méthode 2: Via ifconfig/ip (Linux/Android)
        try:
            # Essayer ifconfig d'abord
            result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)
            output = result.stdout
        except:
            # Si ifconfig n'existe pas, essayer ip addr
            try:
                result = subprocess.run(['ip', 'addr'], capture_output=True, text=True, timeout=5)
                output = result.stdout
            except:
                output = ""
        
        if output:
            # Chercher toutes les adresses IP
            ip_pattern = r'inet (\d+\.\d+\.\d+\.\d+)'
            ips = re.findall(ip_pattern, output)
            
            # Analyser chaque interface dans l'output
            lines = output.split('\n')
            current_interface = ""
            
            for line in lines:
                # Détecter le nom de l'interface
                if line and not line.startswith(' ') and ':' in line:
                    current_interface = line.split(':')[0].strip()
                
                # Chercher les IPs dans cette ligne
                ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                if ip_match:
                    ip = ip_match.group(1)
                    if ip != "127.0.0.1":
                        # Identifier le type d'interface
                        interface_name = current_interface.lower()
                        if any(x in interface_name for x in ['wlan', 'wifi', 'ap', 'hotspot']):
                            if any(x in interface_name for x in ['ap', 'hotspot']) or ip.startswith('192.168.43.') or ip.startswith('192.168.137.'):
                                interfaces['Hotspot Mobile'] = ip
                            else:
                                interfaces['WiFi'] = ip
                        elif any(x in interface_name for x in ['eth', 'enp', 'ens']):
                            interfaces['Ethernet'] = ip
                        elif 'usb' in interface_name:
                            interfaces['USB'] = ip
                        else:
                            interfaces[current_interface] = ip
    except:
        pass
    
    try:
        # Méthode 3: Spécifique Android/Termux - chercher les interfaces hotspot courantes
        common_hotspot_ranges = [
            '192.168.43.',  # Android hotspot standard
            '192.168.137.', # Windows hotspot
            '10.0.0.',      # iOS hotspot
            '172.20.10.',   # iOS hotspot alternatif
        ]
        
        for ip in ['192.168.43.1', '192.168.137.1', '10.0.0.1', '172.20.10.1']:
            try:
                # Tester si on peut se connecter à cette IP (hotspot actif)
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.1)
                result = test_socket.connect_ex((ip, 1))
                test_socket.close()
                
                if result == 0 or result == 111:  # Port fermé mais IP accessible
                    interfaces['Hotspot Mobile'] = ip
                    break
            except:
                continue
                
    except:
        pass
    
    return interfaces
    
if __name__ == "__main__":
    print("\n" + "="*80)
    print(" ⏳ CRYPTIFILE SERVER CONFIGURATION ⏳ V 2.0.0 by LECRYPTIQUE Yaoundé-Cameroun")
    print("            Lancement de votre serveur de fichiers sécurisé ✅")
    print(" Veillez remplir l'Ip du serveur et le port de connexion pour son démarrage ✅")
    print("="*80)
    
    # Détecter toutes les interfaces réseau
    print("\n🔍 Détection des interfaces réseau disponibles...")
    interfaces = get_all_network_interfaces()
    
    if interfaces:
        print("\n📡 Adresses IP détectées:")
        for name, ip in interfaces.items():
            print(f"   • {name}: {ip}")
        print()
    
    # Demander l'host
    try:
        host = input("📡 Host IP (appuyez Entree pour 0.0.0.0 - toutes interfaces): ").strip()
        if not host:
            host = "0.0.0.0"  # Accessible depuis toutes les interfaces
        
        # Demander le port
        port_input = input("🔌 Port (appuyez Entree pour 8080): ").strip()
        if not port_input:
            port = 8080
        else:
            port = int(port_input)
        
        print("\n⏳Configuration:")
        print("📡 Host:", host)
        print("🔌 Port:", port)
        
        # Afficher toutes les URLs d'accès possibles
        print("\n🌐 URLs d'accès:")
        if host == "0.0.0.0":
            print(f"   • Local: http://127.0.0.1:{port}")
            for name, ip in interfaces.items():
                print(f"   • {name}: http://{ip}:{port}")
        else:
            print(f"   • Principal: http://{host}:{port}")
        
        print("\n🚀 Demarrage du serveur...\n")
        
        app.run(host=host, port=port, debug=False)
        
    except KeyboardInterrupt:
        print("\nServeur arrete❌ Au-revoir.")
    except ValueError:
        print("Erreur: ❌ Port invalide!")
    except Exception as e:
        print("Erreur:", str(e))