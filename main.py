import os
from datetime import timedelta, datetime
from flask import Flask, redirect, url_for, render_template, request, flash, send_from_directory
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
from flask_moment import Moment
from flask_socketio import SocketIO, send, emit
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from sqlalchemy import create_engine
from werkzeug.exceptions import abort
from werkzeug.utils import secure_filename
from wtforms import StringField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from wtforms.widgets import PasswordInput

UPLOAD_FOLDER = 'C:/Users/srkz/PycharmProjects/flaskWebsite/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


def byte_units(value, units=-1):
    UNITS = ('Bytes', 'KB', 'MB', 'GB', 'TB', 'EB', 'ZB', 'YB')
    i = 1
    value /= 1000.0
    while value > 1000 and (units == -1 or i < units) and i + 1 < len(UNITS):
        value /= 1000.0
        i += 1
    return f'{round(value, 3):.3f} {UNITS[i]}'


app = Flask(__name__, instance_path='C:/Users/srkz/PycharmProjects/flaskWebsite/uploads/')
app.secret_key = "mundialdoqatarcomprado"  # decriptar os dados da sessao
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.sqlite3'
app.config['SECRET_KEY'] = 'cristianoreinaldo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.permanent_session_lifetime = timedelta(minutes=15)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000
app.add_url_rule(
    "/uploads/<name>", endpoint="download_file", build_only=True
)

app.jinja_env.filters.update(byte_units=byte_units)


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
io = SocketIO(app)
moment = Moment(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

messages = []

engine = create_engine("mysql+pymysql://user:pw@host/db", pool_pre_ping=True)


@app.before_first_request
def create_table():
    db.create_all()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(80), nullable=False)


class EmployeeModel(db.Model):
    __tablename__ = "table"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer(), unique=True)
    name = db.Column(db.String(20))
    age = db.Column(db.Integer())
    position = db.Column(db.String(80))

    def __init__(self, employee_id, name, age, position):
        self.employee_id = employee_id
        self.name = name
        self.age = age
        self.position = position

    def __repr__(self):
        return f"{self.name}:{self.employee_id}"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/data/create', methods=['GET', 'POST'])
def create():
    if request.method == 'GET':
        return render_template('createpage.html')

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        name = request.form['name']
        age = request.form['age']
        position = request.form['position']
        employee = EmployeeModel(employee_id=employee_id, name=name, age=age, position=position)
        db.session.add(employee)
        db.session.commit()
        return redirect('/data')


@app.route('/data')
def RetrieveList():
    employees = EmployeeModel.query.all()
    return render_template('datalist.html', employees=employees)


@app.route('/data/<int:id>')
def RetrieveEmployee(id):
    employee = EmployeeModel.query.filter_by(employee_id=id).first()
    if employee:
        return render_template('data.html', employee=employee)
    return f"O empregado com o ID = {id} ainda não existe."


@app.route('/data/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    employee = EmployeeModel.query.filter_by(employee_id=id).first()
    if request.method == 'POST':
        if employee:
            db.session.delete(employee)
            db.session.commit()

            name = request.form['name']
            age = request.form['age']
            position = request.form['position']
            employee = EmployeeModel(employee_id=id, name=name, age=age, position=position)

            db.session.add(employee)
            db.session.commit()
            return redirect(f'/data/'+str(id))
        return f"Employee with id = {id} não existe"

    return render_template('update.html', employee=employee)


@app.route('/data/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    employee = EmployeeModel.query.filter_by(employee_id=id).first()
    if request.method == 'POST':
        if employee:
            db.session.delete(employee)
            db.session.commit()
            return redirect('/data')
        abort(404)

    return render_template('delete.html')


class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})

    password = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Password"},
                           widget=PasswordInput(hide_value=False))

    submit = SubmitField("Registar")

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(username=username.data).first()

        if existing_user_username:
            raise ValidationError("Esse nome de usuario já existe!")


class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})

    password = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Password"},
                           widget=PasswordInput(hide_value=False))

    submit = SubmitField("Login")


@io.on('sendMessage')
def send_message_handle(msg):
    messages.append(msg)
    emit('getMessage', msg, json=True, broadcast=True)


@io.on('message')
def message_handler(msg):
    send(messages)


@app.route("/", methods=["POST", "GET"])
def home():
    return render_template("index.html")


@app.route("/register", methods=["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template("register.html", form=form)


@app.route('/data/<id>')
def RetrieveSingleUser(id):
    employees = EmployeeModel.query.filter_by(employee_id=id).first()
    if employees:
        return render_template('createpage.html', employees=employees)
    return f"Utilizador ={id} não existe"


@app.route("/view")
def view():
    return render_template("view.html", values=User.query.all())


@app.route("/login", methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('dashboard'))
            else:
                flash("Utilizador ou password errada!")
        else:
            flash("Utilizador ou password errada!")

    return render_template('login.html', form=form)


@app.route("/dashboard", methods=['POST', 'GET'])
@login_required
def dashboard():
    return render_template('dashboard.html')


@app.route("/logout", methods=['POST', 'GET'])
@login_required
def logout():
    logout_user()
    flash("Logout efetuado com sucesso!", "info")
    return redirect(url_for("login"))


@app.route("/chatroom", methods=['POST', 'GET'])
def chatroom():
    return render_template('chatroom.html')


@app.route('/uploads')
@login_required
def upload():
    return render_template('uploads.html')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/success', methods=['POST'])
def success():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Sem ficheiro selecionado')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Sem ficheiro selecionado')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return render_template('acknowledgement.html')


def get_files(target):
    for file in os.listdir(target):
        path = os.path.join(target, file)
        if os.path.isfile(path):
            yield (
                file,
                datetime.utcfromtimestamp(os.path.getmtime(path)),
                os.path.getsize(path)
            )


@app.route('/download')
@login_required
def maindown():
    files = get_files(app.config['UPLOAD_FOLDER'])
    return render_template('download.html', **locals())


@app.route('/download/<path:filename>')
@login_required
def download(filename):
    print(app.root_path)
    full_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    print(full_path)
    return send_from_directory(full_path, filename)


if __name__ == "__main__":
    io.run(app, host="localhost", debug=True)
