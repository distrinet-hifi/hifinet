from node import Host, Switch

class Link:
    vid = 1

    def __init__(self, node1, node2, params):
        self.node1 = node1
        self.node2 = node2
        self.intf1 = None
        self.intf2 = None
        self.params = params

        intf1_name = "%s-eth%s" % (node1.name, len(node1.intfs)+1)
        intf2_name = "%s-eth%s" % (node2.name, len(node2.intfs)+1)
        intf1 = Interface(intf1_name, params)
        intf2 = Interface(intf2_name, params)
        self.intf1 = intf1
        self.intf2 = intf2

        if node1.parent.ip == node2.parent.ip:
            worker = node1.parent
            cmd = "ip link add %s type veth peer name %s; ip link set %s up; ip link set %s up" % (intf1_name, intf2_name, intf1_name, intf2_name)
            worker.run(cmd)

        else:
            worker1, worker2 = node1.parent, node2.parent
            vid = Link.vid
            cmd1 = "ip link add %s type vxlan id %i remote %s local %s dstport 4789; ip link set %s up" % (intf1_name, vid, worker2.ip, worker1.ip, intf1_name)
            cmd2 = "ip link add %s type vxlan id %i remote %s local %s dstport 4789; ip link set %s up" % (intf2_name, vid, worker1.ip, worker2.ip, intf2_name)
            worker1.run(cmd1)
            worker2.run(cmd2)
            Link.vid += 1

        node1.attach(intf1)
        node2.attach(intf2)
        intf1.plug()
        intf2.plug()
    
    def delete(self):
        self.intf1.delete()
        self.intf2.delete()

class Interface:
    def __init__(self, name, params):
        self.name = name
        self.params = params
        self.node = None
        self.parent = None
        self.ifindex = None
    
    def plug(self):
        if 'delay' in self.params:
            d = self.params['delay']
        else:
            d = '0ms'

        if 'bw' in self.params:
            bw = self.params['bw']
        else:
            bw = '100Mbit'

        if isinstance(self.node, Host):
            suffix = "ip netns exec %s" % self.node.container.cid
        elif isinstance(self.node, Switch):
            suffix = ""

        cmd = ""
        cmd += " %s tc qdisc add dev %s root handle 1: htb;" % (suffix, self.name)
        cmd += " %s tc class add dev %s parent 1: classid 1:10 htb rate %s;" % (suffix, self.name, bw)
        cmd += " %s tc filter add dev %s parent 1: bpf da obj /root/hifi/logger sec egress flowid 1:10;" % (suffix, self.name)
        cmd += " %s tc qdisc add dev %s parent 1:10 handle 2: netem delay %s rate %s;" % (suffix, self.name, d, bw)
        cmd += " %s tc qdisc add dev %s ingress handle ffff: ;" % (suffix, self.name)
        cmd += " %s tc filter add dev %s parent ffff: bpf da obj /root/hifi/logger sec ingress;" % (suffix, self.name)

        self.parent.run(cmd)

        cmd = """%s python3 -c "import socket; print(socket.if_nametoindex('%s'))" """ % (suffix, self.name)
        stdout, stderr = self.parent.run(cmd)
        # self.ifindex = int(stdout[:-1])
        try:
            self.ifindex = int(stdout[:-1])
        except Exception as e:
            print(cmd, stdout, stderr)
            raise e

    def delete(self):
        if isinstance(self.node, Host):
            cmd = "ip netns exec %s ip link del %s" % (self.node.container.cid, self.name)
            self.parent.run(cmd)
        elif isinstance(self.node, Switch):
            cmd = "ovs-vsctl del-port %s; ip link del %s" % (self.name, self.name)
            self.parent.run(cmd)
        
