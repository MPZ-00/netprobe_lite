# Redis helper
#
# Functions to help read and write from Redis


from config import Config_Redis
import redis
import json

class RedisConnect():

    def __init__(self):

        # No password: the redis container ignores redis.conf (no config arg), so it runs without auth
        self.r = redis.Redis(
            host=Config_Redis.redis_url,
            port=Config_Redis.redis_port
        )

    def redis_read(self,key): # Read data from Redis

        results = self.r.get(key) # Get the latest results from Redis for a given key

        return json.loads(results) if results else None

    def redis_write(self,key,data,ttl): # Write data to Redis

        return self.r.set(key,json.dumps(data),ttl) # Store data with a given TTL
