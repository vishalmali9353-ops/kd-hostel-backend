import os
from datetime import datetime
from functools import wraps

import cloudinary
import cloudinary.uploader
from bson.objectid import ObjectId
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_pymongo import PyMongo
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from modules import MODULES

app = Flask(__name__)
app.config.from_object(Config)

# Frontend (github.io) aur backend (onrender.com) alag sites hain,
# isliye login cookie cross-site bhejne ke liye ye zaroori hai.
app.config.update(SESSION_COOKIE_SAMESITE="None", SESSION_COOKIE_SECURE=True)

CORS(app, supports_credentials=True, origins=[app.config["FRONTEND_ORIGIN"]])

mongo = PyMongo(app)
db = mongo.db

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please login to access the faculty panel."

# --- Cloudinary setup (permanent file storage) ---
cloudinary.config(
    cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
    api_key=app.config["CLOUDINARY_API_KEY"],
    api_secret=app.config["CLOUDINARY_API_SECRET"],
)

ALLOWED_EXT = {"pdf", "ppt", "pptx", "doc", "docx", "jpg", "jpeg", "png"}


class AdminUser(UserMixin):
    def __init__(self, doc):
        self.id = str(doc["_id"])
        self.username = doc["username"]
        self.role = doc.get("role", "admin")


@login_manager.user_loader
def load_user(user_id):
    doc = db.users.find_one({"_id": ObjectId(user_id)})
    return AdminUser(doc) if doc else None


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user_doc = db.users.find_one({"username": username})
        if user_doc and check_password_hash(user_doc["password"], password):
            login_user(AdminUser(user_doc))
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    counts = {key: db[key].count_documents({}) for key in MODULES}
    return render_template("dashboard.html", modules=MODULES, counts=counts)


def _parse_form(fields):
    data = {}
    for f in fields:
        if f["type"] == "checkbox":
            data[f["name"]] = request.form.get(f["name"]) is not None
            continue
        if f["type"] == "file":
            continue
        value = request.form.get(f["name"], "").strip()
        if f["type"] == "number":
            try:
                value = int(value) if value != "" else 0
            except ValueError:
                value = 0
        data[f["name"]] = value
    return data


def _handle_file_upload(fields):
    """Uploads any file fields to Cloudinary, returns dict of {field_name: secure_url}."""
    saved = {}
    for f in fields:
        if f["type"] == "file":
            file = request.files.get(f["name"])
            if file and file.filename:
                ext = file.filename.rsplit(".", 1)[-1].lower()
                if ext in ALLOWED_EXT:
                    try:
                        result = cloudinary.uploader.upload(
                            file,
                            resource_type="auto",
                            folder="kd_hostel_notices",
                        )
                        saved[f["name"]] = result["secure_url"]
                    except Exception as e:
                        flash(f"Document upload failed: {str(e)}. Record saved without document.", "warning")
    return saved


@app.route("/admin/<module>")
@login_required
def list_items(module):
    if module not in MODULES:
        abort(404)
    items = list(db[module].find().sort("_id", -1))
    return render_template(
        "module_list.html",
        module_key=module,
        module=MODULES[module],
        items=items,
    )


@app.route("/admin/<module>/add", methods=["POST"])
@login_required
def add_item(module):
    if module not in MODULES:
        abort(404)
    data = _parse_form(MODULES[module]["fields"])
    data.update(_handle_file_upload(MODULES[module]["fields"]))
    data["created_at"] = datetime.utcnow()
    db[module].insert_one(data)
    flash(f"{MODULES[module]['label']} record added.", "success")
    return redirect(url_for("list_items", module=module))


@app.route("/admin/<module>/edit/<item_id>", methods=["POST"])
@login_required
def edit_item(module, item_id):
    if module not in MODULES:
        abort(404)
    data = _parse_form(MODULES[module]["fields"])
    uploaded = _handle_file_upload(MODULES[module]["fields"])
    data.update(uploaded)
    db[module].update_one({"_id": ObjectId(item_id)}, {"$set": data})
    flash(f"{MODULES[module]['label']} record updated.", "success")
    return redirect(url_for("list_items", module=module))


@app.route("/admin/<module>/delete/<item_id>", methods=["POST"])
@login_required
def delete_item(module, item_id):
    if module not in MODULES:
        abort(404)
    db[module].delete_one({"_id": ObjectId(item_id)})
    flash(f"{MODULES[module]['label']} record deleted.", "info")
    return redirect(url_for("list_items", module=module))


