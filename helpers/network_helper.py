# Network tests
import re
import subprocess
from threading import Thread
import dns.resolver
import speedtest

LOSS_RE = re.compile(r'([\d.]+)% packet loss')
RTT_RE = re.compile(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/[\d.]+/([\d.]+) ms')


def run_parallel(threads):
    for t in threads:
        t.start()
    for t in threads:
        t.join()


class NetworkCollector(object): # Main network collection class

    def __init__(self,sites,count,dns_test_site,nameservers_external):
        self.sites = sites # List of sites to ping
        self.count = str(count) # Number of pings
        self.stats = [] # List of stat dicts
        self.dnsstats = [] # List of stat dicts
        self.dns_test_site = dns_test_site # Site used to test DNS response times
        self.nameservers = nameservers_external

    def pingtest(self,count,site):

        ping = subprocess.run(["ping", "-n", "-i", "0.1", "-W", "1", "-c", count, site], capture_output=True, text=True).stdout

        loss = LOSS_RE.search(ping)
        rtt = RTT_RE.search(ping)

        # No summary at all (e.g. name resolution failed) still counts as total loss
        netdata = {
            "site":site,
            "loss":float(loss.group(1)) if loss else 100.0,
            "latency":float(rtt.group(1)) if rtt else None,
            "jitter":float(rtt.group(2)) if rtt else None
        }

        if not rtt:
            print(f"Error pinging {site}")

        self.stats.append(netdata)

    def dnstest(self,site,nameserver):

        my_resolver = dns.resolver.Resolver()

        try:

            my_resolver.nameservers = [nameserver[1]]
            my_resolver.lifetime = 10

            answers = my_resolver.resolve(site,'A')

            dns_latency = round(answers.response.time * 1000,2)

        except Exception as e:
            print(f"Error performing DNS resolution on {nameserver}")
            print(e)
            dns_latency = 5000

        self.dnsstats.append({
            "nameserver":nameserver[0],
            "nameserver_ip":nameserver[1],
            "latency":dns_latency
        })

    def collect(self):

        # Empty previous results
        self.stats = []
        self.dnsstats = []

        # Pings first, DNS after, so ping traffic doesn't skew DNS timings
        run_parallel([Thread(target=self.pingtest, args=(self.count,item,)) for item in self.sites])
        run_parallel([Thread(target=self.dnstest, args=(self.dns_test_site,item,)) for item in self.nameservers])

        return {
            "stats":self.stats,
            "dns_stats":self.dnsstats
        }


class Netprobe_Speedtest(object): # Speed test class

    def collect(self):

        s = speedtest.Speedtest()
        s.get_best_server()

        return {
            "speed_stats":{
                "download": s.download(),
                "upload": s.upload()
            }
        }
