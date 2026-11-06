"""PHAF - Pain Has A Face: streetwear and music webstore (Flask + SQLite)."""
import json, os, secrets, sqlite3
from datetime import datetime
from functools import wraps
from urllib.parse import quote

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.utils import secure_filename

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "store.db")
UPLOADS = os.path.join(BASE, "static", "uploads")
os.makedirs(UPLOADS, exist_ok=True)

app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret-key"),
                  MAX_CONTENT_LENGTH=100 * 1024 * 1024)
ADMIN_PASSWORD = os.environ.get("PHAF_ADMIN_PASSWORD", "phaf-admin")  # CHANGE THIS

CATS = [("tee", "T-Shirts"), ("hood", "Hoodies"), ("cap", "Caps"), ("bucket", "Bucket Hats"),
        ("shorts", "Shorts"), ("socks", "Socks"), ("bag", "School Bags")]
SIZED = {"tee", "hood", "shorts"}
STATUSES = ["New", "Paid", "Packed", "Shipped", "Delivered", "Cancelled"]
IMG_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
AUDIO_EXT = {"mp3", "m4a", "wav", "ogg", "aac", "mp4"}

SEED_PRODUCTS = [
    ("PHAF Script Tee", "tee", 399, "#5c2c1c", "#f7f1e3", "script"), ("Sunrise Tee", "tee", 399, "#b9cde3", "#2b1208", "sun"),
    ("Cream Statement Tee", "tee", 379, "#efe9d2", "#2b1208", "txt"), ("Orange Dot Tee", "tee", 399, "#f6f4ee", "#2b1208", "dot"),
    ("Abstract Art Tee", "tee", 399, "#f2f0ea", "#2b1208", "art"), ("Stone Grey Tee", "tee", 379, "#b9b8b4", "#2b1208", "txt"),
    ("No Way Back Tee", "tee", 399, "#a3a2a0", "#2b1208", "txt2"), ("PHAF Badge Tee", "tee", 399, "#f6f4ee", "#2b1208", "badge"),
    ("Tan Script Tee", "tee", 399, "#c9b49a", "#4a2012", "script"), ("Sand Script Tee", "tee", 399, "#d6c4aa", "#4a2012", "script"),
    ("Latte Script Tee", "tee", 399, "#cdb89a", "#4a2012", "script"), ("Cocoa Script Tee", "tee", 399, "#6b3a28", "#f7f1e3", "script"),
    ("PHAF Hoodie", "hood", 749, "#e6d9bf", "#4a2012", ""), ("Black PHAF Hoodie", "hood", 749, "#161616", "#ffffff", ""),
    ("PHAF Cap", "cap", 249, "#111111", "#ffffff", ""), ("Brown PHAF Cap", "cap", 249, "#5c2c1c", "#f7f1e3", ""),
    ("PHAF Bucket Hat", "bucket", 199, "#111111", "#ffffff", ""), ("Sand Bucket Hat", "bucket", 199, "#cdb89a", "#4a2012", ""),
    ("PHAF Shorts", "shorts", 399, "#111111", "#ffffff", ""), ("Brown PHAF Shorts", "shorts", 399, "#5c2c1c", "#f7f1e3", ""),
    ("PHAF Socks", "socks", 149, "#ffffff", "#111111", ""), ("Black PHAF Socks", "socks", 149, "#222222", "#ffffff", ""),
    ("PHAF School Bag", "bag", 599, "#161616", "#ffffff", ""), ("Brown School Bag", "bag", 599, "#5c2c1c", "#f7f1e3", ""),
]
SEED_TRACKS = [("Pain Has A Face", 195), ("Township Dreams", 200), ("Real Life", 192), ("Fight Back", 220), ("South Africa", 208)]
DEFAULT_SETTINGS = {"whatsapp": "27780699101", "email": "nkuthalombilini61@gmail.com", "bank": "",
                    "pay_url": "", "cod": "1", "shipping": "0"}


