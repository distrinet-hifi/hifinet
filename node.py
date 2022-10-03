DOCKER = "docker"

class Container:
    def __init__(self, name, image, parent):
        self.name = name
        self.parent = parent

        cmd = "%s run --name %s -d %s sleep infinity" % (DOCKER, name, image)
        (stdout, stderr) = self.parent.run(cmd)
        self.cid = stdout[:12]

        # cmd = "docker ps -aqf 'name=%s'" % self.name
        # (stdout, stderr) = self.parent.run(cmd)
        # self.cid = stdout[:-1]

        cmd = "%s inspect -f '{{.State.Pid}}' %s" % (DOCKER, self.cid)
        (stdout, stderr) = self.parent.run(cmd)
        self.pid = stdout[:-1]

        cmd = "mkdir -p /var/run/netns; touch /var/run/netns/%s; mount -o bind /proc/%s/ns/net /var/run/netns/%s" % (self.cid, self.pid, self.cid)
        self.parent.run(cmd)

    def cmd(self, command):
        if type(command) is list:
            command = ' '.join(command)
        cmd = """%s exec %s sh -c "%s" """ % (DOCKER, self.cid, command)
        (stdout, stderr) = self.parent.run(cmd)
        return (stdout, stderr)
    
    def push(self, path, remote_path):
        filename = path.split('/')[-1]
        inter_path = '/tmp/' + filename
        self.parent.push(path, inter_path)
        cmd = """%s cp %s %s:%s""" % (DOCKER, inter_path, self.cid, remote_path)
        (stdout, stderr) = self.parent.run(cmd)
        return (stdout, stderr)
    
    def pull(self, path, local_path):
        filename = path.split('/')[-1]
        inter_path = '/tmp/' + filename
        cmd = """%s cp %s:%s %s""" % (DOCKER, self.cid, path, inter_path)
        (stdout, stderr) = self.parent.run(cmd)
        self.parent.pull(inter_path, local_path)
        return (stdout, stderr)

    def kill(self):
        cmd = "%s rm -f %s" % (DOCKER, self.cid)
        self.parent.run(cmd)


class Node:
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent
        self.intfs = []

class Host(Node):
    def __init__(self, name, image, ip, parent):
        super().__init__(name, parent)
        self.container = Container(name, image, parent)
        self.ip = ip

    def cmd(self, command):
        return self.container.cmd(command)
    
    def push(self, path, remote_path):
        return self.container.push(path, remote_path)
    
    def pull(self, path, local_path):
        return self.container.pull(path, local_path)

    def attach(self, intf):
        self.intfs.append(intf)
        intf.node = self
        intf.parent = self.parent
        cmd = "ip link set %s netns %s; ip netns exec %s ifconfig %s %s up;" % (intf.name, self.container.cid, self.container.cid, intf.name, self.ip)
        self.parent.run(cmd)
    
    def delete(self):
        self.container.kill()

class Switch(Node):
    def __init__(self, name, parent):
        super().__init__(name, parent)
        cmd = "ovs-vsctl add-br %s; ip link set %s up" % (self.name, self.name)
        self.parent.run(cmd)
    
    def attach(self, intf):
        self.intfs.append(intf)
        intf.node = self
        intf.parent = self.parent
        cmd = "ovs-vsctl add-port %s %s" % (self.name, intf.name)
        self.parent.run(cmd)
    
    def delete(self):
        cmd = "ovs-vsctl del-br %s" % self.name
        self.parent.run(cmd)
