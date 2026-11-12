"""One lazy, pooled client per worker. Health checks are explicit."""
from threading import Lock
from pymongo import MongoClient

class MongoDatabaseProvider:
    def __init__(self, uri, database_name, timeout_ms=3000):
        self.uri, self.database_name = uri, database_name
        self.timeout_ms, self.client, self.last_error = timeout_ms, None, None
        self._lock = Lock()

    def get_database(self):
        with self._lock:
            if self.client is None:
                self.client = MongoClient(self.uri, serverSelectionTimeoutMS=self.timeout_ms,
                    connectTimeoutMS=self.timeout_ms, socketTimeoutMS=5000)
            return self.client[self.database_name]

    def healthcheck(self):
        self.get_database().command('ping')
