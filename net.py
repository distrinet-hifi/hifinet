from node import Node, Host, Switch
from link import Link


IMAGE = 'ayyoub321456/host-img'
NETWORK = '10.0.0.0/8'

class Network:
    ip = [10, 0, 0, 1]
    
    @staticmethod
    def _gen_ip():
        new_ip = '.'.join([str(i) for i in Network.ip]) + '/8'
        if Network.ip[3] < 255:
            Network.ip[3] += 1
        elif Network.ip[2] < 255:
            Network.ip[3] = 1
            Network.ip[2] += 1
        elif Network.ip[1] < 255:
            Network.ip[3] = 1
            Network.ip[2] = 0
            Network.ip[1] += 1
        else:
            Network.ip[3] = 1
            Network.ip[2] = 0
            Network.ip[1] = 0 
            Network.ip[0] += 1
        return new_ip
        
    def __init__(self, mapper):
        self.mapper = mapper
        self.topo = mapper.topo
        self.infra = mapper.infra
        self.hosts = {}
        self.switches = {}
        self.nodes = {}
        self.links = {}
        
    
    def start(self):
        print("* Starting end-hosts", end='')
        
        for hostname in self.topo.hosts:
            parent = self.mapper.mapping[hostname]
            ip = Network._gen_ip()
            host = Host(hostname, IMAGE, ip, parent)
            self.hosts[hostname] = host
            self.nodes[hostname] = host
            parent.nodes[hostname] = host
            print('.', end='')
        print('')
         
        print("* Starting switches", end='')
        
        for switchname in self.topo.switches:
            parent = self.mapper.mapping[switchname]
            switch = Switch(switchname, parent)
            self.switches[switchname] = switch
            self.nodes[switchname] = switch
            parent.nodes[switchname] = switch
            print('.', end='')
        print('')
            
        print("* Setting up links", end='')
        
        for (node1_name, node2_name, params) in self.topo.links:
            node1, node2 = self.nodes[node1_name], self.nodes[node2_name]
            link = Link(node1, node2, params)
            linkname = "%s--%s" % (link.intf1.name, link.intf2.name)
            linkeman = "%s--%s" % (link.intf2.name, link.intf1.name)
            self.links[linkname] = link
            self.links[linkeman] = link
            print('.', end='')
        print('')

        for worker in self.infra.workers:
            worker.monitor()
    
    def stop(self):
        for node in self.nodes.values():
            node.delete()
    
    def clean(self):
        for host in self.hosts.values():
            cid = host.container.cid
            for intf in host.intfs:
                cmd = "ip netns exec %s ip link del %s" % (cid, intf.name)
                intf.parent.run(cmd)
        for switch in self.switches.values():
            for intf in switch.intfs:
                cmd = "ip link del %s" % (intf.name)
                intf.parent.run(cmd)
    
    def get(self, name):
        if '--' not in name:
            return self.nodes[name]
        else:
            return self.links[name]
