# -*- coding: utf-8 -*-

import sqlite3
from threading import Thread

import subprocess
from flask import Flask, render_template, session, redirect, request
from werkzeug.security import generate_password_hash, check_password_hash

nvr_thread_list = []


# 유저 클래스
class User(object):
    def __init__(self, username, password, salted=False):
        self.username = username
        if salted is False:
            self.password = generate_password_hash(password)
        else:
            self.password = password

    def check_password(self, password):
        return check_password_hash(self.password, password)


# 카메라 클래스
class CameraInfo(object):
    def __init__(self, number, camera_name, root_dir, server_port, origin_url, owner):
        self.number = number
        self.camera_name = camera_name
        self.server_port = str(server_port)
        self.stream_url = 'rtsp://kimdata.iptime.org:' + self.server_port + '/' + self.camera_name
        self.origin_url = origin_url
        self.root_dir = root_dir
        self.owner = owner


def connect_db():
    return sqlite3.connect('./db/pinvr.db')


def disconnect_db(_db):
    _db.commit()
    _db.close()


def get_current_username():
    if 'username' in session:
        return session['username']
    else:
        return None


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


def get_camera_list(owner):
    _camera_list = []
    _db = connect_db()
    _cursor = _db.cursor()
    if owner is 'admin':
        _cursor.execute('select * from camera_list')
    else:
        _cursor.execute('select * from camera_list where owner="' + owner + '"')

    _item_list = _cursor.fetchall()

    if len(_item_list) > 0:
        for item in _item_list:
            _camera = CameraInfo(item[0], item[1], item[2], item[3], item[4], item[5])
            _camera_list.append(_camera)

    _cursor.close()
    disconnect_db(_db)

    return _camera_list


# NVR 스레드 클래스
class NVRThread(Thread):
    def __init__(self, root_dir='', camera_name='', origin_url='', server_port=-1):
        self.root_dir = root_dir
        self.camera_name = camera_name
        self.server_port = server_port
        self.origin_url = origin_url
        self.runnable = None

        Thread.__init__(self)

    def run(self):
        params = ' -s ' + self.root_dir + ' -n ' + self.camera_name + ' -O ' \
                 + str(self.server_port) + ' -r ' + self.origin_url + ' M'

        cmd = '/home/pi/opt/PiNVR/pinvr' + params
        cmd_args = cmd.split()

        # self._runnable = envoy.run('/home/pi/opt/PiNVR/pinvr' + cmd_args)

        self.runnable = subprocess.Popen(cmd_args, shell=False)

        # call(cmd_args)


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
    _camera_list = None

    if 'username' in session:
        _camera_list = get_camera_list(session['username'])

    return render_template('status.html', camera_list=_camera_list)


@app.route('/logout')
def logout():
    session.pop('username', None)

    return redirect('/')


@app.route('/add', methods=['GET', 'POST'])
def add():
    owner = get_current_username()

    print owner

    if owner is not None:
        if request.method == 'GET':
            return render_template('form_add.html', owner=owner)
        else:
            root_dir = request.form['root_dir']
            camera_name = request.form['camera_name']
            origin_url = request.form['origin_url']
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

            if root_dir and camera_name and origin_url and server_port is not -1:
                _db = connect_db()
                _cursor = _db.cursor()
                _cursor.executemany(
                    'insert into camera_list (camera_name, root_dir, origin_url, server_port, owner) \
                     values (?, ?, ?, ?, ?)',
                    [(camera_name, root_dir, origin_url, server_port, owner)])

                _cursor.close()
                disconnect_db(_db)

                nvr_thread = NVRThread(root_dir=root_dir, camera_name=camera_name, origin_url=origin_url,
                                       server_port=server_port)

                nvr_thread_list.append(nvr_thread)

                nvr_thread.start()

                print('nvt added.')
            else:
                print('wrong arguments in flask.')

    return redirect('/')


if __name__ == '__main__':
    # DB 테이블 생성
    db = connect_db()
    cursor = db.cursor()

    cursor.execute('CREATE TABLE if not exists camera_list( \
                    id INTEGER PRIMARY KEY AUTOINCREMENT, \
                    camera_name TEXT NOT NULL, \
                    root_dir TEXT NOT NULL, \
                    server_port INTEGER NOT NULL, \
                    origin_url TEXT NOT NULL, \
                    owner TEXT NOT NULL \
                    );')

    cursor.execute('CREATE TABLE if not exists user_list( \
                    username TEXT PRIMARY KEY NOT NULL, \
                    password TEXT NOT NULL \
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
