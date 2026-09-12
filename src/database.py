"""Conexão sob demanda com o MongoDB.

O cliente não é validado durante a inicialização do Flask. Assim, uma
indisponibilidade temporária do Atlas não deixa a aplicação presa a ``None``
até o próximo deploy/restart.
"""

from pymongo import MongoClient


class MongoDatabaseProvider:
    """Entrega o banco quando ele estiver acessível e tenta novamente após falhas."""

    def __init__(self, uri: str, database_name: str, timeout_ms: int = 10_000):
        self.uri = uri
        self.database_name = database_name
        self.timeout_ms = timeout_ms
        self.client = None
        self.last_error = None

    def get_database(self):
        """Valida a conexão atual ou cria uma nova antes de devolver o banco."""
        try:
            if self.client is None:
                self.client = MongoClient(
                    self.uri,
                    serverSelectionTimeoutMS=self.timeout_ms,
                    connectTimeoutMS=self.timeout_ms,
                )
            self.client.admin.command("ping")
            self.last_error = None
            return self.client[self.database_name]
        except Exception as exc:
            self.last_error = str(exc) or "Banco de dados indisponível"
            if self.client is not None:
                self.client.close()
            # A próxima requisição deve criar um cliente novo, inclusive após
            # uma falha de seleção de servidor do Atlas.
            self.client = None
            return None
