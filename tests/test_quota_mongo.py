"""Optional real MongoDB 4.2+ concurrency tests in a disposable isolated DB.

Set AUDIT_TEST_MONGO_URI to a TEST server, never the application database.
"""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from pymongo import MongoClient
from src.models.userModel import UserModel


@unittest.skipUnless(os.getenv('AUDIT_TEST_MONGO_URI'), 'Requires isolated test MongoDB')
class MongoQuotaTests(unittest.TestCase):
    def setUp(self):
        self.client = MongoClient(os.environ['AUDIT_TEST_MONGO_URI'], serverSelectionTimeoutMS=3000)
        self.name = 'aleteia_audit_test_' + uuid4().hex
        self.db = self.client[self.name]
        self.db.users.create_index('firebase_uid', unique=True)
        # Provider avoids PyMongo dynamic attribute lookup for get_database.
        class Provider:
            def get_database(inner):
                return self.db
        self.model = UserModel(Provider())
        self.model.sincronizar_usuario_firebase('u', 'test@example.org')

    def tearDown(self):
        if self.name.startswith('aleteia_audit_test_'):
            self.client.drop_database(self.name)
        self.client.close()

    def test_concurrent_rollover_only_one_reservation_and_refund_once(self):
        self.db.users.update_one({'firebase_uid':'u'}, {'$set': {'uso_diario.data':'2000-01-01', 'uso_diario.perguntas_feitas':10}})
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: self.model.verificar_e_incrementar_uso('u'), range(8)))
        winners = [user for ok, user in results if ok]
        self.assertEqual(len(winners), 1)
        self.model.finalizar_reserva('u', winners[0], False)
        self.model.finalizar_reserva('u', winners[0], False)
        self.assertEqual(self.db.users.find_one({'firebase_uid':'u'})['uso_diario']['perguntas_feitas'], 0)

    def test_short_rate_survives_refunds_and_success_consumes(self):
        for index in range(3):
            ok, reservation = self.model.verificar_e_incrementar_uso('u')
            self.assertTrue(ok)
            self.model.finalizar_reserva('u', reservation, index == 0)
        ok, user = self.model.verificar_e_incrementar_uso('u')
        self.assertFalse(ok)
        self.assertEqual(user['quota_reason'], 'rate_limited')
        self.assertEqual(user['uso_diario']['perguntas_feitas'], 1)
