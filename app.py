from flask import Flask, render_template, request, redirect, session, jsonify
import aiohttp
import asyncio
import json
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "fanatic_ressel_secret_2024"

BOT_TOKEN = "MTUxMzEyNDUxNDMyMDQ4MjMyNA.GGqeaO.WHBsZwBg1ugfIRAX-qPl2nd7E4VZ8PlwTTp-c0"
GUILD_ID = 1513108386722480211
PASSWORD = "fanatic2024"

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

# ─── Discord API ───────────────────────────────────────────
async def discord_post(channel_id, embed, mention_everyone=False):
    async with aiohttp.ClientSession() as s:
        headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
        payload = {"embeds": [embed]}
        if mention_everyone:
            payload["content"] = "@everyone"
        async with s.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers, json=payload) as r:
            return r.status == 200

async def discord_edit(channel_id, message_id, embed):
    async with aiohttp.ClientSession() as s:
        headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
        async with s.patch(
            f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}",
            headers=headers, json={"embeds": [embed]}) as r:
            return r.status == 200

async def discord_delete(channel_id, message_id):
    async with aiohttp.ClientSession() as s:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        async with s.delete(
            f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}",
            headers=headers) as r:
            return r.status == 204

async def get_guild_info():
    async with aiohttp.ClientSession() as s:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        async with s.get(
            f"https://discord.com/api/v10/guilds/{GUILD_ID}?with_counts=true",
            headers=headers) as r:
            return await r.json() if r.status == 200 else {}

async def get_members():
    async with aiohttp.ClientSession() as s:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        async with s.get(
            f"https://discord.com/api/v10/guilds/{GUILD_ID}/members?limit=100",
            headers=headers) as r:
            return await r.json() if r.status == 200 else []

async def kick_member(uid, reason):
    async with aiohttp.ClientSession() as s:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        async with s.delete(
            f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{uid}",
            headers=headers, params={"reason": reason}) as r:
            return r.status == 204

async def ban_member(uid, reason):
    async with aiohttp.ClientSession() as s:
        headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
        async with s.put(
            f"https://discord.com/api/v10/guilds/{GUILD_ID}/bans/{uid}",
            headers=headers, json={"reason": reason}) as r:
            return r.status == 200

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
    guild = run(get_guild_info())
    logs  = load_logs()
    cat   = load_catalogue()
    dispo = sum(1 for p in cat if p.get("statut") == "disponible")
    vendu = sum(1 for p in cat if p.get("statut") == "vendu")
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
    members = run(get_members())
    return render_template("membres.html", members=members)

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
        "discord_message_id": None,
        "discord_channel_id": None,
    }
    embed = build_product_embed(produit)
    channel_id = CHANNELS.get(produit["categorie"])
    if channel_id:
        # On envoie dans Discord via aiohttp directement
        async def send_and_get_id():
            async with aiohttp.ClientSession() as s:
                headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
                async with s.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers=headers, json={"embeds": [embed]}) as r:
                    if r.status == 200:
                        msg = await r.json()
                        return msg.get("id")
            return None
        msg_id = run(send_and_get_id())
        produit["discord_message_id"] = msg_id
        produit["discord_channel_id"] = channel_id
        # Aussi dans nouveautés
        run(discord_post(CHANNELS["nouveautes"], embed))

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
    embed = build_product_embed(p)
    if p.get("discord_message_id") and p.get("discord_channel_id"):
        run(discord_edit(p["discord_channel_id"], p["discord_message_id"], embed))
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
    if p.get("discord_message_id") and p.get("discord_channel_id"):
        run(discord_delete(p["discord_channel_id"], p["discord_message_id"]))
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
    ok = run(discord_post(CHANNELS["stock_disponible"], embed))
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
    ok = run(discord_post(CHANNELS["drops_a_venir"], embed, mention_everyone=True))
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
    ok = run(discord_post(CHANNELS["alertes_restocks"], embed, mention_everyone=True))
    if ok: save_log("Restock annoncé", f"{data['produit']}")
    return jsonify({"success": ok})

@app.route("/api/kick/<uid>", methods=["POST"])
@auth
def api_kick(uid):
    data = request.json
    ok = run(kick_member(uid, data.get("raison","Dashboard")))
    if ok: save_log("Kick", f"User {uid}")
    return jsonify({"success": ok})

@app.route("/api/ban/<uid>", methods=["POST"])
@auth
def api_ban(uid):
    data = request.json
    ok = run(ban_member(uid, data.get("raison","Dashboard")))
    if ok: save_log("Ban", f"User {uid}")
    return jsonify({"success": ok})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
