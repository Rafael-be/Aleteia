"""Offline tests for the Firebase/legacy-account boundary."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import bcrypt
from firebase_admin._auth_utils import UserNotFoundError
from flask import Flask, g

from src.controller.authController import AuthController
from src.models.userModel import IdentityConflictError, UserModel
from src.utils.migration_rate_limit import LegacyMigrationRateLimiter


class LegacyMigrationModelTests(unittest.TestCase):
    def legacy_document(self, password="senha-antiga", **extra):
        document = {
            "_id": "legacy-id",
            "email": "Pessoa@Exemplo.com",
            "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "is_active": True,
            "tokens_usados_hoje": 770,
            "data_ultimo_reset": "2026-08-11",
            "created_at": "original-date",
            "limite_diario_perguntas": 100,
        }
        document.update(extra)
        return document

    def model_without_database(self):
        model = UserModel.__new__(UserModel)
        return model

    def test_legacy_password_and_inactive_account_are_checked(self):
        model = self.model_without_database()
        document = self.legacy_document()
        model._encontrar_legado = MagicMock(return_value=document)
        self.assertEqual(model.validar_credenciais_legadas("pessoa@exemplo.com", "senha-antiga"), document)
        self.assertIsNone(model.validar_credenciais_legadas("pessoa@exemplo.com", "errada"))
        model._encontrar_legado.return_value = self.legacy_document(is_active=False)
        self.assertIsNone(model.validar_credenciais_legadas("pessoa@exemplo.com", "senha-antiga"))

    def test_link_preserves_legacy_document_and_normalizes_current_fields(self):
        model = self.model_without_database()
        collection = MagicMock()
        collection.find_one_and_update.return_value = {"firebase_uid": "new-firebase-uid"}
        model._obter_colecao = MagicMock(return_value=collection)
        document = self.legacy_document()
        result = model.vincular_usuario_legado(document, "new-firebase-uid", "pessoa@exemplo.com", "test")
        self.assertEqual(result["firebase_uid"], "new-firebase-uid")
        query, update = collection.find_one_and_update.call_args.args
        self.assertEqual(query["_id"], "legacy-id")
        self.assertEqual(query["password"], document["password"])
        fields = update["$set"]
        self.assertEqual(fields["limite_diario_perguntas"], 100)
        self.assertEqual(fields["uso_diario"]["tokens_usados"], 0)
        self.assertEqual(document["tokens_usados_hoje"], 770)
        self.assertEqual(fields["criado_em"], "original-date")
        self.assertNotIn("password", fields)

    def test_email_match_does_not_claim_legacy_profile(self):
        model = self.model_without_database()
        collection = MagicMock()
        collection.find_one.side_effect = [None, {"_id": "old-profile", "email": "same@example.com"}]
        model._obter_colecao = MagicMock(return_value=collection)
        with self.assertRaises(IdentityConflictError):
            model.sincronizar_usuario_firebase("new-firebase-uid", "same@example.com")
        collection.find_one_and_update.assert_not_called()

    def test_existing_uid_keeps_profile_and_updates_email_metadata(self):
        model = self.model_without_database()
        collection = MagicMock()
        collection.find_one.return_value = {"_id": "current", "firebase_uid": "uid"}
        collection.find_one_and_update.return_value = {"firebase_uid": "uid", "email": "new@example.com"}
        model._obter_colecao = MagicMock(return_value=collection)
        result = model.sincronizar_usuario_firebase("uid", " NEW@example.com ")
        self.assertEqual(result["email"], "new@example.com")
        self.assertFalse(collection.find_one_and_update.call_args.kwargs.get("upsert", False))

    def test_recovery_proof_accepts_one_orphaned_uid_match(self):
        model = self.model_without_database()
        document = self.legacy_document(firebase_uid="deleted-firebase-uid")
        collection = MagicMock()
        collection.find.return_value.limit.return_value = [document]
        model._obter_colecao = MagicMock(return_value=collection)
        self.assertEqual(model.validar_prova_recuperacao("pessoa@exemplo.com", "senha-antiga"), document)


class LegacyMigrationRateLimitTests(unittest.TestCase):
    def test_limiter_uses_email_digest_and_ip_bucket(self):
        limiter = LegacyMigrationRateLimiter(limit=2, window_seconds=60)
        self.assertTrue(limiter.allow("127.0.0.1", "one@example.com"))
        self.assertTrue(limiter.allow("127.0.0.1", "one@example.com"))
        self.assertFalse(limiter.allow("127.0.0.1", "one@example.com"))
        self.assertNotIn("one@example.com", repr(limiter._attempts))


class LegacyMigrationControllerTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.controller = AuthController.__new__(AuthController)
        self.controller.user_model = MagicMock()
        self.controller.user_model.normalizar_email.side_effect = lambda email: email.strip().lower() if isinstance(email, str) else None
        self.app.add_url_rule("/migrar", view_func=self.controller.migrar_usuario_legado, methods=["POST"])
        self.app.add_url_rule("/sincronizar", view_func=self.controller.sincronizar_usuario, methods=["POST"])

        @self.app.before_request
        def claims():
            g.firebase_claims = {}

    def test_creates_firebase_only_after_legacy_proof(self):
        legacy = {"_id": "legacy"}
        firebase_user = SimpleNamespace(uid="new-uid", email_verified=False)
        self.controller.user_model.validar_credenciais_legadas.return_value = legacy
        self.controller.user_model.vincular_usuario_legado.return_value = {"firebase_uid": "new-uid"}
        with unittest.mock.patch("src.controller.authController.legacy_migration_limiter.allow", return_value=True), \
             unittest.mock.patch("src.controller.authController.firebase_auth.get_user_by_email", side_effect=UserNotFoundError("missing")), \
             unittest.mock.patch("src.controller.authController.firebase_auth.create_user", return_value=firebase_user), \
             unittest.mock.patch("src.controller.authController.obter_uid_do_token_firebase", return_value=(None, None)):
            response = self.app.test_client().post("/migrar", json={"email": "old@example.com", "senha": "legacy-pass"})
        self.assertEqual(response.status_code, 200)
        self.controller.user_model.vincular_usuario_legado.assert_called_once_with(
            legacy, "new-uid", "old@example.com", "legacy_password_and_firebase_creation")

    def test_existing_firebase_identity_is_not_linked_without_second_proof(self):
        legacy = {"_id": "legacy"}
        self.controller.user_model.validar_credenciais_legadas.return_value = legacy
        firebase_user = SimpleNamespace(uid="existing-uid", email_verified=True)
        with unittest.mock.patch("src.controller.authController.legacy_migration_limiter.allow", return_value=True), \
             unittest.mock.patch("src.controller.authController.firebase_auth.get_user_by_email", return_value=firebase_user), \
             unittest.mock.patch("src.controller.authController.obter_uid_do_token_firebase", return_value=(None, None)):
            response = self.app.test_client().post("/migrar", json={"email": "old@example.com", "senha": "legacy-pass"})
        self.assertEqual(response.status_code, 401)
        self.controller.user_model.vincular_usuario_legado.assert_not_called()

    def test_sync_distinguishes_unverified_identity_conflict_and_database_failure(self):
        with unittest.mock.patch("src.controller.authController.obter_uid_do_token_firebase", return_value=("uid", False)):
            response = self.app.test_client().post("/sincronizar")
        self.assertEqual(response.status_code, 403)

        self.controller.user_model.sincronizar_usuario_firebase.side_effect = IdentityConflictError()
        with unittest.mock.patch("src.controller.authController.obter_uid_do_token_firebase", return_value=("uid", True)):
            response = self.app.test_client().post("/sincronizar")
        self.assertEqual(response.status_code, 409)

        self.controller.user_model.sincronizar_usuario_firebase.side_effect = RuntimeError("offline")
        with unittest.mock.patch("src.controller.authController.obter_uid_do_token_firebase", return_value=("uid", True)):
            response = self.app.test_client().post("/sincronizar")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
