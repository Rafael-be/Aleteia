# src/controller/gemini_controller.py
from flask import request, jsonify
from services.gemini_services import obter_resposta

def responder_controller():
    dados = request.get_json(silent=True)

    if not dados:
        return jsonify({"erro": "JSON inválido"}), 400

    mensagem  = dados.get("mensagem", "").strip()
    sessao_id = dados.get("sessaoId", "default")

    if not mensagem:
        return jsonify({"erro": "Mensagem vazia"}), 400

    if len(mensagem) > 2000:
        return jsonify({"erro": "Mensagem muito longa (máx. 2000 caracteres)"}), 400

    try:
        resposta = obter_resposta(mensagem, sessao_id)
        return jsonify({"resposta": resposta}), 200
    except Exception as e:
        print(f"[Gemini] Erro: {e}")
        return jsonify({"erro": "Erro ao processar com a IA. Tente novamente."}), 500;