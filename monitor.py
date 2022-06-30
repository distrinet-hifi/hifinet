import json
import re
import numpy as np


class Monitor:
    def __init__(self, net):
        self.net = net
        self.infra = net.infra
        self.mapper = net.mapper
        self.databases = {}
    
    def monitor(self):
        for worker in self.infra.workers:
            worker.pull('/root/hifi/logs/%s.log' % worker.ip, '/root/results/')
            database = DataBase(worker)
            database.parse()
            self.databases[worker.ip] = database

        for link in self.net.links.values():
            if 'sample' not in link.params:
                continue
            elif not link.params['sample']:
                continue

            intf1, intf2 = link.intf1, link.intf2
            # db1, db2 = self.databases[intf1.parent.ip].ifindexes[intf1.ifindex], self.databases[intf2.parent.ip].ifindexes[intf2.ifindex]
            db1, db2 = {}, {}
            worker1, worker2 = intf1.parent, intf2.parent
            db1['packets_in'], db1['packets_out'] = self.databases[worker1.ip].ins[intf1.ifindex], self.databases[worker1.ip].outs[intf1.ifindex]
            db2['packets_in'], db2['packets_out'] = self.databases[worker2.ip].ins[intf2.ifindex], self.databases[worker2.ip].outs[intf2.ifindex]
            if len(db1['packets_in'])*len(db1['packets_out'])*len(db2['packets_in'])*len(db2['packets_out']) == 0:
                continue

            if 'delay' in link.params:
                d = int(link.params['delay'][:-2])
            else:
                d = 0
            if 'bw' in link.params:
                B = int(link.params['bw'][:-4]) * 1e6
            else:
                B = 100e6
            collector = Collector(db1, db2, B, d)
            collector.merge()
            collector.sort()
            collector.analyse()
            
            filename = '/root/results/%s--%s' % (intf1.name, intf2.name)
            collector.save(filename)



length = len

PATTERN_IN   = re.compile(r"^.*\s(?P<ts>[0-9]+\.[0-9]+):.*\s\[in\]\s(?P<dev>[0-9]+)\s(?P<xid>[0-9]+)\s*$")
PATTERN_OUT  = re.compile(r"^.*\s(?P<ts>[0-9]+\.[0-9]+):.*\s\[out\]\s(?P<dev>[0-9]+)\s(?P<xid>[0-9]+)\s(?P<len>[0-9]+)\s*$")
PATTERN_ENQ = re.compile(r"^.*\s\[enq\]\s(?P<dev>[0-9]+)\s(?P<xid>[0-9]+)\s(?P<blen>[0-9]+)\s*$")
PATTERN_DEQ  = re.compile(r"^.*\s(?P<ts>[0-9]+\.[0-9]+):.*\s\[deq\]\s(?P<dev>[0-9]+)\s(?P<len>[0-9]+)\s*$")

class DataBase:
    def __init__(self, worker):
        self.filename = "/root/results/%s.log" % worker.ip
        self.worker = worker

        self.ifindexes = {}
        for node in worker.nodes.values():
            for intf in node.intfs:
                name = intf.name
                ifindex = intf.ifindex
                self.ifindexes[ifindex] = name

        self.ins = {ifindex: {} for ifindex in self.ifindexes}
        self.outs = {ifindex: {} for ifindex in self.ifindexes}

        self.lastt = {ifindex: None for ifindex in self.ifindexes}
        self.lastl = {ifindex: None for ifindex in self.ifindexes}

    def parse_line(self, line):
        if '[in]' in line:
            m = PATTERN_IN.match(line)
            if m is not None:
                dev, xid, ts = int(m.group('dev')), int(m.group('xid')), int(1e6*float(m.group('ts')))
                if dev in self.ifindexes:
                    arr = self.ins[dev].get(xid)
                    if arr is not None:
                        arr.append((ts))
                    else:
                        self.ins[dev][xid] = [(ts)]
                return

        elif '[enq]' in line:
            m = PATTERN_ENQ.match(line)
            if m is not None:
                dev, xid, blen = int(m.group('dev')), int(m.group('xid')), int(m.group('blen'))
                if dev in self.ifindexes:
                    arr = self.outs[dev].get(xid)
                    if arr is not None:
                        arr.append(blen)
                    else:
                        self.outs[dev][xid] = [blen]
                return

        elif '[out]' in line:
            m = PATTERN_OUT.match(line)
            if m is not None:
                dev, xid, ts, len = int(m.group('dev')), int(m.group('xid')), int(1e6*float(m.group('ts'))), int(m.group('len'))
                if dev in self.ifindexes:
                    arr = self.outs[dev].get(xid)
                    if arr is not None:
                        blen = self.outs[dev][xid][-1]
                        tau = 0
                        plen = 0
                        if self.lastl[dev] is not None:
                            tau = ts - self.lastt[dev] # us
                            plen = self.lastl[dev]
                        self.outs[dev][xid][-1] = (ts, len, blen, plen, tau)
                return

        elif '[deq]' in line:
            m = PATTERN_DEQ.match(line)
            if m is not None:
                dev, ts, len = int(m.group('dev')), int(1e6*float(m.group('ts'))), int(m.group('len'))
                if dev in self.ifindexes:
                    self.lastt[dev] = ts
                    self.lastl[dev] = len
                return

    def parse(self):
        with open(self.filename, 'r') as f:
            lines = f.readlines()
            for line in lines:
                self.parse_line(line)




