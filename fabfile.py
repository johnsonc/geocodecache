from fabric.api import *

env.hosts = ['carmela.triposobackend.net']

app_name = 'geocodecache'
app_user = 'geocodecache'
app_dir = '/var/apps/%s/' % app_name


def pack():
  local('tar czf /tmp/%s.tgz .' % app_name)


def update_code():
  pack()
  put('/tmp/%s.tgz' % app_name, '/tmp/')
  with cd(app_dir):
    sudo('tar xzf /tmp/%s.tgz' % app_name, user=app_user)
    sudo('HOME=. virtualenv/bin/pip install -r requirements.txt', user=app_user)
  run('rm /tmp/%s.tgz' % app_name)


def migrate():
  update_code()
  with cd(app_dir):
    with settings(warn_only=True):
      sudo('virtualenv/bin/python db/manage.py version_control --repository=db --url=postgresql://%s@localhost/%s' % (
      app_user, app_name), user=app_user)
    sudo('virtualenv/bin/python db/manage.py upgrade --repository=db --url=postgresql://%s@localhost/%s' % (
    app_user, app_name), user=app_user)


def start_unicorn():
  with cd(app_dir):
    sudo('virtualenv/bin/gunicorn --daemon --pid=gunicorn.pid --bind unix:gunicorn.socket geocodecache:app',
         user=app_user)


def hup_unicorn():
  with cd(app_dir):
    with settings(warn_only=True):
      sudo('kill -HUP `cat /var/apps/%s/gunicorn.pid`' % app_name, user=app_user)


def stop_unicorn():
  with cd(app_dir):
    with settings(warn_only=True):
      sudo('kill `cat /var/apps/%s/gunicorn.pid`' % app_name, user=app_user)


def deploy():
  update_code()
  start_unicorn()
  hup_unicorn()


def restart():
  stop_unicorn()
  start_unicorn()

