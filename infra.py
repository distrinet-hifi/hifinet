from paramiko.client import SSHClient
from paramiko import AutoAddPolicy
from scp import SCPClient

class Worker:
    def __init__(self, ip, key):
        self.ip = ip
        self.client = SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(AutoAddPolicy())
        self.client.connect(ip, username="root", key_filename=key)
        self.scp_client = SCPClient(self.client.get_transport())
        self.nodes = {}

    def run(self, command):
        if type(command) is list:
            command = ' '.join(command)
        (stdin, stdout_, stderr_) = self.client.exec_command(command)
        stdout = stdout_.read().decode("utf-8")
        stderr = stderr_.read().decode("utf-8")

        stdin.close()
        stdout_.close()
        stderr_.close()

        return (stdout, stderr)

    def bgrun(self, command, out='/dev/null', err='/dev/null'):
        if type(command) is list:
            command = ' '.join(command)
        command = "nohup %s & > %s 2>%s < /dev/null" % (command, out, err)
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout, stderr

    def monitor(self):
        stdout, stderr = self.bgrun("python3 /root/hifi/agent.py %s" % self.ip)
        return stdout, stderr

    def close(self):
        self.run('pkill python3; pkill cat')
        self.client.close()

    def push(self, filename, remote_path):
        # command = "scp -o StrictHostKeyChecking=no %s root@%s:%s" % (filename, self.ip, remote_path)
        # stdout, stderr = self.run(command)
        self.scp_client.put(filename, remote_path)
        # return stdout, stderr

    def pull(self, filename, local_path):
        # command = "scp -o StrictHostKeyChecking=no root@%s:%s %s" % (self.ip, filename, local_path)
        # stdout, stderr = self.run(command)
        # return stdout, stderr
        self.scp_client.get(filename, local_path)

    
class Infrastructure:
    def __init__(self):
        self.workerdict = {}
        self.workers = []

    def add_worker(self, ip, key):
        worker = Worker(ip, key)
        self.workerdict[ip] = worker
        self.workers.append(worker)
        return worker

    def shutdown(self):
        for worker in self.workers:
            worker.close()
