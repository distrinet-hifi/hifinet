from monitor import Monitor
from topo import Topo
from infra import Infrastructure
from net import Network
from mapper import Mapper
from argparse import ArgumentParser
from time import sleep
import random
import json

FILESIZE = 100
TAU = 50

class RenaterTopo(Topo):
    def build(self, n, m):
        self.n = n
        self.m = m
        self.blocks = {}
        self.sites = ['lille', 'paris', 'nancy', 'rennes', 'nantes', 'lyon', 'grenoble', 'toulouse', 'marseille', 'nice']
        self.hostmap = {site: [[] for _ in range(n)] for site in self.sites}
        self.linkmap = {'edge': {site: [] for site in self.sites}, 'access': {site: [] for site in self.sites}, 'core': []}
        
        cores = []
        j = 1
        k = 1

        for site in self.sites:
            s = self.add_switch('s%i' % j)
            j += 1
            cores.append(s)
            self.blocks[site] = [s]

            for ii in range(n):
                ss = self.add_switch('s%i' % j)
                j += 1
                self.blocks[site].append(ss)
                link = self.add_link(s, ss, delay='1ms', bw='1000Mbit')
                self.linkmap['access'][site].append(link)

                for iii in range(m):
                    h = self.add_host('h%i' % k)
                    k += 1
                    self.blocks[site].append(h)
                    self.hostmap[site][ii].append(h)
                    link = self.add_link(ss, h, delay='1ms', bw='100Mbit')
                    self.linkmap['edge'][site].append(link)

        link = self.add_link(cores[0], cores[1], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)
        link = self.add_link(cores[1], cores[2], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)
        link = self.add_link(cores[1], cores[3], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)
        link = self.add_link(cores[1], cores[5], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)
        link = self.add_link(cores[3], cores[4], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)
        link = self.add_link(cores[5], cores[6], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)
        link = self.add_link(cores[5], cores[8], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)
        link = self.add_link(cores[7], cores[8], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)
        link = self.add_link(cores[8], cores[9], delay='10ms', bw='10000Mbit')
        self.linkmap['core'].append(link)


class RenaterMapper(Mapper):
    def place(self):
        for i in range(10):
            for node in self.topo.blocks[self.topo.sites[i]]:
                self.mapping[node] = self.infra.workers[i]


class RenaterNetwork(Network):
    def _get_link(self, node1, node2):
        for linkname in self.links:
            if node1 in linkname and node2 in linkname:
                # return self.links[linkname]
                return linkname
        return None

    def snapshot(self):
        infos = {}
        infos['hosts'] = self.topo.hostmap
        infos['links'] = self.topo.linkmap
        for site in infos['links']['access']:
            for i in range(len(infos['links']['access'][site])):
                (node1, node2) = infos['links']['access'][site][i]
                linkname = self._get_link(node1, node2)
                infos['links']['access'][site][i] = linkname
        for site in infos['links']['edge']:
            for i in range(len(infos['links']['edge'][site])):
                (node1, node2) = infos['links']['edge'][site][i]
                linkname = self._get_link(node1, node2)
                infos['links']['edge'][site][i] = linkname
        for i in range(len(infos['links']['core'])):
            (node1, node2) = infos['links']['core'][i]
            linkname = self._get_link(node1, node2)
            infos['links']['core'][i] = linkname
        return infos

        


def gen_date():
    x = TAU + 11
    while x - 10 > TAU:
        x = 10 + random.expovariate(1/TAU)
    return x

def bittorrent(net, n, m, master):
    N = 10*n*m

    print("*** Starting tracker")
    server = net.get('h1')
    server.cmd("bttrack --dfile download_file > server.log 2>&1 &")

    x = random.randint(2, N)
    print("*** Creating file (seeder is h%i)" % x)
    seeder = net.get('h%i' % x)
    seeder.cmd("head -c %iM /dev/urandom > file" % FILESIZE)
    seeder.cmd("""ctorrent -t -u "http://10.0.0.1:80/announce" -s file.torrent file""")
    seeder.cmd("scp -o StrictHostKeyChecking=no file.torrent root@%s:" % master)

    print("*** Distributing torrent file", end='')
    for i in range(1, N+1):
        peer = net.get('h%i' % i)
        peer.cmd("scp -o StrictHostKeyChecking=no root@%s:file.torrent /root/" % master)
        print('.', end='')
    print('')

    print("*** Creating timeline", end='')
    timeline = [(0, x)]
    for i in range(2, N+1):
        if i == x:
            continue
        t = gen_date()
        timeline.append((t, i))
        print('.', end='')
    print('')

    print("*** Downloading")
    timeline.sort(key=lambda y: y[0])
    t_ = 0
    for (t, i) in timeline:
        dt = t - t_
        sleep(dt)
        peer = net.get('h%i' % i)
        logfile = "peer_%i.log" % i
        peer.cmd("nohup ctorrent /root/file.torrent -v > %s 2>&1 < /dev/null &" % logfile)
        print("%.2f h%i" % (t, i))
        t_ = t
    sleep(2*TAU)

    print("*** Retrieving logs", end='')
    for i in range(2, N+1):
        peer = net.get('h%i' % i)
        peer.cmd("scp -o StrictHostKeyChecking=no *.log root@%s:/root/results/" % master)
        print('.', end='')
    print('')

    print("*** Saving metadata")
    metadata = net.snapshot()
    raw = json.dumps(metadata)
    with open('/root/results/metadata', 'w') as f:
        f.write(raw)



if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--master', type=str)
    parser.add_argument('--workers', type=str)
    parser.add_argument('--switches', '-n', type=int, default=2)
    parser.add_argument('--peers', '-m', type=int, default=2)
    
    args = parser.parse_args()
    master = args.master
    workers = args.workers.split(',')
    n = args.switches
    m = args.peers

    topo = RenaterTopo(n, m)
    infra = Infrastructure()
    for ip in workers:
        infra.add_worker(ip, key='/root/.ssh/id_rsa')
    mapper = RenaterMapper(infra, topo)
    net = RenaterNetwork(mapper)

    net.start()
    monitor = Monitor(net)

    try:
        bittorrent(net, n, m, master)
        monitor.monitor()
    except Exception as e:
        print(e)

    net.stop()
    net.clean()
    infra.shutdown()


