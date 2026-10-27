"""Testes HTTP com o cliente Flask, sem abrir portas ou usar senhas reais."""

import importlib.util
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

from verificador_senhas import analisar_senha, criar_app

FLASK_DISPONIVEL = importlib.util.find_spec("flask") is not None


class Pagina(HTMLParser):
    """Extrai controles e textos sem depender da formatação do HTML."""

    def __init__(self, html):
        super().__init__()
        self.elementos = []
        self.textos = {"title": [], "brand": [], "footer": []}
        self.ativos = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        atributos = dict(attrs)
        self.elementos.append((tag, atributos))
        if tag in ("title", "footer"):
            self.ativos.add(tag)
        if tag == "a" and "brand" in atributos.get("class", "").split():
            self.ativos.add("brand")

    def handle_endtag(self, tag):
        self.ativos.discard(tag)
        if tag == "a":
            self.ativos.discard("brand")

    def handle_data(self, data):
        for chave in self.ativos:
            self.textos[chave].append(data)


@unittest.skipUnless(FLASK_DISPONIVEL, "Instale requirements.txt para testar Flask")
class TestWeb(unittest.TestCase):
    def setUp(self):
        self.app = criar_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_pagina_principal(self):
        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('lang="pt-BR"', resposta.text)
        self.assertIn('type="password"', resposta.text)
        self.assertIn('id="strength-meter"', resposta.text)
        self.assertIn("/static/app.js", resposta.text)
        self.assertIn("/static/style.css", resposta.text)

    def test_arquivos_estaticos(self):
        for nome in ("app.js", "style.css", "favicon.svg"):
            with self.subTest(arquivo=nome):
                with self.client.get(f"/static/{nome}") as resposta:
                    self.assertEqual(resposta.status_code, 200)

    def test_identidade_firepassjw_no_layout(self):
        pagina = Pagina(self.client.get("/").text)
        for regiao in ("title", "brand", "footer"):
            with self.subTest(regiao=regiao):
                self.assertIn("FirePassJW", "".join(pagina.textos[regiao]))
        marca = next(
            attrs for tag, attrs in pagina.elementos
            if tag == "a" and "brand" in attrs.get("class", "").split()
        )
        self.assertEqual(marca["aria-label"], "FirePassJW, início")

    def test_controles_de_senha_com_estado_inicial_seguro(self):
        pagina = Pagina(self.client.get("/").text)
        elementos = {
            attrs["id"]: (tag, attrs)
            for tag, attrs in pagina.elementos if "id" in attrs
        }
        tag, senha = elementos["password"]
        self.assertEqual(tag, "input")
        self.assertEqual(senha["type"], "password")
        self.assertEqual(senha["autocomplete"], "off")
        self.assertFalse(senha.get("value"))
        self.assertEqual(senha["data-limit"], "4096")
        for chave in ("toggle-password", "clear-password"):
            self.assertEqual(elementos[chave][0], "button")
            self.assertEqual(elementos[chave][1]["type"], "button")
        self.assertEqual(elementos["toggle-password"][1]["aria-pressed"], "false")
        self.assertIn("disabled", elementos["clear-password"][1])

    def test_rotulos_acessiveis_apontam_para_elementos_existentes(self):
        pagina = Pagina(self.client.get("/").text)
        ids = [attrs["id"] for _, attrs in pagina.elementos if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)), "Há IDs duplicados na página")
        for tag, attrs in pagina.elementos:
            for chave in ("aria-labelledby", "aria-describedby"):
                for referencia in attrs.get(chave, "").split():
                    self.assertIn(referencia, ids)
            if tag == "label" and "for" in attrs:
                self.assertIn(attrs["for"], ids)

    def test_barra_e_indicadores_iniciam_sem_analise(self):
        pagina = Pagina(self.client.get("/").text)
        barra = next(
            attrs for _, attrs in pagina.elementos
            if attrs.get("id") == "strength-meter"
        )
        self.assertEqual(barra["role"], "progressbar")
        self.assertEqual(barra["aria-valuenow"], "0")
        self.assertEqual(barra["aria-valuemax"], "5")
        criterios = {
            attrs["data-criterion"]
            for _, attrs in pagina.elementos if "data-criterion" in attrs
        }
        self.assertEqual(criterios, {
            "comprimento", "maiusculas", "minusculas", "numeros", "especiais",
        })

    def test_resultado_igual_ao_terminal(self):
        casos = (
            "", "rT7!vK9@pL2#xN5$", "Ab1!Ab1!Ab1!Ab1!",
            "jabuticaba farol nuvem trilha horizonte", "áT7!vK9@pL2#xN5$",
        )
        for indice, senha in enumerate(casos):
            with self.subTest(caso=indice):
                resposta = self.client.post("/api/analisar", json={"senha": senha})
                self.assertEqual(resposta.status_code, 200)
                dados = resposta.get_json()
                esperado = analisar_senha(senha)
                self.assertEqual(dados["classificacao"], esperado.classificacao)
                self.assertEqual(dados["recomendacoes"], list(esperado.recomendacoes))
                self.assertEqual(len(dados["criterios"]), 5)

    def test_indicadores_usam_texto_avaliado(self):
        resposta = self.client.post(
            "/api/analisar", json={"senha": "rT7" + "\u200b " * 20}
        )
        dados = resposta.get_json()
        self.assertEqual(dados["comprimento_avaliado"], 3)
        criterios = {c["id"]: c["atendido"] for c in dados["criterios"]}
        self.assertFalse(criterios["comprimento"])
        self.assertFalse(criterios["especiais"])
        self.assertTrue(criterios["maiusculas"])
        self.assertTrue(criterios["minusculas"])
        self.assertTrue(criterios["numeros"])

    def test_senha_nao_aparece_em_respostas_ou_logs(self):
        senha = "Ficticia7!vK9@pL2#"
        with self.assertNoLogs(self.app.logger):
            with self.assertNoLogs("werkzeug"):
                resposta = self.client.post("/api/analisar", json={"senha": senha})
        self.assertNotIn(senha, resposta.text)
        self.assertNotIn("senha", resposta.get_json())
        self.assertNotIn("Set-Cookie", resposta.headers)

    def test_cabecalhos_de_privacidade(self):
        for caminho in ("/", "/nao-existe"):
            resposta = self.client.get(caminho)
            self.assertEqual(resposta.headers["Cache-Control"], "no-store")
            self.assertEqual(resposta.headers["Referrer-Policy"], "no-referrer")
            self.assertEqual(resposta.headers["X-Frame-Options"], "DENY")
            self.assertEqual(resposta.headers["X-Content-Type-Options"], "nosniff")
            csp = resposta.headers["Content-Security-Policy"]
            self.assertIn("connect-src 'self'", csp)
            self.assertNotIn("unsafe-inline", csp)

    def test_tipos_invalidos_e_campos_inesperados(self):
        casos = (
            {}, [], None, {"senha": None}, {"senha": 123},
            {"senha": True}, {"senha": []}, {"senha": "x", "extra": "y"},
        )
        for indice, dados in enumerate(casos):
            with self.subTest(caso=indice):
                # data permite enviar o JSON null sem perder o Content-Type.
                resposta = self.client.post(
                    "/api/analisar", data=json.dumps(dados),
                    content_type="application/json",
                )
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("erro", resposta.get_json())

    def test_json_malformado(self):
        resposta = self.client.post(
            "/api/analisar", data='{"senha":', content_type="application/json"
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.get_json()["erro"], "JSON inválido.")

    def test_rejeita_formulario(self):
        resposta = self.client.post("/api/analisar", data={"senha": "ficticia"})
        self.assertEqual(resposta.status_code, 415)

    def test_rejeita_query_string(self):
        resposta = self.client.post(
            "/api/analisar?extra=1", json={"senha": "ficticia"}
        )
        self.assertEqual(resposta.status_code, 400)

    def test_api_nao_aceita_get(self):
        self.assertEqual(self.client.get("/api/analisar").status_code, 405)

    def test_limite_de_caracteres(self):
        resposta = self.client.post("/api/analisar", json={"senha": "x" * 4097})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("4096", resposta.get_json()["erro"])
        resposta = self.client.post("/api/analisar", json={"senha": "🔑" * 4096})
        self.assertEqual(resposta.status_code, 200)

    def test_limite_do_corpo_http(self):
        resposta = self.client.post(
            "/api/analisar", data="x" * (64 * 1024 + 1),
            content_type="application/json",
        )
        self.assertEqual(resposta.status_code, 413)
        self.assertIn("erro", resposta.get_json())

    def test_rejeita_origem_externa_e_aceita_local(self):
        resposta = self.client.post(
            "/api/analisar", json={"senha": "ficticia"},
            headers={"Origin": "https://externo.example"},
        )
        self.assertEqual(resposta.status_code, 403)
        resposta = self.client.post(
            "/api/analisar", json={"senha": "ficticia"},
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(resposta.status_code, 200)

    def test_rejeita_host_desconhecido(self):
        resposta = self.client.get("/", base_url="http://externo.example")
        self.assertEqual(resposta.status_code, 400)

    def test_senha_comum_tem_penalizacao_na_api(self):
        resposta = self.client.post(
            "/api/analisar", json={"senha": "P@ssw0rd2026!"}
        )
        self.assertEqual(resposta.get_json()["classificacao"], "Muito fraca")

    def test_limite_de_requisicoes_expira_sem_espera_real(self):
        agora = [100.0]
        app = criar_app({
            "TESTING": True, "RATE_LIMIT_MAX_REQUESTS": 2,
            "RATE_LIMIT_WINDOW": 60, "RATE_LIMIT_CLOCK": lambda: agora[0],
        })
        with app.test_client() as client:
            for _ in range(2):
                self.assertEqual(client.post(
                    "/api/analisar", json={"senha": "ficticia"}
                ).status_code, 200)
            resposta = client.post("/api/analisar", json={"senha": "ficticia"})
            self.assertEqual(resposta.status_code, 429)
            self.assertEqual(resposta.headers["Retry-After"], "60")
            self.assertEqual(resposta.headers["Cache-Control"], "no-store")
            agora[0] = 160.0
            self.assertEqual(client.post(
                "/api/analisar", json={"senha": "ficticia"}
            ).status_code, 200)

    def test_limite_independente_por_ip_sem_confiar_em_forwarded(self):
        app = criar_app({"TESTING": True, "RATE_LIMIT_MAX_REQUESTS": 1})
        with app.test_client() as client:
            self.assertEqual(client.post(
                "/api/analisar", json={"senha": "ficticia"}
            ).status_code, 200)
            self.assertEqual(client.post(
                "/api/analisar", json={"senha": "ficticia"},
                headers={"X-Forwarded-For": "192.0.2.99"},
            ).status_code, 429)
            self.assertEqual(client.post(
                "/api/analisar", json={"senha": "ficticia"},
                environ_overrides={"REMOTE_ADDR": "192.0.2.10"},
            ).status_code, 200)

    def test_requisicoes_concorrentes_respeitam_o_limite(self):
        app = criar_app({"TESTING": True, "RATE_LIMIT_MAX_REQUESTS": 5})

        def enviar(_):
            with app.test_client() as client:
                return client.post(
                    "/api/analisar", json={"senha": "ficticia"}
                ).status_code

        with ThreadPoolExecutor(max_workers=8) as executor:
            codigos = list(executor.map(enviar, range(12)))
        self.assertEqual(codigos.count(200), 5)
        self.assertEqual(codigos.count(429), 7)

    def test_entradas_maximas_em_paralelo(self):
        # Conteúdo sintético; sem teste de tempo dependente da máquina.
        senha = ("rT7!vK9@pL2#xN5$" * 256)[:4096]

        def enviar(_):
            with self.app.test_client() as client:
                return client.post(
                    "/api/analisar", json={"senha": senha}
                ).status_code

        with ThreadPoolExecutor(max_workers=4) as executor:
            codigos = list(executor.map(enviar, range(8)))
        self.assertEqual(codigos, [200] * 8)


if __name__ == "__main__":
    unittest.main()
