from monitor import Monitor
from topo import Topo
from infra import Infrastructure
from net import Network
from mapper import Mapper
from argparse import ArgumentParser
from time import sleep
import random
import json

class ToyTopo(Topo):
    def build(self):
        h1 = self.add_host('h1')
        h2 = self.add_host('h2')
        s1 = self.add_switch('s1')
        s2 = self.add_switch('s2')
        self.add_link(h1, s1, delay='1ms', bw='100Mbit')
        self.add_link(s1, s2, delay='10ms', bw='1000Mbit', sample=True)
        self.add_link(h2, s2, delay='1ms', bw='100Mbit', sample=False)


if __name__ == '__main__':
    topo = ToyTopo()
    infra = Infrastructure()
    infra.add_worker('172.16.100.5', key='/root/.ssh/id_rsa')
    mapper = Mapper(infra, topo)
    net = Network(mapper)
    
    try:
        net.start()
        monitor = Monitor(net)

        n = 1
        print("Start")
        for i in range(n):
            t = 60 * (n-i)
            print("%i seconds remaining" % t)
            sleep(60)
    
        monitor.monitor()
    except Exception as e:
        print(e)

    net.stop()
    net.clean()
    infra.shutdown()
