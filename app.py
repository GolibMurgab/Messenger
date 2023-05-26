import flask
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import psycopg2
import datetime
import random
from string import ascii_uppercase

app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds"
socketio = SocketIO(app)

conn = psycopg2.connect(database="messanger",
                        user="postgres",
                        password="123",
                        host="localhost",
                        port="5432")

cursor = conn.cursor()


@app.route('/', methods=['POST', 'GET'])
def login():
    session["room"] = 0
    if request.method == 'POST':
        if request.form.get("login"):
            username = request.form.get('username')
            password = request.form.get('password')
            cursor.execute("SELECT * FROM users WHERE login=%s AND password=%s", (str(username), str(password)))
            records = list(cursor.fetchall())
            if ' ' in str(username) or ' ' in str(password) or str(password) == "" or str(username) == "":
                return render_template('login.html', error="Неправильный логин или пароль, запрещены символы пробела")
            if len(records) == 0:
                return render_template('login.html', error="Нет такого пользователя")
            session["name"] = username
            session["room"] = 1
            return redirect('/room')
        elif request.form.get("registration"):
            return redirect("/registration/")
    return render_template('login.html')


@app.route('/registration/', methods=['POST', 'GET'])
def registration():
    if request.method == 'POST':
        login = request.form.get('login').strip()
        password = request.form.get('password').strip()
        cursor.execute("SELECT * FROM users WHERE login=%s", (str(login),))
        records = list(cursor.fetchall())
        if len(records) != 0:
            return render_template('registration.html', error2="Данный пользователь уже зарегистрирован")
        if " " in str(login):
            return render_template('registration.html', error2="Пробел недопустим")
        elif str(login) == "":
            return render_template('registration.html', error2="Введен пустой логин")
        if " " in str(password):
            return render_template('registration.html', error3="Пробел недопустим")
        elif str(password) == "":
            return render_template('registration.html', error3="Введен пустой пароль")
        cursor.execute('INSERT INTO users (login, password) VALUES (%s, %s);', (str(login), str(password)))
        conn.commit()
        return redirect('/')
    return render_template('registration.html')


@app.route("/room",  methods=['POST', 'GET'])
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room == 0:
        return redirect('/')
    session["room"] = 1
    if request.method == "POST":
        if request.form.get("find"):
            room = request.form.get('room_number')
            cursor.execute("SELECT room FROM rooms WHERE room=%s", (str(room),))
            records = list(cursor.fetchall())
            if len(records) == 0:
                session["room"] = 1
                return render_template("room.html", error="Нет такой комнаты")
            else:
                session["room"] = room
                return render_template("room.html", messages=getmessage(room), room_number=session["room"])
        if request.form.get("create"):
            session["room"] = generate_unique_code(4)
            cursor.execute("INSERT INTO rooms VALUES (%s);", (str(session["room"]),))
            return render_template("room.html", room_number=session["room"])
        if request.form.get("leave"):
            session.clear()
            return redirect('/')
    return render_template("room.html")


@socketio.on("message")
def message(data):
    room = session.get("room")
    if room != 1 and room is not None:
        dt_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = {
            "name": session.get("name"),
            "message": data["data"],
            "time": str(dt_now)
        }
        savemessage(room, content)
        send(content, room=room)


@socketio.on("connect")
def connect():
    room = session.get("room")
    join_room(room)
    if room != 1:
        dt_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(room)
        content = {
            "name": session.get("name"),
            "message": 'Присоеденился к комнате',
            "time": str(dt_now)
        }
        send(content, room=room)


@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    leave_room(room)
    if room != 1:
        dt_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        content = {
            "name": session.get("name"),
            "message": 'Отсоединился от комнаты',
            "time": str(dt_now)
        }
        send(content, room=room)


def savemessage(room, content):
    sender = content['name']
    messages = content['message']
    time = content['time']
    cursor.execute('INSERT INTO messages (sender, messages, room, time) VALUES (%s, %s, %s, %s);',
                   (str(sender), str(messages), str(room), str(time)))
    conn.commit()


def getmessage(room):
    a = []
    cursor.execute("SELECT sender, messages, time FROM messages WHERE room = %s ORDER BY time", (str(room),))
    records = list(cursor.fetchall())
    for i in records:
        content = {
            "name": i[0],
            "message": i[1],
            "time": i[2]
        }
        a.append(content)
    return a


def generate_unique_code(length):
    cursor.execute("SELECT room from rooms")
    rooms = list(cursor.fetchall())
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)

        if code not in rooms:
            break
    return code


if __name__ == "__main__":
    socketio.run(app, debug=True)
