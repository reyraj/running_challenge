from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "replace_this_with_a_real_secret"

# Render PostgreSQL DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://running_challenge_db_user:jDwTumrQBFw0fArwGei08KPkEFTXuTQP@dpg-d26gocmuk2gs739ql3ug-a.virginia-postgres.render.com/running_challenge_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ─── MODELS ───────────────────────────────────────────────
class Participant(db.Model):
    __tablename__ = 'participant'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MilesLog(db.Model):
    __tablename__ = 'miles_log'
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    miles = db.Column(db.Float, nullable=False)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── ROUTES ───────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('ask.html')

@app.route('/ask', methods=['POST'])
def ask():
    answer = request.form.get('answer')
    if answer == 'yes':
        return redirect(url_for('join'))
    return redirect(url_for('decline'))

@app.route('/join', methods=['GET', 'POST'])
def join():
    if request.method == 'POST':
        fn = request.form['first_name'].strip().upper()
        li = request.form['last_initial'].strip().upper()
        name = f"{fn} {li}."

        if Participant.query.filter_by(name=name).first():
            flash("User already exists; please log in.", "warning")
            return redirect(url_for('login'))

        p = Participant(name=name)
        db.session.add(p)
        db.session.commit()
        session['participant_id'] = p.id
        return redirect(url_for('dashboard'))

    return render_template('join.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        fn = request.form['first_name'].strip().upper()
        li = request.form['last_initial'].strip().upper()
        name = f"{fn} {li}."
        p = Participant.query.filter_by(name=name).first()
        if not p:
            flash("Not found—please enroll first.", "danger")
            return redirect(url_for('join'))
        session['participant_id'] = p.id
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard', methods=['GET','POST'])
def dashboard():
    pid = session.get('participant_id')

    if not pid:
        flash("You must log in or enroll first.", "danger")
        return redirect(url_for('home'))

    participant = Participant.query.get(pid)
    if not participant:
        flash("Account not found. Please join or log in again.", "danger")
        session.pop('participant_id', None)
        return redirect(url_for('home'))

    if request.method == 'POST':
        try:
            miles = float(request.form['miles'])
        except (ValueError, KeyError):
            flash("Please enter a valid number.", "danger")
            return redirect(url_for('dashboard'))

        db.session.add(MilesLog(participant_id=pid, miles=miles))
        db.session.commit()
        flash("Congratulations on logging miles today!", "success")
        return redirect(url_for('dashboard'))

    total = (db.session
               .query(db.func.sum(MilesLog.miles))
               .filter_by(participant_id=pid)
               .scalar() or 0.0)

    top5 = (db.session
              .query(Participant.name, db.func.sum(MilesLog.miles).label('total'))
              .outerjoin(MilesLog)
              .group_by(Participant.id)
              .order_by(db.desc('total'))
              .limit(5)
              .all())

    roster = [(runner, total or 0.0) for runner, total in
              (db.session
                .query(Participant, db.func.sum(MilesLog.miles).label('total'))
                .outerjoin(MilesLog)
                .group_by(Participant.id)
                .order_by(Participant.name)
                .all())]

    return render_template('dashboard.html',
                           name=participant.name,
                           total=total,
                           top5=top5,
                           roster=roster)

@app.route('/decline')
def decline():
    return render_template('decline.html')

@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == '1541':
            session['admin'] = True
            return redirect(url_for('admin_panel'))
        flash("Bad code.", "danger")
    return render_template('admin_login.html')

@app.route('/admin', methods=['GET','POST'])
def admin_panel():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        if 'remove_miles' in request.form:
            pid = int(request.form['participant_id'])
            m = float(request.form['remove_miles'])
            db.session.add(MilesLog(participant_id=pid, miles=-abs(m)))
            db.session.commit()
            flash("Removed miles.", "info")
        if 'drop_id' in request.form:
            pid = int(request.form['drop_id'])
            MilesLog.query.filter_by(participant_id=pid).delete()
            Participant.query.filter_by(id=pid).delete()
            db.session.commit()
            flash("Runner dropped.", "info")
        return redirect(url_for('admin_panel'))

    roster = [(runner, total or 0.0) for runner, total in
              (db.session
                .query(Participant, db.func.sum(MilesLog.miles).label('total'))
                .outerjoin(MilesLog)
                .group_by(Participant.id)
                .order_by(Participant.name)
                .all())]
    return render_template('admin.html', roster=roster)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', debug=True)