# ---------------------------------------------------------------- database
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT, cat TEXT, price REAL, color TEXT, ink TEXT,
        graphic TEXT DEFAULT '', image TEXT DEFAULT '', stock INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS tracks(id INTEGER PRIMARY KEY, title TEXT, duration INTEGER DEFAULT 180, file TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, ref TEXT UNIQUE, name TEXT, phone TEXT, email TEXT, address TEXT,
        city TEXT, code TEXT, note TEXT, pay TEXT, shipping REAL, total REAL, status TEXT DEFAULT 'New', items TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    if not conn.execute("SELECT 1 FROM products LIMIT 1").fetchone():
        conn.executemany("INSERT INTO products(name,cat,price,color,ink,graphic) VALUES(?,?,?,?,?,?)", SEED_PRODUCTS)
        conn.executemany("INSERT INTO tracks(title,duration) VALUES(?,?)", SEED_TRACKS)
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
    conn.commit()
    conn.close()


def settings():
    return {r["key"]: r["value"] for r in db().execute("SELECT * FROM settings")}


def save_upload(field, allowed):
    f = request.files.get(field)
    if not f or not f.filename:
        return ""
    ext = f.filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed:
        flash(f"File type .{ext} is not allowed here.", "err")
        return ""
    name = f"{secrets.token_hex(6)}_{secure_filename(f.filename)}"
    f.save(os.path.join(UPLOADS, name))
    return name


def remove_upload(name):
    if name:
        try:
            os.remove(os.path.join(UPLOADS, name))
        except OSError:
            pass


# -------------------------------------------------------------------- cart
def cart_lines():
    lines = []
    for key, qty in session.get("cart", {}).items():
        pid, _, size = key.partition("|")
        p = db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
        if p and p["stock"]:
            lines.append({"key": key, "p": p, "size": size, "qty": qty, "sub": qty * p["price"]})
    return lines


app.jinja_env.globals["money"] = lambda n: f"R{n:,.2f}"


@app.context_processor
def inject():
    cfg = settings()
    return {"cfg": cfg, "cats": CATS, "SIZED": SIZED, "cart_count": sum(session.get("cart", {}).values()),
            "is_admin": session.get("admin", False), "money": lambda n: f"R{n:,.2f}",
            "ship": float(cfg.get("shipping") or 0)}


# ------------------------------------------------------------------ public
@app.route("/")
def index():
    tees = db().execute("SELECT * FROM products WHERE cat='tee' ORDER BY id LIMIT 8").fetchall()
    return render_template("index.html", tees=tees)


@app.route("/shop")
def shop():
    cat, q = request.args.get("cat", ""), request.args.get("q", "").strip()
    sql, args = "SELECT * FROM products WHERE 1=1", []
    if cat:
        sql += " AND cat=?"; args.append(cat)
    if q:
        sql += " AND name LIKE ?"; args.append(f"%{q}%")
    return render_template("shop.html", products=db().execute(sql + " ORDER BY id", args).fetchall(), cat=cat, q=q)


@app.route("/product/<int:pid>")
def product(pid):
    p = db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone() or abort(404)
    more = db().execute("SELECT * FROM products WHERE id!=? ORDER BY cat=? DESC, id LIMIT 4", (pid, p["cat"])).fetchall()
    return render_template("product.html", p=p, more=more)


@app.route("/cart")
def cart():
    return render_template("cart.html", lines=cart_lines())


@app.post("/cart/add")
def cart_add():
    pid, size = request.form.get("id", ""), request.form.get("size", "")
    p = db().execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p or not p["stock"]:
        flash("That item is sold out.", "err")
        return redirect(request.referrer or url_for("shop"))
    c = session.get("cart", {})
    key = f"{pid}|{size if p['cat'] in SIZED else ''}"
    c[key] = c.get(key, 0) + 1
    session["cart"] = c
    flash(f"{p['name']} added to your cart.", "ok")
    return redirect(request.form.get("next") or request.referrer or url_for("shop"))


@app.post("/cart/update")
def cart_update():
    c = session.get("cart", {})
    key, op = request.form["key"], request.form["op"]
    if key in c:
        c[key] += 1 if op == "inc" else -1
        if op == "del" or c[key] <= 0:
            c.pop(key)
    session["cart"] = c
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    lines = cart_lines()
    if not lines:
        flash("Your cart is empty.", "err")
        return redirect(url_for("shop"))
    cfg = settings()
    ship = float(cfg.get("shipping") or 0)
    total = sum(l["sub"] for l in lines) + ship
    pays = []
    if cfg.get("bank"): pays.append(("eft", "EFT / bank transfer"))
    if cfg.get("cod") == "1": pays.append(("cod", "Cash on delivery"))
    if cfg.get("pay_url"): pays.append(("card", "Pay by card (secure payment link)"))
    if not pays: pays.append(("arrange", "Arrange payment with the store"))
    if request.method == "POST":
        f = {k: request.form.get(k, "").strip() for k in ("name", "phone", "email", "address", "city", "code", "note", "pay")}
        if not (f["name"] and f["phone"] and f["address"] and f["city"]):
            flash("Please fill in name, phone, address and city.", "err")
        elif f["pay"] not in [p[0] for p in pays]:
            flash("Choose a payment method.", "err")
        else:
            ref = "PHAF-" + secrets.token_hex(3).upper()
            items = [{"name": l["p"]["name"], "size": l["size"], "qty": l["qty"], "price": l["p"]["price"]} for l in lines]
            db().execute("INSERT INTO orders(ref,name,phone,email,address,city,code,note,pay,shipping,total,items,created)"
                         " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (ref, f["name"], f["phone"], f["email"], f["address"], f["city"], f["code"], f["note"], f["pay"],
                          ship, total, json.dumps(items), datetime.now().strftime("%Y-%m-%d %H:%M")))
            db().commit()
            session["cart"] = {}
            return redirect(url_for("done", ref=ref))
    return render_template("checkout.html", lines=lines, pays=pays, total=total)


