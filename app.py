from flask import Flask, request, jsonify, render_template, session, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "secret123"

# ================= DATABASE =================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///saas.db'
db = SQLAlchemy(app)

# ================= MODELS =================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100))
    password = db.Column(db.String(200))

class Villa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Integer)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    villa_name = db.Column(db.String(100))
    customer = db.Column(db.String(100))
    date = db.Column(db.String(50))

# ================= INIT DB =================
with app.app_context():
    db.create_all()

# ================= HOME =================
@app.route('/')
def home():
    villas = Villa.query.all()
    return render_template("index.html", villas=villas)

# ================= REGISTER =================
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    user = User(
        email=data['email'],
        password=generate_password_hash(data['password'])
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"msg": "Registered"})

# ================= LOGIN =================
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()

    if user and check_password_hash(user.password, data['password']):
        token = jwt.encode({
            "user": user.id,
            "exp": datetime.utcnow() + timedelta(days=1)
        }, app.secret_key, algorithm="HS256")

        return jsonify({"token": token})

    return jsonify({"msg": "Invalid"})

# ================= AUTH =================
def auth(token):
    try:
        data = jwt.decode(token, app.secret_key, algorithms=["HS256"])
        return data['user']
    except:
        return None

# ================= ADD VILLA =================
@app.route('/add-villa', methods=['POST'])
def add_villa():
    token = request.headers.get("Authorization")
    user = auth(token)

    if not user:
        return jsonify({"msg": "Unauthorized"})

    data = request.json

    villa = Villa(
        name=data['name'],
        price=data['price']
    )

    db.session.add(villa)
    db.session.commit()

    return jsonify({"msg": "Villa Added"})

# ================= BOOK =================
@app.route('/book', methods=['POST'])
def book():
    data = request.json

    booking = Booking(
        villa_name=data['villa'],
        customer=data['name'],
        date=data['date']
    )

    db.session.add(booking)
    db.session.commit()

    return jsonify({"msg": "Booked"})

# ================= DASHBOARD =================
@app.route('/dashboard')
def dashboard():
    bookings = Booking.query.all()
    return jsonify([
        {
            "villa": b.villa_name,
            "customer": b.customer,
            "date": b.date
        } for b in bookings
    ])

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