@app.route("/api/notices")
def api_notices():
    notices = list(db.notices.find().sort("_id", -1))
    notices.sort(key=lambda n: not n.get("pinned", False))
    for n in notices:
        n["_id"] = str(n["_id"])
        n["created_at"] = n.get("created_at", "").isoformat() if n.get("created_at") else ""
        if n.get("document"):
            n["document_url"] = n["document"]  # Cloudinary already returns full URL
    return {"notices": notices}


@app.route("/api/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or request.form
    student = {
        "name": (payload.get("name") or "").strip(),
        "gender": (payload.get("gender") or "").strip(),
        "dob": (payload.get("dob") or "").strip(),
        "phone": (payload.get("phone") or "").strip(),
        "email": (payload.get("email") or "").strip(),
        "aadhar": (payload.get("aadhar") or "").strip(),
        "course": (payload.get("course") or "").strip(),
        "year": (payload.get("year") or "").strip(),
        "roll_no": (payload.get("roll_no") or "").strip(),
        "guardian": (payload.get("guardian") or "").strip(),
        "guardian_mobile": (payload.get("guardian_mobile") or "").strip(),
        "address": (payload.get("address") or "").strip(),
        "room_no": "",
        "created_at": datetime.utcnow(),
    }
    if not student["name"] or not student["roll_no"] or not student["phone"]:
        return {"success": False, "message": "Name, Enrollment No. and Mobile are required."}, 400

    result = db.students.insert_one(student)
    return {"success": True, "message": "Registration successful!", "id": str(result.inserted_id)}, 201


# =====================================================================
#  SMART ROOM ALLOCATION
#  Collections used:
#    rooms        -> room_no, block, capacity, occupied, status  (existing module)
#    students     -> roll_no, room_no ...                         (existing module)
#    allocations  -> NEW: kaun si room mein kaun hai
#    waiting      -> NEW: jinko bed nahi mili
# =====================================================================

# Girls block ke room numbers andaaza se hain -- asli numbers ke hisaab se badal lena.
ROOM_LAYOUT = {
    "Boys": (["B%03d" % n for n in range(1, 12)]            # B001-B011 (ground)
             + ["B%d" % (100 + n) for n in range(1, 12)]    # B101-B111 (1st)
             + ["B%d" % (200 + n) for n in range(1, 11)]),  # B201-B210 (2nd)
    "Girls": (["G%03d" % n for n in range(1, 10)]           # G001-G009 (ground)
              + ["G%d" % (100 + n) for n in range(1, 10)]   # G101-G109 (1st)
              + ["G%d" % (200 + n) for n in range(1, 11)]), # G201-G210 (2nd)
}

BLOCKED_STATUS = ["Under Maintenance", "Full"]


def api_login_required(fn):
    """Faculty login chahiye; login na ho to redirect ki jagah JSON 401 deta hai."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return {"success": False, "message": "Faculty login required."}, 401
        return fn(*args, **kwargs)
    return wrapper


def _floor_of(room_no):
    """B001 -> 0 (ground), B101 -> 1, B201 -> 2."""
    try:
        return int(str(room_no)[1])
    except (ValueError, IndexError):
        return 0


def _norm_block(value):
    v = (value or "").strip().lower()
    if "girl" in v:
        return "Girls"
    if "boy" in v:
        return "Boys"
    return None


def _parse_floor(value):
    v = str(value if value is not None else "").strip().lower()
    if v in ("", "any", "none"):
        return None
    if "ground" in v or v.startswith("0"):
        return 0
    if v.startswith("1") or "first" in v:
        return 1
    if v.startswith("2") or "second" in v:
        return 2
    return None


def _truthy(value):
    return value is True or str(value).strip().lower() in ("1", "true", "on", "yes")


def _iso(dt):
    return dt.isoformat() + "Z" if dt else ""


def _ser_alloc(a):
    return {
        "id": str(a["_id"]),
        "name": a.get("name", ""),
        "roll_no": a.get("roll_no", ""),
        "course": a.get("course", ""),
        "year": a.get("year", ""),
        "block": a.get("block", ""),
        "room_no": a.get("room_no", ""),
        "time": _iso(a.get("created_at")),
    }


def _find_candidate_rooms(block, floor_pref, ground_needed, course, year):
    """Available rooms ko best-first order mein deta hai.
    Order: pasandida floor -> same course+year roommates -> khali room -> mixed room."""
    rooms = list(db.rooms.find({
        "block": block,
        "status": {"$nin": BLOCKED_STATUS},
        "$expr": {"$lt": ["$occupied", "$capacity"]},
    }))
    if ground_needed:
        rooms = [r for r in rooms if _floor_of(r["room_no"]) == 0]
    if not rooms:
        return []

    mates = {}
    for a in db.allocations.find({"room_no": {"$in": [r["room_no"] for r in rooms]}}):
        mates.setdefault(a["room_no"], []).append(a)

    course_l = (course or "").strip().lower()
    year_l = (year or "").strip().lower()

    def score(r):
        floor_penalty = 0 if (floor_pref is None or _floor_of(r["room_no"]) == floor_pref) else 1
        roommates = mates.get(r["room_no"], [])
        if not roommates:
            group = 1  # khali room
        elif any((m.get("course", "").strip().lower() == course_l
                  and m.get("year", "").strip().lower() == year_l) for m in roommates):
            group = 0  # same course + year
        else:
            group = 2  # mixed
        return (floor_penalty, group, r["room_no"])

    return sorted(rooms, key=score)


def _try_allocate(person):
    """Bed dhoondhkar allot karta hai. Mil jaye to allocation dict, warna None."""
    for room in _find_candidate_rooms(person["block"], person.get("floor_pref"),
                                      person.get("ground_needed", False),
                                      person["course"], person["year"]):
        # Atomic update: do log ek saath aaye to bhi room overbook nahi hoga.
        res = db.rooms.update_one(
            {"_id": room["_id"],
             "status": {"$nin": BLOCKED_STATUS},
             "$expr": {"$lt": ["$occupied", "$capacity"]}},
            {"$inc": {"occupied": 1}},
        )
        if res.modified_count != 1:
            continue  # kisi aur ne bed le li, agla room try karo

        db.rooms.update_one(
            {"_id": room["_id"], "$expr": {"$gte": ["$occupied", "$capacity"]}},
            {"$set": {"status": "Full"}},
        )
        alloc = {
            "name": person["name"],
            "roll_no": person["roll_no"],
            "course": person["course"],
            "year": person["year"],
            "block": person["block"],
            "room_no": room["room_no"],
            "floor": _floor_of(room["room_no"]),
            "created_at": datetime.utcnow(),
        }
        db.allocations.insert_one(alloc)
        db.students.update_many({"roll_no": person["roll_no"]},
                                {"$set": {"room_no": room["room_no"]}})
        return alloc
    return None


def _promote_waiting(block):
    """Bed khali hone par us block ke sabse pehle waiting student ko room dete hain."""
    for w in db.waiting.find({"block": block}).sort("created_at", 1):
        alloc = _try_allocate({
            "name": w["name"], "roll_no": w["roll_no"], "course": w["course"],
            "year": w["year"], "block": w["block"],
            "floor_pref": w.get("floor_pref"),
            "ground_needed": w.get("ground_needed", False),
        })
        if alloc:
            db.waiting.delete_one({"_id": w["_id"]})
            return alloc
    return None


@app.route("/setup-rooms-kdhostel2026")
@login_required
def setup_rooms():
    created = 0
    for block, numbers in ROOM_LAYOUT.items():
        for num in numbers:
            if not db.rooms.find_one({"room_no": num}):
                db.rooms.insert_one({
                    "room_no": num,
                    "block": block,
                    "capacity": 3,
                    "occupied": 0,
                    "status": "Available",
                    "created_at": datetime.utcnow(),
                })
                created += 1
    return {"created_rooms": created, "total_rooms": db.rooms.count_documents({})}


@app.route("/api/room-stats")
def api_room_stats():
    """Public: sirf counts, kisi student ka naam nahi."""
    total = occupied = available = 0
    blocks = {"Boys": {"total": 0, "occupied": 0}, "Girls": {"total": 0, "occupied": 0}}
    for r in db.rooms.find():
        cap = r.get("capacity", 0)
        occ = min(r.get("occupied", 0), cap)
        total += cap
        occupied += occ
        if r.get("status") != "Under Maintenance":
            available += cap - occ
        b = blocks.setdefault(r.get("block", "Other"), {"total": 0, "occupied": 0})
        b["total"] += cap
        b["occupied"] += occ
    for b in blocks.values():
        b["percent"] = round(b["occupied"] * 100 / b["total"]) if b["total"] else 0
    return {
        "total_beds": total,
        "occupied": occupied,
        "available": available,
        "waiting": db.waiting.count_documents({}),
        "blocks": blocks,
    }


@app.route("/api/rooms")
def api_rooms():
    """Public: room grid. Student ke naam sirf faculty login hone par milte hain."""
    block = _norm_block(request.args.get("block"))
    floor = _parse_floor(request.args.get("floor"))
    q = (request.args.get("q") or "").strip().lower()
    is_faculty = current_user.is_authenticated

    query = {"block": block} if block else {}
    rooms = list(db.rooms.find(query).sort("room_no", 1))

    mates = {}
    if is_faculty:
        for a in db.allocations.find({"room_no": {"$in": [r["room_no"] for r in rooms]}}):
            mates.setdefault(a["room_no"], []).append(a)

    out = []
    for r in rooms:
        fl = _floor_of(r["room_no"])
        if floor is not None and fl != floor:
            continue
        students = mates.get(r["room_no"], [])
        if q:
            hit = q in r["room_no"].lower() or any(
                q in s.get("name", "").lower() or q in s.get("roll_no", "") for s in students)
            if not hit:
                continue
        cap = r.get("capacity", 0)
        occ = min(r.get("occupied", 0), cap)
        maintenance = r.get("status") == "Under Maintenance"
        out.append({
            "room_no": r["room_no"],
            "block": r.get("block", ""),
            "floor": fl,
            "capacity": cap,
            "occupied": occ,
            "free": 0 if maintenance else cap - occ,
            "status": r.get("status", ""),
            "students": [{"id": str(s["_id"]), "name": s.get("name", ""),
                          "course": s.get("course", ""), "year": s.get("year", "")}
                         for s in students],
        })
    return {"rooms": out}


@app.route("/api/allocate", methods=["POST"])
@api_login_required
def api_allocate():
    p = request.get_json(silent=True) or request.form
    name = (p.get("name") or p.get("student_name") or "").strip()
    roll_no = (p.get("roll_no") or p.get("enrollment") or "").strip()
    block = _norm_block(p.get("block"))
    course = (p.get("course") or "").strip()
    year = (p.get("year") or "").strip()

    if not name or not course or not year:
        return {"success": False, "message": "Name, course and year are required."}, 400
    if not (roll_no.isdigit() and len(roll_no) == 11):
        return {"success": False, "message": "Enrollment no. 11 digit ka hona chahiye."}, 400
    if not block:
        return {"success": False, "message": "Hostel block select karein."}, 400

    existing = db.allocations.find_one({"roll_no": roll_no})
    if existing:
        return {"success": False,
                "message": "Is enrollment no. ko room %s pehle se mil chuka hai." % existing["room_no"]}, 409
    if db.waiting.find_one({"roll_no": roll_no}):
        return {"success": False, "message": "Ye student pehle se waiting list mein hai."}, 409

    person = {
        "name": name, "roll_no": roll_no, "course": course, "year": year, "block": block,
        "floor_pref": _parse_floor(p.get("floor")),
        "ground_needed": _truthy(p.get("ground_needed")),
    }
    alloc = _try_allocate(person)
    if alloc:
        return {"success": True, "status": "allocated", "room_no": alloc["room_no"],
                "message": "Room %s allot ho gaya." % alloc["room_no"]}, 201

    db.waiting.insert_one({
        "name": name, "roll_no": roll_no, "course": course, "year": year, "block": block,
        "floor_pref": person["floor_pref"], "ground_needed": person["ground_needed"],
        "created_at": datetime.utcnow(),
    })
    return {"success": True, "status": "waiting",
            "message": "Abhi koi bed khali nahi hai. Student waiting list mein add ho gaya."}, 200


@app.route("/api/allocations/recent")
@api_login_required
def api_recent_allocations():
    try:
        limit = max(1, min(int(request.args.get("limit", 10)), 50))
    except ValueError:
        limit = 10
    items = db.allocations.find().sort("created_at", -1).limit(limit)
    return {"allocations": [_ser_alloc(a) for a in items]}


@app.route("/api/waiting")
@api_login_required
def api_waiting():
    items = db.waiting.find().sort("created_at", 1)
    return {"waiting": [{
        "id": str(w["_id"]), "name": w.get("name", ""), "roll_no": w.get("roll_no", ""),
        "course": w.get("course", ""), "year": w.get("year", ""), "block": w.get("block", ""),
        "ground_needed": w.get("ground_needed", False), "time": _iso(w.get("created_at")),
    } for w in items]}


@app.route("/api/allocations/<alloc_id>", methods=["DELETE"])
@api_login_required
def api_vacate(alloc_id):
    try:
        oid = ObjectId(alloc_id)
    except Exception:
        return {"success": False, "message": "Invalid id."}, 400
    alloc = db.allocations.find_one({"_id": oid})
    if not alloc:
        return {"success": False, "message": "Allocation nahi mila."}, 404

    db.allocations.delete_one({"_id": oid})
    db.rooms.update_one({"room_no": alloc["room_no"], "occupied": {"$gt": 0}},
                        {"$inc": {"occupied": -1}})
    db.rooms.update_one({"room_no": alloc["room_no"], "sta
