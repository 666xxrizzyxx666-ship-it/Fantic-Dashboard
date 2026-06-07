from flask import Flask, render_template, request, redirect, session, jsonify
import aiohttp
import asyncio
import json
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fanatic_ressel_secret_2024")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GUILD_ID = 1513108386722480211
PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "fanatic2024")

WEBHOOKS = {
    "nouveautes":      os.environ.get("WH_NOUVEAUTES",   "https://discord.com/api/webhooks/1513190518413070417/8fh-HLHfzpQKrrfIi_tf3SErMbTmwwDt5T2BP35w9SP1XR92CASrTiQs36kSUViLYV69"),
    "sneakers":        os.environ.get("WH_SNEAKERS",     "https://discord.com/api/webhooks/1513190674768597092/5SDLmctbSBLN2wAFi2CFiL2aogiIfkmEAMy65vxBylGHqVFP991HwSe6ogmtDYVW0Snr"),
    "vetements":       os.environ.get("WH_VETEMENTS",    "https://discord.com/api/webhooks/1513190765944111230/Op_r6PS95s3x6f0Nm2Y67OcfsHagNzwACU5mxxQl2mXFgZEUPxmbmx3NTiLIX4urB4Y7"),
    "parfums":         os.environ.get("WH_PARFUMS",      "https://discord.com/api/webhooks/1513190863105167410/6a74VgRT0tijelIJmL4YpwGyCTeBUPkxmWhTEMz8V7aKrcOOFWXzybpY7qivWLVWWc2L"),
    "tech":            os.environ.get("WH_TECH",         "https://discord.com/api/webhooks/1513190940200927335/rXQCilAF1P3sfYOpAwMQKDhG2tPfPeYFB5chA-sr21FlfVS9l-qEXTgpp93TWMm0nfz6"),
    "accessoires":     os.environ.get("WH_ACCESSOIRES",  "https://discord.com/api/webhooks/1513191027211636926/Cs_Q7uhF-eoxPv8CxWXwfJyJE2bOm8pkd9-x-ym-kVjCP7038F5CfXiSCNJO9BJ4_ZSA"),
    "prix_du_moment":  os.environ.get("WH_PRIX",         "https://discord.com/api/webhooks/1513191113974874202/uGxLoFM2nMFhBpKbWGYZI5jqOwBb9QWBJFUzCXjxZuIZMiio-czaa1D3fBsdsX8ZQqD0"),
    "drops_a_venir":   os.environ.get("WH_DROPS",        "https://discord.com/api/webhooks/1513191196548137060/SqyyaiIDoovNrM74AAwW6oe3HZI5hl1n7ikXbiM54cpP8DZR6vZM9EdYMXBo6LMzbDzO"),
    "alertes_restocks":os.environ.get("WH_RESTOCKS",     "https://discord.com/api/webhooks/1513191298075590696/J6ATqLExI3GDoMPZVb4KS1yyBvKFh0V-pDzdZk9Z-OAq7hbNsQHbk_jvxyf0VQm6wQSd"),
    "stock_disponible":os.environ.get("WH_STOCK",        "https://discord.com/api/webhooks/1513191399678542045/CCZv1s3EDXzQrJCse109g-4PJWSoq4Y8ZAVJXjAj3ADtfR1IkCUHiRO5zzxZtqectOGR"),
    "annonces":        os.environ.get("WH_ANNONCES",     "https://discord.com/api/webhooks/1513191478057238638/TSvrF1PgVmdOzOVbO7KvbcEjyL3UedXsNWvBM8VBOoDKXlhLqOph2VVebhE3g9fJJp6b"),
}

CHANNELS = {
    "sneakers":    1513111096439865374,
    "vetements":   1513111122037706842,
    "parfums":     1513111147832938506,
    "tech":        1513111170876440628,
    "accessoires": 1513111196692123749,
    "nouveautes":  1513110903514730676,
    "prix_du_moment": 1513110932744573018,
    "stock_disponible": 1513110960947204107,
    "drops_a_venir": 1513110992173928518,
    "alertes_restocks": 1513111015498190878,
    "annonces": 1513110628112400464,
}

CATALOGUE_FILE = "catalogue.json"
LOGS_FILE      = "dashboard_logs.json"

# ─── Data helpers ──────────────────────────────────────────
def load_catalogue():
    if os.path.exists(CATALOGUE_FILE):
        with open(CATALOGUE_FILE) as f:
            return json.load(f)
    return []

