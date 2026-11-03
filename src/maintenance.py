"""Explicit, offline index management: python -m src.maintenance [--apply]."""
import argparse
import json
import os
from src import config
from src.database import MongoDatabaseProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Create indexes after reviewing existing data and query plans')
    parser.add_argument('--explain-uid', help='Read-only executionStats for a test UID')
    args = parser.parse_args()
    provider = MongoDatabaseProvider(os.environ['MONGO_URI'], os.getenv('MONGO_DB_NAME', 'aleteia'))
    db = provider.get_database()
    if args.apply:
        db.users.create_index('firebase_uid', unique=True, sparse=True)
        # Email is profile metadata, not the Firebase identity. Keep existing
        # email indexes untouched; do not silently change uniqueness policies.
        db.chats.create_index([('firebase_uid', 1), ('conversa_id', 1), ('created_at', 1), ('_id', 1)])
        db.chats.create_index([('firebase_uid', 1), ('created_at', 1)])
    result = {name: db[name].index_information() for name in ('users', 'chats')}
    if args.explain_uid:
        result['explain'] = db.command('explain', {'find': 'chats',
            'filter': {'firebase_uid': args.explain_uid, 'conversa_id': 'audit-test'},
            'sort': {'created_at': 1, '_id': 1}, 'limit': 100}, verbosity='executionStats')
    print(json.dumps(result, default=str))


if __name__ == '__main__':
    main()
