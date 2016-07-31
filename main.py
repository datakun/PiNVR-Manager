# -*- coding: utf-8 -*-
import os
import socket
import sqlite3
import subprocess
from threading import Thread
from time import sleep

import psutil
from flask import Flask, render_template, session, redirect, request, url_for
from werkzeug.security import generate_password_hash, check_password_hash

host_ip_address = ''
host_domain = ''

nvs_thread_list = []

nvs_list = dict()

current_directory = os.path.dirname(os.path.abspath(__file__))


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
class NVSInfo(object):
    def __init__(self, camera_name, root_dir, server_port, origin_url, owner, enabled):
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
        self.alive = 'DEAD'
        self.enabled = enabled


def get_current_username():
    if 'username' in session:
        return session['username']
    else:
        return None


def connect_db():
    return sqlite3.connect(current_directory + '/pinvr.db')


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
    _camera_list = dict()
    _db = connect_db()
    _cursor = _db.cursor()
    if owner is 'admin':
        _cursor.execute('select * from camera_list')
    else:
        _cursor.execute('select * from camera_list where owner="' + owner + '"')

    _item_list = _cursor.fetchall()

    for item in _item_list:
        _camera = NVSInfo(item[1], item[2], item[3], item[4], item[5], item[6])
        _camera_list[item[3]] = _camera

    _cursor.close()
    disconnect_db(_db)

    return _camera_list


def get_db_camera(server_port):
    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.execute('select * from camera_list where server_port=' + server_port)

    item = _cursor.fetchone()

    if item is not None:
        _camera = NVSInfo(item[1], item[2], item[3], item[4], item[5], item[6])
    else:
        _camera = None

    _cursor.close()
    disconnect_db(_db)

    return _camera


def insert_db_camera(camera_info):
    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.execute(
        'insert into camera_list (camera_name, root_dir, origin_url, server_port, owner, enabled) \
         values (?, ?, ?, ?, ?, ?)',
        [camera_info.camera_name, camera_info.root_dir, camera_info.origin_url, camera_info.server_port,
         camera_info.owner, camera_info.enabled])

    _cursor.close()
    disconnect_db(_db)


def db_enable_camera(server_port, enabled=True):
    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.execute('update camera_list set enabled=? where server_port=?',
                    [enabled, server_port])

    _cursor.close()
    disconnect_db(_db)


def update_db_camera(camera_name, root_dir, origin_url, server_port):
    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.execute('update camera_list set camera_name=?, root_dir=?, origin_url=? where server_port=?',
                    [camera_name, root_dir, origin_url, server_port])

    _cursor.close()
    disconnect_db(_db)


def delete_db_camera(server_port):
    _db = connect_db()
    _cursor = _db.cursor()
    _cursor.execute('delete from camera_list where server_port=?', [server_port])

    _cursor.close()
    disconnect_db(_db)


def run_camera(root_dir, camera_name, origin_url, server_port):
    flag = 0
    _thread = None
    for thread in nvs_thread_list:
        if thread.server_port == str(server_port):
            _thread = thread

            break

        flag += 1

    if _thread is not None:
        nvs_thread_list.remove(_thread)

    nvs_thread = NVSThread(root_dir=root_dir, camera_name=camera_name, origin_url=origin_url,
                           server_port=server_port)

    nvs_thread_list.append(nvs_thread)

    nvs_thread.start()


def update_process_status():
    pids = psutil.pids()

    for thread in nvs_thread_list:
        if thread.pid in pids:
            p = psutil.Process(thread.pid)

            if thread.server_port in nvs_list:
                nvs_list[thread.server_port].alive = 'ALIVE'

            if p.status() == "zombie":
                nvs_list[thread.server_port].alive = 'ZOMBIE'
        else:
            if thread.server_port in nvs_list:
                nvs_list[thread.server_port].alive = 'DEAD'

            nvs_thread_list.remove(thread)


def is_process_alive(pid):
    pids = psutil.pids()

    if pid in pids:
        return True
    else:
        return False