class Collector:
    def __init__(self, db1, db2, B=100e6, d=0):
        self.db1 = db1
        self.db2 = db2
        self.B = B
        self.d = d

        self.packets12 = []
        self.packets21 = []

        self.xids12 = list(set(self.db1['packets_out']) & set(self.db2['packets_in']))
        self.xids21 = list(set(self.db2['packets_out']) & set(self.db1['packets_in']))

    def merge(self):
        # 1 -> 2
        for xid in self.xids12:
            if length(self.db1['packets_out'][xid]) != length(self.db2['packets_in'][xid]):
                continue

            for i in range(min(length(self.db1['packets_out'][xid]), length(self.db2['packets_in'][xid]))):
                pin  = self.db2['packets_in'][xid][i]
                pout = self.db1['packets_out'][xid][i]
                (ts_in) = pin # us
                try:
                    (ts_out, len, blen, plen, tau) = pout
                except:
                    # print(pout)
                    continue

                packet = (xid, ts_out, ts_in, len, blen, plen, tau)
                self.packets12.append(packet)

        # 2 -> 1
        for xid in self.xids21:
            if length(self.db1['packets_in'][xid]) != length(self.db2['packets_out'][xid]):
                continue
                
            for i in range(min(length(self.db2['packets_out'][xid]), length(self.db1['packets_in'][xid]))):
                pin  = self.db1['packets_in'][xid][i]
                pout = self.db2['packets_out'][xid][i]
                (ts_in) = pin # us
                try:
                    (ts_out, len, blen, plen, tau) = pout
                except:
                    print(pout)
                    continue

                packet = (xid, ts_out, ts_in, len, blen, plen, tau)
                self.packets21.append(packet)

    def sort(self):
        self.packets12.sort(key = lambda p: p[1])
        self.packets21.sort(key = lambda p: p[2])

    def analyse(self):
        B = self.B 
        d = self.d

        self.rtds = [] # ms
        self.rtds_ = [] # ms
        self.tss1 = []
        self.tss2 = []

        self.plens = []
        self.blens = []
        self.lens = []
        self.taus = []

        i = 0
        packet21 = self.packets21[0]
        for packet12 in self.packets12:
            while packet21[2] < packet12[1] and i < length(self.packets21)-1:
                i += 1
                packet21 = self.packets21[i]
            if packet21[2] < packet12[1]:
                break

            (xid12, ts_out12, ts_in12, len12, blen12, plen12, tau12) = packet12
            (xid21, ts_out21, ts_in21, len21, blen21, plen21, tau21) = packet21

            mes = (ts_in12 - ts_out12 + ts_in21 - ts_out21) * 1e-3 # ms

            # if mes < -100:
            #       print(xid12, xid21, mes)

            # if mes < 0:
            #       continue

            self.rtds.append(mes)
            self.tss1.append(ts_out12)
            self.tss2.append(ts_out21)

            blen = (blen12 + blen21)*8 # bits

            if plen12*8/B*1e6 < tau12:
                plen12 = 0
                tau12 = 0
            
            if plen21*8/B*1e6 < tau21:
                plen21 = 0
                tau21 = 0
            
            plen = (plen12 + plen21)*8 # bits

            len = (len12 + len21)*8 # bits

            tau = tau12 + tau21 # µs

            est = len*1e3/B + blen*1e3/B + (plen*1e3/B - tau*1e-3) + 2 * d

            self.blens.append(blen)
            self.plens.append(plen)
            self.lens.append(len)
            self.taus.append(tau)

            self.rtds_.append(est)


        # self.clean()

        # N = length(self.lens)

        # X = np.array([ [self.lens[i], self.blens[i], self.plens[i], self.taus[i]] for i in range(N) ])
        # y = np.array(self.rtds)

        # result = LinearRegression().fit(X, y)
        # print(result.score(X, y))
        # print(result.coef_)
        # print(result.intercept_)

    def clean(self, inf=5, sup=95):
        inf = np.percentile(self.rtds, inf)
        sup = np.percentile(self.rtds, sup)
        indices = [i for i in range(length(self.rtds)) if self.rtds[i]>inf and self.rtds[i]<sup]

        self.rtds = [self.rtds[i] for i in indices]
        self.lens = [self.lens[i] for i in indices]
        self.blens = [self.blens[i] for i in indices]
        self.plens = [self.plens[i] for i in indices]
        self.taus = [self.taus[i] for i in indices]

    def save(self, filename):
        data = {}
        data['rtds'] = self.rtds
        data['rtds_'] = self.rtds_
        raw = json.dumps(data)
        with open(filename, 'w') as f:
            f.write(raw)
            f.close()
        return filename

