import os

import redis


class RedisDatabase:

  def __init__(self):
    self.redis_client = redis.Redis(host=os.environ['REDIS_URL'], password=os.environ['REDIS_PASSWORD'], db=0)

  def hset(self, key: str, value: str):
    return self.redis_client.hset(key, value)
