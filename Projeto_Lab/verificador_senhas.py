"""Verificador local: não armazena nem registra senhas."""

import argparse
import math
import re
import time
import unicodedata
import warnings
from collections import OrderedDict, deque
from dataclasses import dataclass
from getpass import GetPassWarning, getpass
from threading import Lock

LIMITE_ENTRADA = 4096
COMPRIMENTO_MINIMO = 8
COMPRIMENTO_FORTE = 12
COMPRIMENTO_MUITO_FORTE = 16
COMPRIMENTO_LONGO_FORTE = 20
COMPRIMENTO_LONGO_MUITO_FORTE = 28
DIVERSIDADE_MINIMA = 8
TAMANHO_SEQUENCIA = 4
NIVEL_FRACO = 1
NIVEL_FORTE = 3
NIVEL_MUITO_FORTE = 4
CLASSIFICACOES = ("Muito fraca", "Fraca", "Média", "Forte", "Muito forte")
SEQUENCIAS_PREVISIVEIS = (
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
)
REPETICAO_CONSECUTIVA = re.compile(r"(.)\1{3,}")
SUBSTITUICOES_COMUNS = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t",
    "@": "a", "$": "s", "!": "i",
})
# Lista ilustrativa local de escolhas conhecidas; não é uma base de vazamentos.
SENHAS_COMUNS = frozenset({
    "password", "senha", "admin", "administrator", "administrador", "letmein",
    "welcome", "bemvindo", "iloveyou", "euteamo", "changeme", "monkey",
    "dragon", "football", "master", "login", "secret", "princess", "qwerty",
    "abc", "test", "teste", "default", "root", "guest", "acesso", "internet",
    "superman", "batman", "trustnoone", "correcthorsebatterystaple",
    "queaforcaestejacomvoce", "maytheforcebewithyou", "euteamoparasempre",
})
SENHAS_NUMERICAS_COMUNS = frozenset({
    "123456", "1234567", "12345678", "123456789", "1234567890",
    "000000", "00000000", "111111", "11111111", "123123", "121212",
})


def _senha_comum(texto: str) -> bool:
    """Reconhece a lista local e variações triviais de caixa, acentos e sufixos."""
    if texto in SENHAS_NUMERICAS_COMUNS:
        return True
    chave = unicodedata.normalize("NFKD", texto.casefold())
    chave = "".join(c for c in chave if not unicodedata.combining(c))
    chave = re.sub(r"^[\W_\d]+|[\W_\d]+$", "", chave)
    return chave.translate(SUBSTITUICOES_COMUNS) in SENHAS_COMUNS


class _LimitadorRequisicoes:
    """Janela móvel por IP, em memória e sem conteúdo das requisições."""

    def __init__(self, maximo, janela, max_clientes, relogio):
        if maximo < 1 or janela <= 0 or max_clientes < 1:
            raise ValueError("Os limites de requisição devem ser positivos.")
        self.maximo = maximo
        self.janela = janela
        self.max_clientes = max_clientes
        self.relogio = relogio
        self.clientes = OrderedDict()
        self.lock = Lock()

    def verificar(self, cliente):
        with self.lock:
            agora = self.relogio()
            if cliente not in self.clientes:
                if len(self.clientes) >= self.max_clientes:
                    self.clientes.popitem(last=False)
                self.clientes[cliente] = deque()
            historico = self.clientes[cliente]
            self.clientes.move_to_end(cliente)
            while historico and historico[0] <= agora - self.janela:
                historico.popleft()
            if len(historico) >= self.maximo:
                return max(1, math.ceil(historico[0] + self.janela - agora))
            historico.append(agora)
            return 0


def _padrao_previsivel(texto: str) -> bool:
    """Detecta blocos repetidos ou padrões que dominam o texto avaliado."""
    texto = texto.casefold()
    if not texto:
        return False
    periodo = (texto + texto).find(texto, 1)
    if periodo < len(texto):
        return True

    posicoes_previsiveis = set()
    for repeticao in REPETICAO_CONSECUTIVA.finditer(texto):
        posicoes_previsiveis.update(range(*repeticao.span()))
    for sequencia in SEQUENCIAS_PREVISIVEIS:
        for i in range(len(sequencia) - TAMANHO_SEQUENCIA + 1):
            trecho = sequencia[i:i + TAMANHO_SEQUENCIA]
            for padrao in (trecho, trecho[::-1]):
                inicio = texto.find(padrao)
                while inicio != -1:
                    posicoes_previsiveis.update(
                        range(inicio, inicio + TAMANHO_SEQUENCIA)
                    )
                    inicio = texto.find(padrao, inicio + 1)
    return len(posicoes_previsiveis) * 2 >= len(texto)


