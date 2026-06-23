"""
Módulo de Gerenciamento de Usuários.

Este módulo contém a classe UserModel, responsável por interagir com o MongoDB,
realizar validações de e-mail e senha, e aplicar criptografia (bcrypt) 
para o armazenamento seguro das credenciais.
"""

import bcrypt
from datetime import datetime
from email_validator import validate_email, EmailNotValidError

class UserModel:
    """
    Modelo de usuário para MongoDB.
    Responsável por validar, estruturar e criptografar dados do usuário.
    """

    COLLECTION_NAME = "users"

    def __init__(self, db):
        """
        Inicializa o modelo com a instância do banco de dados.

        :param db: Instância do banco de dados MongoDB (pymongo.database.Database)
        """
        self.collection = db[self.COLLECTION_NAME]
        # Garante índice único no campo email
        self.collection.create_index("email", unique=True)

    # ------------------------------------------------------------------
    # Validações
    # ------------------------------------------------------------------

    @staticmethod
    def validate_email_format(email: str) -> str:
        """
        Valida o formato do e-mail.

        :param email: String com o e-mail informado pelo usuário.
        :return: E-mail normalizado (lowercase, sem espaços).
        :raises ValueError: Se o e-mail for inválido.
        """
        try:
            valid = validate_email(email, check_deliverability=False)
            return valid.normalized  # retorna e-mail normalizado
        except EmailNotValidError as e:
            raise ValueError(f"E-mail inválido: {str(e)}")

    @staticmethod
    def validate_password(password: str, confirm_password: str) -> None:
        """
        Valida a senha e a confirmação de senha.

        Regras:
        - Mínimo de 8 caracteres
        - Ao menos uma letra maiúscula
        - Ao menos um número
        - password == confirm_password

        :param password: Senha informada.
        :param confirm_password: Confirmação da senha.
        :raises ValueError: Se alguma regra for violada.
        """
        if len(password) < 8:
            raise ValueError("A senha deve ter no mínimo 8 caracteres.")

        if not any(c.isupper() for c in password):
            raise ValueError("A senha deve conter ao menos uma letra maiúscula.")

        if not any(c.isdigit() for c in password):
            raise ValueError("A senha deve conter ao menos um número.")

        if password != confirm_password:
            raise ValueError("As senhas não coincidem.")

    # ------------------------------------------------------------------
    # Criptografia
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Gera o hash bcrypt da senha.

        :param password: Senha em texto puro.
        :return: Hash da senha como string UTF-8.
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def check_password(password: str, hashed_password: str) -> bool:
        """
        Verifica se a senha informada corresponde ao hash armazenado.

        :param password: Senha em texto puro.
        :param hashed_password: Hash armazenado no banco.
        :return: True se a senha for válida, False caso contrário.
        """
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )

    # ------------------------------------------------------------------
    # Estrutura do documento
    # ------------------------------------------------------------------

    @staticmethod
    def build_user_document(email: str, hashed_password: str) -> dict:
        """
        Monta o documento que será inserido no MongoDB.

        :param email: E-mail já validado e normalizado.
        :param hashed_password: Senha já criptografada.
        :return: Dicionário representando o documento do usuário.
        """
        return {
            "email": email,
            "password": hashed_password,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

    # ------------------------------------------------------------------
    # Operações no banco
    # ------------------------------------------------------------------

    def create_user(self, email: str, password: str, confirm_password: str) -> dict:
        """
        Valida os dados, criptografa a senha e insere o usuário no banco.

        :param email: E-mail informado pelo usuário.
        :param password: Senha informada.
        :param confirm_password: Confirmação de senha.
        :return: Dicionário com o id do usuário inserido.
        :raises ValueError: Se alguma validação falhar.
        :raises Exception: Se o e-mail já estiver cadastrado.
        """
        # 1. Validações
        normalized_email = self.validate_email_format(email)
        self.validate_password(password, confirm_password)

        # 2. Verifica duplicidade
        if self.collection.find_one({"email": normalized_email}):
            raise ValueError("Este e-mail já está cadastrado.")

        # 3. Criptografa a senha
        hashed_password = self.hash_password(password)

        # 4. Monta e insere o documento
        user_document = self.build_user_document(normalized_email, hashed_password)
        result = self.collection.insert_one(user_document)

        return {"id": str(result.inserted_id)}

    def find_by_email(self, email: str) -> dict | None:
        """
        Busca um usuário pelo e-mail.

        :param email: E-mail a ser pesquisado.
        :return: Documento do usuário ou None se não encontrado.
        """
        normalized_email = email.strip().lower()
        return self.collection.find_one({"email": normalized_email})