# -*- coding: utf-8 -*-

import sqlite3
from threading import Thread

from flask import Flask, render_template, session, redirect, request
from werkzeug.security import generate_password_hash, check_password_hash

nvr_thread_list = []


def connect_db():
    return sqlite3.connect('./db/pinvr.db')


def disconnect_db(_db):
    _db.commit()
    _db.close()


def get_current_username():
    return session['username']


def get_user(username):
    _current_user = None

    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.execute('select * from user_list where username="' + username + '"')

    _users = _cursor.fetchall()

    if len(_users) > 0:
        _user = _users[0]
        _current_user = User(_user[0], _user[1], True)

    _cursor.close()
    disconnect_db(_db)

    return _current_user


# 유저 정보 클래스
class User(object):
    def __init__(self, username, password, salted=False):
        self.username = username
        if salted is False:
            self.password = generate_password_hash(password)
        else:
            self.password = password

    def check_password(self, password):
        return check_password_hash(self.password, password)


# NVR 스레드 클래스
class NVRThread(Thread):
    def __init__(self, root_dir='', camera_name='', stream_url='', server_port=-1):
        self.root_dir = root_dir
        self.camera_name = camera_name
        self.server_port = server_port
        self.stream_url = stream_url
        self.runnable = None

        Thread.__init__(self)

    def run(self):
        params = ' -s ' + self.root_dir + ' -n ' + self.camera_name + ' -O ' \
                 + str(self.server_port) + ' -r ' + self.stream_url + ' M'

        # self._runnable = envoy.run('/home/pi/opt/PiNVR/pinvr' + params)

        cmd = '/home/pi/opt/PiNVR/pinvr' + params
        cmd_args = cmd.split()

        # self.runnable = subprocess.Popen(cmd_args, shell=False)

        # call(cmd_args)

        print(params)
        # print(self._runnable.std_out)


app = Flask(__name__)

# set the secret key.  keep this really secret:
app.secret_key = 'A8(kMF5$@1X !*FKEeo(]%LWX/,?RT'


@app.route('/', methods=['GET', 'POST'])
def index():
    error = None

    if request.method == 'POST':
        _current_user = get_user(request.form['username'])

        if _current_user is not None:
            if _current_user.check_password(request.form['password']) is True:
                session['username'] = request.form['username']

                return redirect('/status')
            else:
                error = 'invalid password.'
        else:
            error = 'invalid username.'
    else:
        if 'username' in session:
            return redirect('/status')

    return render_template('login.html', error=error)


@app.route('/status')
def status():
    return render_template('status.html', username=session['username'])


@app.route('/logout')
def logout():
    # remove the username from the session if its there
    session.pop('username', None)

    return redirect('/')


@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'GET':
        if admin_data.username is get_current_username():
            return render_template('form_add.html')
    else:
        root_dir = request.form['root_dir']
        camera_name = request.form['camera_name']
        stream_url = request.form['stream_url']
        server_port = 8000

        while True:
            flag = 0
            for thread in nvr_thread_list:
                if thread.server_port == server_port:
                    break
                flag += 1

            if flag == len(nvr_thread_list):
                break
            else:
                server_port += 1

        if root_dir and camera_name and stream_url and server_port is not -1:
            _db = connect_db()
            _cursor = _db.cursor()
            _cursor.executemany(
                'insert into camera_list (camera_name, root_dir, stream_url, server_port, owner) \
                 values (?, ?, ?, ?, ?)',
                [(camera_name, root_dir, stream_url, server_port, get_current_username())])

            _cursor.close()
            disconnect_db(_db)

            nvr_thread = NVRThread(root_dir=root_dir, camera_name=camera_name, stream_url=stream_url,
                                   server_port=server_port)

            nvr_thread_list.append(nvr_thread)

            nvr_thread.start()
        else:
            print('wrong arguments in flask.')

    return redirect('/')


if __name__ == '__main__':

    # DB 테이블 생성
    db = connect_db()
    cursor = db.cursor()

    cursor.execute('CREATE TABLE if not exists camera_list( \
                    id INTEGER PRIMARY KEY AUTOINCREMENT, \
                    camera_name TEXT, \
                    root_dir TEXT, \
                    server_port INTEGhER, \
                    stream_url TEXT, \
                    owner TEXT \
                    );')

    cursor.execute('CREATE TABLE if not exists user_list( \
                    username TEXT PRIMARY KEY, \
                    password TEXT \
                    );')

    current_user = get_user('admin')

    if current_user is not None:
        admin_data = current_user
    else:
        admin_data = User(username='admin', password='admin')
        cursor = db.cursor()
        cursor.executemany('insert into user_list values (?, ?)',
                           [(admin_data.username, admin_data.password)])

    cursor.close()
    disconnect_db(db)

    # flask 실행
    app.run(host='0.0.0.0', port='1024')
