from bcc import BPF
from os import system
from sys import argv

KPROBE = """
#include <net/sch_generic.h>
#include <bcc/proto.h>
#include <uapi/linux/ptrace.h>
#include <uapi/linux/ip.h>
#include <uapi/linux/icmp.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/in.h>

BPF_HASH(last);

int kprobe__htb_enqueue(struct pt_regs *ctx, struct sk_buff *skb, struct Qdisc *sch, struct sk_buff **to_free)
{
    int mtu = skb->dev->mtu;
    if (mtu == 1500)
        return 0;

    u64 dev, *lastlen = 0;

    void *data = (void *)(long)skb->data;                                                                         
    struct iphdr *iph = (struct iphdr *)(skb->head + skb->network_header);

    unsigned short int hash = iph->check;
    if (hash == 0 || hash % 100 > 1)
        return 0;
    
    unsigned short int id = iph->id;
    unsigned short int fo = iph->frag_off;
    id = (id << 8) | (id >> 8);
    fo = (fo << 8) | (fo >> 8);
    unsigned int xid = (id << 16) | fo;


    unsigned int blen = sch->qstats.backlog;
    dev = skb->dev->ifindex;

    lastlen = last.lookup(&dev);
    if (lastlen == NULL) {
        bpf_trace_printk("[deq] %d 0\\n", dev);
    } else {
        bpf_trace_printk("[deq] %d %d\\n", dev, *lastlen);
    }

    bpf_trace_printk("[enq] %d %u %u\\n", dev, xid, blen);
                 
    return 0;
}
                                                                                                
int kretprobe__htb_dequeue(struct pt_regs *ctx, struct Qdisc *sch)  
{   
    struct sk_buff *skb = (struct sk_buff *)PT_REGS_RC(ctx);
   
    if (skb) {
        int mtu = skb->dev->mtu;
        if (mtu == 1500)
            return 0;

        u64 dev, len = 0;
        len = skb->len;
        dev = skb->dev->ifindex;
        last.update(&dev, &len);
        // bpf_trace_printk("[deq] %d %d\\n", dev, len);
    }
   
   return 0;
}
"""


if __name__ == '__main__':
    ip = argv[1]
    kprobe = BPF(text = KPROBE)
    system('cat /sys/kernel/debug/tracing/trace_pipe > /root/hifi/logs/%s.log' % ip)
    kprobe.cleanup()
