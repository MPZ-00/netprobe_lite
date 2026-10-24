# Netprobe Service

import time
from helpers.network_helper import NetworkCollector
from helpers.redis_helper import RedisConnect
from config import Config_Netprobe
from helpers.logging_helper import setup_logging

if __name__ == '__main__':

    # Global Variables

    probe_interval = Config_Netprobe.probe_interval
    probe_count = Config_Netprobe.probe_count
    sites = Config_Netprobe.sites
    dns_test_site = Config_Netprobe.dns_test_site
    nameservers_external = Config_Netprobe.nameservers

    collector = NetworkCollector(sites,probe_count,dns_test_site,nameservers_external)

    # Logging Config

    logger = setup_logging("logs/netprobe.log")

    # A probe run plus the sleep can exceed interval + a few seconds during an outage, so keep a wide margin
    cache_interval = probe_interval * 2

    while True:

        try:
            stats = collector.collect()

        except Exception as e:
            print("Error testing network")
            logger.error("Error testing network")
            logger.error(e)
            time.sleep(probe_interval)
            continue

        try:
            RedisConnect().redis_write('netprobe',stats,cache_interval)

        except Exception as e:

            logger.error("Could not connect to Redis")
            logger.error(e)

        time.sleep(probe_interval)
