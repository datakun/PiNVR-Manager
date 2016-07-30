# -*- coding: utf-8 -*-
import socket
import sqlite3
from threading import Thread

import subprocess
from flask import Flask, render_template, session, redirect, request, url_for
from werkzeug.security import generate_password_hash, check_password_hash

host_ip_address = ''
host_domain = ''

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
    def __init__(self, camera_name, root_dir, server_port, origin_url, owner):
        self.camera_name = camera_name
        self.server_port = server_port
        if host_domain is '':
            base_url = host_ip_address
        else:
            base_url = host_domain
        self.stream_url = ':' + str(self.server_port) + '/' + self.camera_name
        self.origin_url = origin_url
        self.root_dir = root_dir
        self.owner = owner


def get_current_username():
    if 'username' in session:
        return session['username']
    else:
        return None


def connect_db():
    return sqlite3.connect('./pinvr.db')


def disconnect_db(_db):
    _db.commit()
    _db.close()


def get_db_user(username):
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


def get_db_camera_list(owner):
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
            _camera = CameraInfo(item[1], item[2], item[3], item[4], item[5])
            _camera_list.append(_camera)

    _cursor.close()
    disconnect_db(_db)

    return _camera_list


def get_db_camera(server_port):
    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.execute('select * from camera_list where server_port=' + server_port)

    item = _cursor.fetchone()

    if item is not None:
        _camera = CameraInfo(item[1], item[2], item[3], item[4], item[5])
    else:
        _camera = None

    _cursor.close()
    disconnect_db(_db)

    return _camera


def insert_db_camera(camera_info):
    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.executemany(
        'insert into camera_list (camera_name, root_dir, origin_url, server_port, owner) \
         values (?, ?, ?, ?, ?)',
        [(camera_info.camera_name, camera_info.root_dir, camera_info.origin_url, camera_info.server_port,
          camera_info.owner)])

    _cursor.close()
    disconnect_db(_db)


def update_db_camera(camera_info):
    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.execute('update camera_list set camera_name=?, root_dir=?, origin_url=? where server_port=?',
                    [camera_info.camera_name, camera_info.root_dir, camera_info.origin_url, camera_info.server_port])

    _cursor.close()
    disconnect_db(_db)


def run_camera(root_dir, camera_name, origin_url, server_port, owner):
    if root_dir and camera_name and origin_url and server_port is not -1:
        nvr_thread = NVSThread(root_dir=root_dir, camera_name=camera_name, origin_url=origin_url,
                               server_port=server_port)

        nvr_thread_list.append(nvr_thread)

        nvr_thread.start()

        return True
    else:
        return False


# NVR 스레드 클래스
class NVSThread(Thread):
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

        self.runnable = subprocess.Popen(cmd_args, bufsize=1024, shell=False)

        # self._runnable = envoy.run('/home/pi/opt/PiNVR/pinvr' + cmd_args)

        # call(cmd_args)

    def cmd_change_camera_name(self, camera_name):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.camera_name = camera_name
            self.runnable.communicate('-hello ' + camera_name)

    def cmd_change_root_dir(self, root_dir):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.root_dir = root_dir
            self.runnable.communicate('-hello ' + root_dir)

    def cmd_change_server_port(self, server_port):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.server_port = server_port
            self.runnable.communicate('-hello ' + str(server_port))

    def cmd_change_origin_url(self, origin_url):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.origin_url = origin_url
            self.runnable.communicate('-hello ' + origin_url)

    def cmd_kill_nvs(self):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.runnable.kill()


app = Flask(__name__)

# set the secret key.  keep this really secret:
app.secret_key = 'A8(kMF5$@1X !*FKEeo(]%LWX/,?RT'


@app.route('/', methods=['GET', 'POST'])
def index():
    global host_domain
    if host_domain is '':
        host_domain = request.headers['Host'].split(':')[0]

    error = None

    if request.method == 'POST':
        _current_user = get_db_user(request.form['username'])

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
        _camera_list = get_db_camera_list(session['username'])

    return render_template('status.html', camera_list=_camera_list)


@app.route('/logout')
def logout():
    session.pop('username', None)

    return redirect('/')


@app.route('/add', methods=['GET', 'POST'])
def add():
    owner = get_current_username()

    error = None

    if owner is not None:
        if request.method == 'GET':
            return render_template('add_nvs.html', owner=owner)
        else:
            root_dir = request.form['root_dir']
            camera_name = request.form['camera_name']
            origin_url = request.form['origin_url']
            server_port = 8000

            _camera_list = get_db_camera_list(owner)

            while True:
                flag = 0
                for item in _camera_list:
                    if item.server_port == server_port:
                        break
                    flag += 1

                if flag == len(_camera_list):
                    break
                else:
                    server_port += 1

            success = run_camera(root_dir, camera_name, origin_url, server_port, owner)

            if success is True:
                _camera_info = CameraInfo(camera_name, root_dir, server_port, origin_url, owner)
                insert_db_camera(_camera_info)

                print('nvs added.')
            else:
                error = 'Failed to add camera'
    else:
        return redirect('/')

    return redirect(url_for('status', error=error))


@app.route('/modify', methods=['POST'])
def modify():
    owner = get_current_username()

    error = None

    if owner is not None:
        form_type = request.form['type']

        if form_type == 'create_form':
            server_port = request.form['server_port']
            _camera = get_db_camera(server_port)

            if _camera is not None:
                return render_template('modify_nvs.html', camera=_camera)
            else:
                error = 'Can\'t find camera by server port: ' + server_port
        elif form_type == 'modify_nvs':
            root_dir = request.form['root_dir']
            camera_name = request.form['camera_name']
            origin_url = request.form['origin_url']
            server_port = request.form['server_port']

            print 'modify'

            # process 갱신
            for item in nvr_thread_list:
                if str(item.server_port) == server_port:
                    _camera_info = CameraInfo(camera_name, root_dir, server_port, origin_url, owner)
                    update_db_camera(_camera_info)

                    print _camera_info

                    item.cmd_change_camera_name(camera_name)
                    item.cmd_change_root_dir(root_dir)
                    item.cmd_change_origin_url(origin_url)

                    print('nvs modified.')

                    break
    else:
        return redirect('/')

    return redirect(url_for('status', error=error))


if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("google.com", 80))

    host_ip_address = s.getsockname()[0]
    host_domain = ''

    s.close()

    # DB 테이블 생성
    db = connect_db()
    cursor = db.cursor()

    cursor.execute('CREATE TABLE if not exists camera_list( \
                    id INTEGER PRIMARY KEY AUTOINCREMENT, \
                    camera_name TEXT NOT NULL, \
                    root_dir TEXT NOT NULL, \
                    server_port INTEGER NOT NULL, \
                    origin_url TEXT NOT NULL, \
                    owner TEXT NOT NULL, \
                    recording BOOL \
                    );')

    cursor.execute('CREATE TABLE if not exists user_list( \
                    username TEXT PRIMARY KEY NOT NULL, \
                    password TEXT NOT NULL \
                    );')

    current_user = get_db_user('admin')

    if current_user is not None:
        admin_data = current_user
    else:
        admin_data = User(username='admin', password='admin')
        cursor = db.cursor()
        cursor.executemany('insert into user_list values (?, ?)',
                           [(admin_data.username, admin_data.password)])

    cursor.close()
    disconnect_db(db)

    camera_list = get_db_camera_list(admin_data.username)

    for camera in camera_list:
        run_camera(camera.root_dir, camera.camera_name, camera.origin_url, camera.server_port, camera.owner)

    # flask 실행
    app.run(host='0.0.0.0', port='1024')
