# Data presentation service (prometheus)

import time
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client import start_http_server
from helpers.redis_helper import RedisConnect
from helpers.logging_helper import setup_logging
from config import Config_Presentation, Config_Netprobe

# Logging config

logger = setup_logging("logs/presentation.log")


def average(values):
    return sum(values) / len(values) if values else None


def evaluate(value, threshold):
    # Missing measurement means the test failed, so score it as worst case
    if value is None:
        return 1
    return min(value / threshold, 1)


class CustomCollector(object):

    def collect(self):

        try:
            cache = RedisConnect()
            stats_netprobe = cache.redis_read('netprobe') # Get the latest results from Redis
            stats_speedtest = cache.redis_read('speedtest')
        except Exception as e:
            logger.error("Could not read from Redis")
            logger.error(e)
            return

        if not stats_netprobe or not stats_netprobe['stats']:
            return

        g = GaugeMetricFamily("Network_Stats", 'Network statistics for latency and loss from the probe to the destination', labels=['type','target'])

        for item in stats_netprobe['stats']: # Expose each individual latency / loss metric for each site tested
            for metric in ('latency','loss','jitter'):
                if item[metric] is not None:
                    g.add_metric([metric,item['site']],item[metric])

        # Calculate these in presentation rather than prom to reduce cardinality
        average_loss = average([item['loss'] for item in stats_netprobe['stats']])
        average_latency = average([item['latency'] for item in stats_netprobe['stats'] if item['latency'] is not None])
        average_jitter = average([item['jitter'] for item in stats_netprobe['stats'] if item['jitter'] is not None])

        for metric, value in (('latency',average_latency),('loss',average_loss),('jitter',average_jitter)):
            if value is not None:
                g.add_metric([metric,'all'],value)

        yield g

        h = GaugeMetricFamily("DNS_Stats", 'DNS performance statistics for various DNS servers', labels=['server'])

        my_dns_latency = None

        for item in stats_netprobe['dns_stats']:
            h.add_metric([item['nameserver']],item['latency'])

            if item['nameserver'] == Config_Netprobe.DNS_NAMESERVER_4:
                my_dns_latency = float(item['latency']) # Grab the current DNS latency of the probe's DNS resolver

        yield h

        # Lets the dashboard tell "disabled" apart from "no result yet"
        e = GaugeMetricFamily("Speedtest_Enabled", 'Whether the speedtest service is enabled in .env')
        e.add_metric([],int(Config_Netprobe.speedtest_enabled))

        yield e

        if stats_speedtest: # Speed test is optional

            s = GaugeMetricFamily("Speed_Stats", 'Speedtest performance statistics from speedtest.net', labels=['direction'])

            for key, value in stats_speedtest['speed_stats'].items():
                if value:
                    s.add_metric([key],value)

            yield s

        # Master scoring function

        score = 1 \
            - Config_Presentation.weight_loss * evaluate(average_loss, Config_Presentation.threshold_loss) \
            - Config_Presentation.weight_jitter * evaluate(average_jitter, Config_Presentation.threshold_jitter) \
            - Config_Presentation.weight_latency * evaluate(average_latency, Config_Presentation.threshold_latency) \
            - Config_Presentation.weight_dns_latency * evaluate(my_dns_latency, Config_Presentation.threshold_dns_latency)

        i = GaugeMetricFamily("Health_Stats", 'Overall internet health function')
        i.add_metric([],score)

        yield i


if __name__ == '__main__':

    start_http_server(Config_Presentation.presentation_port,addr=Config_Presentation.presentation_interface)

    REGISTRY.register(CustomCollector())
    while True:
        time.sleep(15)
