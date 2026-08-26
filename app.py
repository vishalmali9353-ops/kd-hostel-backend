from datetime import datetime

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

# Allow the GitHub Pages frontend to call this API/backend with credentials
CORS(app, supports_credentials=True, origins=[app.config["FRONTEND_ORIGIN"]])

mongo = PyMongo(app)
db = mongo.db

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please login to access the faculty panel."


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
        value = request.form.get(f["name"], "").strip()
        if f["type"] == "number":
            try:
                value = int(value) if value != "" else 0
            except ValueError:
                value = 0
        data[f["name"]] = value
    return data


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
    for n in notices:
        n["_id"] = str(n["_id"])
        n["created_at"] = n.get("created_at", "").isoformat() if n.get("created_at") else ""
    return {"notices": notices}


@app.route("/api/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or request.form

    student = {
        "name": (payload.get("name") or "").strip(),
        "roll_no": (payload.get("roll_no") or "").strip(),
        "course": (payload.get("course") or "").strip(),
        "room_no": (payload.get("room_no") or "").strip(),
        "phone": (payload.get("phone") or "").strip(),
        "email": (payload.get("email") or "").strip(),
        "created_at": datetime.utcnow(),
    }

    if not student["name"] or not student["roll_no"] or not student["phone"]:
        return {"success": False, "message": "Name, Roll No. and Phone are required."}, 400

    result = db.students.insert_one(student)
    return {"success": True, "message": "Registration successful!", "id": str(result.inserted_id)}, 201


if __name__ == "__main__":
    app.run(debug=True, port=5000)
