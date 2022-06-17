class Mapper:
    def __init__(self, infra, topo):
        self.infra = infra
        self.topo = topo
        self.mapping = {}
        self.place()

    def place(self):
        n = len(self.infra.workers)
        i = 0
        for host in self.topo.hosts:
            worker = self.infra.workers[i % n]
            self.mapping[host] = worker
            i += 1
        i = 0
        for switch in self.topo.switches:
            worker = self.infra.workers[i % n]
            self.mapping[switch] = worker
            i += 1
        return self.mapping
