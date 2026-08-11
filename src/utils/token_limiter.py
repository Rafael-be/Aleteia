"""
Módulo de Controle de Limite Diário de Tokens.

Administradores (role == "admin") não têm limite. Usuários comuns têm um
teto diário de tokens, resetado automaticamente à meia-noite (na prática,
no primeiro uso do dia).
"""

from datetime import date


def usuario_pode_usar_ia(user_model, user_id: str, limite_diario: int) -> tuple[bool, int, int | None]:
    """
    Verifica se o usuário pode fazer uma nova chamada à IA.

    :param user_model: Instância de UserModel.
    :param user_id: ID do usuário autenticado.
    :param limite_diario: Teto de tokens por dia para usuários comuns.
    :return: Tupla (pode_usar, tokens_usados_hoje, limite).
             Para admins, limite retorna None (sem teto).
    """
    usuario = user_model.find_by_id(user_id)
    if not usuario:
        return False, 0, limite_diario

    if usuario.get("role") == "admin":
        return True, usuario.get("tokens_usados_hoje", 0), None

    hoje = str(date.today())
    if usuario.get("data_ultimo_reset") != hoje:
        user_model.update_user(user_id, {"tokens_usados_hoje": 0, "data_ultimo_reset": hoje})
        usuario["tokens_usados_hoje"] = 0

    tokens_usados = usuario.get("tokens_usados_hoje", 0)
    return tokens_usados < limite_diario, tokens_usados, limite_diario


def registrar_uso_de_tokens(user_model, user_id: str, tokens_gastos: int) -> None:
    """
    Soma os tokens gastos na última chamada ao contador diário do usuário.
    Não faz nada para administradores.

    :param user_model: Instância de UserModel.
    :param user_id: ID do usuário autenticado.
    :param tokens_gastos: Quantidade de tokens gastos na chamada à IA.
    """
    usuario = user_model.find_by_id(user_id)
    if not usuario or usuario.get("role") == "admin":
        return

    novo_total = usuario.get("tokens_usados_hoje", 0) + tokens_gastos
    user_model.update_user(user_id, {"tokens_usados_hoje": novo_total})