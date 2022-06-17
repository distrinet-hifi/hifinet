class Topo:
    def __init__(self, *args):
        self.hosts = []
        self.switches = []
        self.links = []
        self.build(*args)

    def build(self, *args):
        pass

    def add_host(self, name):
        self.hosts.append(name)
        return name

    def add_switch(self, name):
        self.switches.append(name)
        return name

    def add_link(self, node1, node2, **kwargs):
        self.links.append((node1, node2, kwargs))
        return (node1, node2)

class SimpleTopo(Topo):
    def build(self):
        h1 = self.add_host('h1')
        h2 = self.add_host('h2')
        s1 = self.add_switch('s1')
        self.add_link(s1, h1, delay='1ms', bw='100Mbit')
        self.add_link(s1, h2, delay='1ms', bw='100Mbit')

class LinearTopo(Topo):
    def build(self, n):
        ss = self.add_switch('s1')
        hh = self.add_switch('h1')
        self.add_link(ss, hh, delay='1ms', bw='100Mbit')
        for i in range(2, n+1):
            s = self.add_switch('s%i' % i)
            h = self.add_switch('h%i' % i)
            self.add_link(s, ss, delay='1ms', bw='100Mbit')
            self.add_link(s, h, delay='1ms', bw='100Mbit')
            ss = s