def save_catalogue(data):
    with open(CATALOGUE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_logs():
    if os.path.exists(LOGS_FILE):
        with open(LOGS_FILE) as f:
            return json.load(f)
    return []

def save_log(action, details):
    logs = load_logs()
    logs.insert(0, {"action": action, "details": details,
                    "date": datetime.now().strftime("%d/%m/%Y %H:%M")})
    with open(LOGS_FILE, "w") as f:
        json.dump(logs[:50], f, indent=2)

# ─── Webhook helpers ───────────────────────────────────────
async def webhook_send(webhook_key, embed, mention_everyone=False):
    url = WEBHOOKS.get(webhook_key)
    if not url:
        return False
    async with aiohttp.ClientSession() as s:
        payload = {"embeds": [embed]}
        if mention_everyone:
            payload["content"] = "@everyone"
        async with s.post(url, json=payload) as r:
            return r.status in [200, 204]

async def webhook_send_url(url, embed):
    async with aiohttp.ClientSession() as s:
        async with s.post(url, json={"embeds": [embed]}) as r:
            return r.status in [200, 204]

def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# ─── Embed builder ─────────────────────────────────────────
CAT_COLOR  = {"sneakers":0x3498DB,"vetements":0xE74C3C,"parfums":0x9B59B6,"tech":0x2ECC71,"accessoires":0xF39C12}
CAT_EMOJI  = {"sneakers":"👟","vetements":"👔","parfums":"🧴","tech":"📱","accessoires":"👜"}
CAT_LABEL  = {"sneakers":"Sneakers","vetements":"Vêtements","parfums":"Parfums","tech":"Tech","accessoires":"Accessoires"}
STATUS_BADGE = {"disponible":"✅ Disponible","vendu":"❌ Vendu","reserve":"⏳ Réservé"}

def build_product_embed(p):
    fields = [
        {"name":"💰 Prix","value":f"**{p['prix']}**","inline":True},
        {"name":"📦 Catégorie","value":CAT_LABEL.get(p['categorie'],p['categorie']),"inline":True},
        {"name":"📊 Statut","value":STATUS_BADGE.get(p['statut'],'✅ Disponible'),"inline":True},
    ]
    if p.get("lien"):
        fields.append({"name":"🛒 Commander","value":f"[Clique ici]({p['lien']})","inline":False})
    embed = {
        "title": f"{CAT_EMOJI.get(p['categorie'],'📦')} {p['nom']}",
        "description": p.get("description",""),
        "color": CAT_COLOR.get(p['categorie'],0x7B2FBE),
        "fields": fields,
        "footer": {"text": f"Fanatic Ressel • Ref #{p['id'][:6]}"},
        "timestamp": datetime.utcnow().isoformat()
    }
    if p.get("image"):
        embed["image"] = {"url": p["image"]}
    return embed

# ─── Auth ──────────────────────────────────────────────────
def auth(f):
    @wraps(f)
    def wrapper(*a,**kw):
        if not session.get("ok"):
            return redirect("/login")
        return f(*a,**kw)
    return wrapper

# ─── Routes ────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["ok"] = True
            return redirect("/")
        return render_template("login.html", error="Mot de passe incorrect")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
@auth
def dashboard():
    logs  = load_logs()
    cat   = load_catalogue()
    dispo = sum(1 for p in cat if p.get("statut") == "disponible")
    vendu = sum(1 for p in cat if p.get("statut") == "vendu")
    guild = {"approximate_member_count": "—", "premium_subscription_count": 0, "premium_tier": 0}
    return render_template("dashboard.html", guild=guild, logs=logs,
                           total=len(cat), dispo=dispo, vendu=vendu)

@app.route("/drops")
@auth
def drops():
    cat = load_catalogue()
    dispo = [p for p in cat if p.get("statut") == "disponible"]
    return render_template("drops.html", produits=dispo,
                           produits_json=json.dumps(dispo))

@app.route("/catalogue")
@auth
def catalogue():
    cat = load_catalogue()
    cat_filter = request.args.get("cat","")
    statut_filter = request.args.get("statut","")
    if cat_filter:
        cat = [p for p in cat if p["categorie"] == cat_filter]
    if statut_filter:
        cat = [p for p in cat if p.get("statut") == statut_filter]
    return render_template("catalogue.html", produits=cat,
                           cat_filter=cat_filter, statut_filter=statut_filter)

@app.route("/annonces")
@auth
def annonces():
    return render_template("annonces.html")

@app.route("/membres")
@auth
def membres():
    return render_template("membres.html", members=[])

# ─── API Catalogue ─────────────────────────────────────────
@app.route("/api/produit", methods=["POST"])
@auth
def api_add_produit():
    data = request.json
    cat = load_catalogue()
    import uuid
    produit = {
        "id": str(uuid.uuid4()),
        "nom": data["nom"],
        "prix": data["prix"],
        "categorie": data["categorie"],
        "description": data.get("description",""),
        "image": data.get("image",""),
        "lien": data.get("lien",""),
        "statut": "disponible",
        "date": datetime.now().strftime("%d/%m/%Y"),
    }
    embed = build_product_embed(produit)
    wh_key = produit["categorie"]
    run(webhook_send(wh_key, embed))
    run(webhook_send("nouveautes", embed))
    cat.append(produit)
    save_catalogue(cat)
    save_log("Produit ajouté", f"{produit['nom']} — {produit['prix']}")
    return jsonify({"success": True, "id": produit["id"]})

@app.route("/api/produit/<pid>", methods=["GET"])
@auth
def api_get_produit(pid):
    cat = load_catalogue()
    p = next((x for x in cat if x["id"] == pid), None)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify(p)

@app.route("/api/produit/<pid>", methods=["PUT"])
@auth
def api_update_produit(pid):
    data = request.json
    cat = load_catalogue()
    p = next((x for x in cat if x["id"] == pid), None)
    if not p:
        return jsonify({"success": False})
    p.update({k: data[k] for k in ["nom","prix","categorie","description","image","lien","statut"] if k in data})
    save_catalogue(cat)
    save_log("Produit modifié", f"{p['nom']} → {p.get('statut','')}")
    return jsonify({"success": True})

@app.route("/api/produit/<pid>", methods=["DELETE"])
@auth
def api_delete_produit(pid):
    cat = load_catalogue()
    p = next((x for x in cat if x["id"] == pid), None)
    if not p:
        return jsonify({"success": False})
    cat = [x for x in cat if x["id"] != pid]
    save_catalogue(cat)
    save_log("Produit supprimé", p["nom"])
    return jsonify({"success": True})

@app.route("/api/stock", methods=["POST"])
@auth
def api_stock():
    data = request.json
    embed = {"title":"📊 STOCK DISPONIBLE","description":data["message"],
             "color":0x7B2FBE,"footer":{"text":"Fanatic Ressel • Mis à jour"},
             "timestamp":datetime.utcnow().isoformat()}
    ok = run(webhook_send("stock_disponible", embed))
    if ok: save_log("Stock mis à jour", data["message"][:50])
    return jsonify({"success": ok})

@app.route("/api/annonce", methods=["POST"])
@auth
def api_annonce():
    data = request.json
    embed = {"title":f"📣 {data['titre']}","description":data["message"],
             "color":0x7B2FBE,"footer":{"text":"Fanatic Ressel • Annonce officielle"},
             "timestamp":datetime.utcnow().isoformat()}
    if data.get("image"):
        embed["image"] = {"url": data["image"]}
    ok = run(discord_post(CHANNELS["annonces"], embed))
    if ok: save_log("Annonce postée", data["titre"])
    return jsonify({"success": ok})

@app.route("/api/annonce", methods=["POST"])
@auth
def api_annonce():
    data = request.json
    embed = {"title":f"📣 {data['titre']}","description":data["message"],
             "color":0x7B2FBE,"footer":{"text":"Fanatic Ressel • Annonce officielle"},
             "timestamp":datetime.utcnow().isoformat()}
    if data.get("image"): embed["image"] = {"url": data["image"]}
    ok = run(webhook_send("annonces", embed))
    if ok: save_log("Annonce postée", data["titre"])
    return jsonify({"success": ok})

@app.route("/api/drop", methods=["POST"])
@auth
def api_drop():
    data = request.json
    embed = {"title":f"📢 DROP À VENIR — {data['titre']}","description":data["description"],
             "color":0xFF6B35,
             "fields":[{"name":"📅 Date","value":f"**{data['date']}**","inline":True}],
             "footer":{"text":"Fanatic Ressel • Restez connectés 🔥"},
             "timestamp":datetime.utcnow().isoformat()}
    if data.get("image"): embed["image"] = {"url": data["image"]}
    ok = run(webhook_send("drops_a_venir", embed, mention_everyone=True))
    if ok: save_log("Drop annoncé", f"{data['titre']} — {data['date']}")
    return jsonify({"success": ok})

@app.route("/api/restock", methods=["POST"])
@auth
def api_restock():
    data = request.json
    embed = {"title":f"🔔 RESTOCK — {data['produit']}",
             "description":f"**{data['produit']}** est de nouveau disponible !",
             "color":0x00FF88,
             "fields":[{"name":"📦 Quantité","value":data["quantite"],"inline":True},
                       {"name":"💰 Prix","value":data["prix"],"inline":True}],
             "footer":{"text":"Fanatic Ressel • Vite avant rupture !"},
             "timestamp":datetime.utcnow().isoformat()}
    ok = run(webhook_send("alertes_restocks", embed, mention_everyone=True))
    if ok: save_log("Restock annoncé", f"{data['produit']}")
    return jsonify({"success": ok})

@app.route("/api/kick/<uid>", methods=["POST"])
@auth
def api_kick(uid):
    save_log("Kick tenté", f"User {uid} — utilise le bot Staff")
    return jsonify({"success": False, "message": "Utilise le bot Staff pour kick"})

@app.route("/api/ban/<uid>", methods=["POST"])
@auth
def api_ban(uid):
    save_log("Ban tenté", f"User {uid} — utilise le bot Staff")
    return jsonify({"success": False, "message": "Utilise le bot Staff pour ban"})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