@dataclass(frozen=True)
class Resultado:
    classificacao: str
    recomendacoes: tuple[str, ...]


def _texto_avaliavel(senha: str) -> str:
    """Normaliza Unicode e remove caracteres que não somam à pontuação."""
    normalizada = unicodedata.normalize("NFC", senha)
    return "".join(
        c for c in normalizada
        if c.isprintable() and not c.isspace()
        and unicodedata.category(c)[0] != "M"
    )


def _nivel_estrutural(texto: str, variedade: int) -> int:
    """Combina comprimento, variedade e bônus, antes das penalizações."""
    tamanho = len(texto)
    if tamanho < COMPRIMENTO_MINIMO:
        nivel = 0
    elif tamanho < COMPRIMENTO_FORTE:
        nivel = min(NIVEL_FRACO, variedade)
    elif tamanho < COMPRIMENTO_MUITO_FORTE:
        nivel = min(NIVEL_FORTE, variedade)
    else:
        nivel = variedade

    if len(set(texto.casefold())) >= DIVERSIDADE_MINIMA:
        if tamanho >= COMPRIMENTO_LONGO_MUITO_FORTE:
            nivel = max(nivel, NIVEL_MUITO_FORTE)
        elif tamanho >= COMPRIMENTO_LONGO_FORTE:
            nivel = max(nivel, NIVEL_FORTE)
    return nivel


def _criterios_caracteres(
    texto: str,
) -> tuple[tuple[str, str, bool, str], ...]:
    """Mantém os mesmos critérios no terminal e na interface web."""
    return (
        (
            "minusculas", "Letras minúsculas",
            any(c.islower() for c in texto), "Inclua letras minúsculas.",
        ),
        (
            "maiusculas", "Letras maiúsculas",
            any(c.isupper() for c in texto), "Inclua letras maiúsculas.",
        ),
        (
            "numeros", "Números",
            any(c.isdecimal() for c in texto), "Inclua números.",
        ),
        (
            "especiais", "Caracteres especiais",
            any(unicodedata.category(c)[0] in "PS" for c in texto),
            "Inclua caracteres especiais, como !, @ ou #.",
        ),
    )


def analisar_senha(senha: str) -> Resultado:
    """Avalia critérios estruturais sem incluir a senha no resultado."""
    if not isinstance(senha, str):
        raise TypeError("A senha deve ser um texto.")
    if len(senha) > LIMITE_ENTRADA:
        raise ValueError(
            f"A senha deve ter no máximo {LIMITE_ENTRADA} caracteres."
        )
    texto = _texto_avaliavel(senha)
    tamanho = len(texto)
    criterios = _criterios_caracteres(texto)
    recomendacoes = [
        mensagem for _, _, presente, mensagem in criterios if not presente
    ]
    if tamanho < COMPRIMENTO_MUITO_FORTE:
        recomendacoes.insert(
            0,
            f"Use pelo menos {COMPRIMENTO_MUITO_FORTE} caracteres visíveis, "
            "sem contar espaços; prefira uma frase longa.",
        )

    variedade = sum(presente for _, _, presente, _ in criterios)
    nivel = _nivel_estrutural(texto, variedade)

    if _padrao_previsivel(texto):
        nivel = min(nivel, NIVEL_FRACO)
        recomendacoes.append(
            "Evite blocos repetidos e senhas dominadas por sequências "
            "ou caracteres repetidos."
        )
    if _senha_comum(texto):
        nivel = 0
        recomendacoes.insert(
            0, "Evite senhas e frases conhecidas ou variações triviais delas."
        )
    if any(not c.isprintable() for c in senha):
        recomendacoes.append("Evite caracteres de controle ou invisíveis.")
    recomendacoes.append(
        "Use uma senha exclusiva para cada conta e um gerenciador de senhas."
    )
    recomendacoes.append(
        "Evite dados pessoais e sequências previsíveis; "
        "ative a autenticação em dois fatores."
    )
    return Resultado(CLASSIFICACOES[nivel], tuple(recomendacoes))