# NVS 스레드 클래스
class NVSThread(Thread):
    def __init__(self, root_dir='', camera_name='', origin_url='', server_port=-1):
        self.root_dir = root_dir
        self.camera_name = camera_name
        self.server_port = server_port
        self.origin_url = origin_url
        self.runnable = None
        self.pid = None

        Thread.__init__(self)

    def run(self):
        params = ' -s ' + self.root_dir + ' -n ' + self.camera_name + ' -O ' \
                 + str(self.server_port) + ' -r ' + self.origin_url

        # 변수로 추출해야 함
        cmd = '/home/pi/opt/PiNVR/pinvr' + params
        cmd_args = cmd.split()

        self.runnable = subprocess.Popen(cmd_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        # self.runnable = subprocess.Popen(['ping', '127.0.0.1'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.pid = self.runnable.pid

        # call(cmd_args)

    def cmd_change_camera_name(self, camera_name):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.camera_name = camera_name
            self.runnable.stdin.write('-hello ' + camera_name)

    def cmd_change_root_dir(self, root_dir):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.root_dir = root_dir
            self.runnable.stdin.write('-hello ' + root_dir)

    def cmd_change_server_port(self, server_port):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.server_port = server_port
            self.runnable.stdin.write('-hello ' + str(server_port))

    def cmd_change_origin_url(self, origin_url):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.origin_url = origin_url
            self.runnable.stdin.write('-hello ' + origin_url)

    def cmd_kill_nvs(self):
        if self.runnable is None:
            print 'runnable is None. Maybe subprocess is dead.'
        else:
            self.runnable.kill()
            outs, errs = self.runnable.communicate()

            print 'nvs killed : ' + str(self.pid), outs, errs


# NVS 감시 스레드
class NVSWatchThread(Thread):
    def __init__(self):
        self.stopped = False

        Thread.__init__(self)

    def run(self):
        while self.stopped is False:
            sleep(3)

            update_process_status()

    def stop(self):
        self.stopped = True


app = Flask(__name__, static_url_path='/static')

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
    global nvs_list

    _camera_list = None

    if 'username' in session:
        _camera_list = []
        for _camera in nvs_list.values():
            if _camera.alive is 'ALIVE':
                _camera.enabled = True
            else:
                _camera.enabled = False

            _camera_list.append(_camera)

    return render_template('status.html', camera_list=_camera_list)


@app.route('/logout')
def logout():
    session.pop('username', None)

    return redirect('/')


@app.route('/kill-all')
def asdf():
    global nvs_thread_list

    for thread in nvs_thread_list:
        thread.cmd_kill_nvs()

    return redirect('/')


@app.route('/add', methods=['GET', 'POST'])
def add():
    global nvs_list, nvs_watcher

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
                if server_port in _camera_list:
                    server_port += 1
                elif server_port > 8100:
                    error = 'NVS is too many.'

                    break
                else:
                    break

            if error is None:
                run_camera(root_dir, camera_name, origin_url, server_port)

                _camera_info = NVSInfo(camera_name, root_dir, server_port, origin_url, owner, True)
                insert_db_camera(_camera_info)

                nvs_list = get_db_camera_list(owner)

                update_process_status()

                print 'nvs added: ' + camera_name, owner
    else:
        return redirect('/')

    return redirect(url_for('status', error=error))


@app.route('/modify', methods=['POST'])
def modify():
    global nvs_list, nvs_watcher
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

            update_db_camera(camera_name, root_dir, origin_url, server_port)

            nvs_list = get_db_camera_list(owner)

            # process 갱신
            for item in nvs_thread_list:
                if str(item.server_port) == server_port:

                    update_process_status()

                    item.cmd_change_camera_name(camera_name)
                    item.cmd_change_root_dir(root_dir)
                    item.cmd_change_origin_url(origin_url)

                    break
    else:
        return redirect('/')

    return redirect(url_for('status', error=error))


@app.route('/enable', methods=['POST'])
def enable():
    global nvs_list, nvs_watcher

    owner = get_current_username()

    error = None

    if owner is not None:
        server_port = request.form['server_port']

        _camera = get_db_camera(server_port)
        run_camera(_camera.camera_name, _camera.root_dir, _camera.origin_url, _camera.server_port)

        db_enable_camera(server_port, True)

        nvs_list = get_db_camera_list(owner)

        update_process_status()

        print 'nvs enabled: ' + _camera.camera_name, owner
    else:
        return redirect('/')

    return redirect(url_for('status', error=error))


@app.route('/disable', methods=['POST'])
def disable():
    global nvs_list, nvs_watcher

    owner = get_current_username()

    error = None

    if owner is not None:
        server_port = request.form['server_port']

        db_enable_camera(server_port, False)

        nvs_list = get_db_camera_list(owner)

        # process 갱신
        for item in nvs_thread_list:
            if str(item.server_port) == server_port:
                item.cmd_kill_nvs()

                update_process_status()

                break

        print 'nvs disabled: ' + item.camera_name, owner
    else:
        return redirect('/')

    return redirect(url_for('status', error=error))


@app.route('/delete', methods=['POST'])
def delete():
    global nvs_list, nvs_watcher

    owner = get_current_username()

    error = None

    if owner is not None:
        server_port = request.form['server_port']

        delete_db_camera(server_port)

        nvs_list = get_db_camera_list(owner)

        # process 갱신
        for item in nvs_thread_list:
            if str(item.server_port) == server_port:
                item.cmd_kill_nvs()

                update_process_status()

                break

        print 'nvs deleted: ' + item.camera_name, owner
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
                    enabled BOOL \
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

    nvs_list = get_db_camera_list(admin_data.username)

    for nvs in nvs_list.values():
        run_camera(nvs.root_dir, nvs.camera_name, nvs.origin_url, nvs.server_port)

    nvs_watcher = NVSWatchThread()
    nvs_watcher.start()

    # flask 실행
    app.run(host='0.0.0.0', port='1024')
