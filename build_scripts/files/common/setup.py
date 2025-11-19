#!/usr/bin/python3

import os
import subprocess


def run_cmd(cmd):
    proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)


def create_host_ssh_keys():
    if not os.path.exists('/etc/ssh/ssh_host_ecdsa_key'):
        run_cmd('dpkg-reconfigure openssh-server')


def create_nginx_certs():
    if (not os.path.exists('/opt/aws/deepracer/password.txt') or
        not os.path.exists('/etc/ssl/certs/nginx-selfsigned.crt') or
            not os.path.exists('/etc/ssl/private/nginx-selfsigned.key')):
        run_cmd('/opt/aws/deepracer/nginx/nginx_install_certs.sh')


if __name__ == '__main__':
    create_host_ssh_keys()
    create_nginx_certs()