def criar_app(config: dict | None = None):
    """Cria a aplicação Flask; o terminal não depende da instalação do Flask."""
    from flask import Flask, jsonify, render_template, request
    from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=64 * 1024,
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
        RATE_LIMIT_MAX_REQUESTS=90,
        RATE_LIMIT_WINDOW=60,
        RATE_LIMIT_MAX_CLIENTS=1024,
        RATE_LIMIT_CLOCK=time.monotonic,
    )
    if config:
        app.config.update(config)
    limitador = _LimitadorRequisicoes(
        app.config["RATE_LIMIT_MAX_REQUESTS"],
        app.config["RATE_LIMIT_WINDOW"],
        app.config["RATE_LIMIT_MAX_CLIENTS"],
        app.config["RATE_LIMIT_CLOCK"],
    )

    @app.after_request
    def proteger_resposta(resposta):
        resposta.headers["Cache-Control"] = "no-store"
        resposta.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; connect-src 'self'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'none'"
        )
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["X-Frame-Options"] = "DENY"
        resposta.headers["Referrer-Policy"] = "no-referrer"
        return resposta

    @app.get("/")
    def inicio():
        return render_template("index.html", limite=LIMITE_ENTRADA)

    @app.post("/api/analisar")
    def analisar_web():
        origem = request.headers.get("Origin")
        if origem and origem != request.host_url.rstrip("/"):
            return jsonify(erro="Origem da requisição não permitida."), 403
        espera = limitador.verificar(request.remote_addr or "local")
        if espera:
            resposta = jsonify(erro="Muitas análises. Aguarde antes de tentar.")
            resposta.headers["Retry-After"] = str(espera)
            return resposta, 429
        if request.query_string:
            return jsonify(erro="Envie a senha somente no corpo JSON."), 400
        if not request.is_json:
            return jsonify(erro="Envie um objeto JSON com o campo senha."), 415
        try:
            dados = request.get_json()
        except BadRequest:
            return jsonify(erro="JSON inválido."), 400
        if not isinstance(dados, dict) or set(dados) != {"senha"}:
            return jsonify(erro="Envie apenas o campo senha no objeto JSON."), 400
        senha = dados["senha"]
        if not isinstance(senha, str):
            return jsonify(erro="O campo senha deve ser um texto."), 400
        try:
            resultado = analisar_senha(senha)
        except ValueError as erro:
            return jsonify(erro=str(erro)), 400
        texto = _texto_avaliavel(senha)
        criterios = [{
            "id": "comprimento",
            "rotulo": f"{COMPRIMENTO_MUITO_FORTE} caracteres avaliados",
            "atendido": len(texto) >= COMPRIMENTO_MUITO_FORTE,
        }]
        criterios.extend(
            {"id": chave, "rotulo": rotulo, "atendido": presente}
            for chave, rotulo, presente, _ in _criterios_caracteres(texto)
        )
        return jsonify(
            classificacao=resultado.classificacao,
            nivel=CLASSIFICACOES.index(resultado.classificacao),
            comprimento=len(senha),
            comprimento_avaliado=len(texto),
            criterios=criterios,
            recomendacoes=resultado.recomendacoes,
        )

    @app.errorhandler(RequestEntityTooLarge)
    def corpo_excessivo(_):
        return jsonify(erro="Requisição maior que o limite permitido."), 413

    return app


def main() -> int:
    print("Verificador de força de senhas (análise local e estimativa estrutural).")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            senha = getpass("Digite a senha (entrada oculta): ")
    except GetPassWarning:
        print("Entrada oculta indisponível. Execute em um terminal interativo.")
        return 1
    except EOFError:
        print("\nOperação cancelada: entrada encerrada.")
        return 1
    except KeyboardInterrupt:
        print("\nOperação cancelada.")
        return 130
    try:
        resultado = analisar_senha(senha)
    except ValueError as erro:
        print(str(erro))
        return 1
    finally:
        del senha
    print(f"Classificação: {resultado.classificacao}")
    print("Recomendações:")
    for recomendacao in resultado.recomendacoes:
        print(f"- {recomendacao}")
    return 0


def executar() -> int:
    parser = argparse.ArgumentParser(description="Verificador local de senhas")
    parser.add_argument(
        "--web", action="store_true", help="abre o servidor web local na porta 5000"
    )
    argumentos = parser.parse_args()
    if not argumentos.web:
        return main()
    try:
        app = criar_app()
    except ModuleNotFoundError as erro:
        if erro.name != "flask":
            raise
        print("Instale a interface web: python -m pip install -r requirements.txt")
        return 1
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(executar())