@app.route("/order/<ref>")
def done(ref):
    o = db().execute("SELECT * FROM orders WHERE ref=?", (ref,)).fetchone() or abort(404)
    items = json.loads(o["items"])
    txt = (f"NEW PHAF ORDER {o['ref']}\n" + "\n".join(f"{i['qty']} x {i['name']}" + (f" ({i['size']})" if i['size'] else "")
           for i in items) + f"\nTOTAL: R{o['total']:.2f}\nName: {o['name']}\nPhone: {o['phone']}")
    return render_template("done.html", o=o, items=items, wa=quote(txt))


@app.route("/music")
def music():
    return render_template("music.html", tracks=db().execute("SELECT * FROM tracks ORDER BY id").fetchall())


@app.route("/about")
def about():
    return render_template("page.html", title="ABOUT PHAF", body="PHAF means Pain Has A Face. We are a South African movement "
                           "built on fashion, music and expression. Every tee, hoodie, cap and album turns pain into something you can wear and feel.")


@app.route("/contact")
def contact():
    return render_template("page.html", title="CONTACT", body="Orders, collabs or bookings - message us.", contact=True)


# ------------------------------------------------------------------- admin
def admin_only(fn):
    @wraps(fn)
    def w(*a, **k):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*a, **k)
    return w


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin_orders"))
        flash("Wrong password.", "err")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@admin_only
def admin_orders():
    rows = db().execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    return render_template("admin/orders.html", orders=[(o, json.loads(o["items"])) for o in rows], statuses=STATUSES)


@app.post("/admin/order/<int:oid>")
@admin_only
def order_status(oid):
    st = request.form.get("status")
    if st in STATUSES:
        db().execute("UPDATE orders SET status=? WHERE id=?", (st, oid)); db().commit()
    return redirect(url_for("admin_orders"))


@app.route("/admin/products")
@admin_only
def admin_products():
    return render_template("admin/products.html", products=db().execute("SELECT * FROM products ORDER BY id DESC").fetchall())


@app.post("/admin/products/save")
@admin_only
def product_save():
    f, pid = request.form, request.form.get("id")
    img = save_upload("image", IMG_EXT)
    vals = [f["name"], f["cat"], float(f.get("price") or 0), 1 if f.get("stock") else 0]
    if pid:
        if img:
            remove_upload(db().execute("SELECT image FROM products WHERE id=?", (pid,)).fetchone()["image"])
            db().execute("UPDATE products SET image=? WHERE id=?", (img, pid))
        db().execute("UPDATE products SET name=?,cat=?,price=?,stock=? WHERE id=?", vals + [pid])
    else:
        db().execute("INSERT INTO products(name,cat,price,stock,color,ink,image) VALUES(?,?,?,?,?,?,?)",
                     vals + ["#2b1208", "#f7f1e3", img])
    db().commit()
    flash("Product saved.", "ok")
    return redirect(url_for("admin_products"))


@app.post("/admin/products/<int:pid>/delete")
@admin_only
def product_delete(pid):
    p = db().execute("SELECT image FROM products WHERE id=?", (pid,)).fetchone()
    if p:
        remove_upload(p["image"])
        db().execute("DELETE FROM products WHERE id=?", (pid,)); db().commit()
    return redirect(url_for("admin_products"))


@app.route("/admin/tracks")
@admin_only
def admin_tracks():
    return render_template("admin/tracks.html", tracks=db().execute("SELECT * FROM tracks ORDER BY id").fetchall())


@app.post("/admin/tracks/save")
@admin_only
def track_save():
    f, tid = request.form, request.form.get("id")
    audio = save_upload("audio", AUDIO_EXT)
    if tid:
        if audio:
            remove_upload(db().execute("SELECT file FROM tracks WHERE id=?", (tid,)).fetchone()["file"])
            db().execute("UPDATE tracks SET file=? WHERE id=?", (audio, tid))
        db().execute("UPDATE tracks SET title=?,duration=? WHERE id=?", (f["title"], int(f.get("duration") or 180), tid))
    else:
        db().execute("INSERT INTO tracks(title,duration,file) VALUES(?,?,?)", (f["title"], int(f.get("duration") or 180), audio))
    db().commit()
    flash("Track saved.", "ok")
    return redirect(url_for("admin_tracks"))


@app.post("/admin/tracks/<int:tid>/delete")
@admin_only
def track_delete(tid):
    t = db().execute("SELECT file FROM tracks WHERE id=?", (tid,)).fetchone()
    if t:
        remove_upload(t["file"])
        db().execute("DELETE FROM tracks WHERE id=?", (tid,)); db().commit()
    return redirect(url_for("admin_tracks"))


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_only
def admin_settings():
    if request.method == "POST":
        for k in DEFAULT_SETTINGS:
            v = "1" if k == "cod" and request.form.get(k) else ("0" if k == "cod" else request.form.get(k, "").strip())
            db().execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))
        db().commit()
        flash("Settings saved.", "ok")
    return render_template("admin/settings.html")


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
