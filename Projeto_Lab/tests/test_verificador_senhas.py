"""Testes unitários com entradas exclusivamente fictícias."""

import io
import unicodedata
import unittest
import warnings
from contextlib import redirect_stdout
from getpass import GetPassWarning
from unittest.mock import patch

from verificador_senhas import analisar_senha, executar, main


class TestVerificador(unittest.TestCase):
    def test_limites_de_comprimento(self):
        base = "rT7!vK9@pL2#xN5$"
        casos = (
            (7, "Muito fraca"),
            (8, "Fraca"),
            (11, "Fraca"),
            (12, "Forte"),
            (15, "Forte"),
            (16, "Muito forte"),
        )
        for tamanho, esperado in casos:
            with self.subTest(tamanho=tamanho):
                resultado = analisar_senha(base[:tamanho])
                self.assertEqual(resultado.classificacao, esperado)

    def test_classificacoes_por_variedade(self):
        casos = (
            ("", "Muito fraca"),
            ("rvmkptnz", "Fraca"),
            ("rv7mk9pt2nz5", "Média"),
            ("rV7mK9pT2nZ5", "Forte"),
        )
        for texto, esperado in casos:
            with self.subTest(esperado=esperado):
                self.assertEqual(analisar_senha(texto).classificacao, esperado)

    def test_cada_recomendacao_ausente(self):
        casos = (
            ("RT7!VK9@PL2#XN5$", "minúsculas"),
            ("rt7!vk9@pl2#xn5$", "maiúsculas"),
            ("rTv!vKp@pLx#xNq$", "números"),
            ("rT7vK9pL2xN5mQ8z", "especiais"),
        )
        for texto, categoria in casos:
            with self.subTest(categoria=categoria):
                inclusoes = [
                    r for r in analisar_senha(texto).recomendacoes
                    if r.startswith("Inclua")
                ]
                self.assertEqual(len(inclusoes), 1)
                self.assertIn(categoria, inclusoes[0])

    def test_espacos_e_invisiveis_nao_inflam_nota(self):
        for preenchimento in (" ", "\t", "\n", "\u200b", "\u0301"):
            resultado = analisar_senha("rT7" + preenchimento * 20)
            self.assertEqual(resultado.classificacao, "Muito fraca")
        self.assertEqual(analisar_senha(" " * 20).classificacao, "Muito fraca")
        recomendacoes = analisar_senha("rT7\u200b").recomendacoes
        self.assertTrue(any("especiais" in r for r in recomendacoes))
        self.assertTrue(any("invisíveis" in r for r in recomendacoes))

    def test_padroes_dominantes_e_blocos_repetidos(self):
        casos = (
            "Ab1!Ab1!Ab1!Ab1!",
            "aaaaaaaavK9!",
            "abcdefghK9!x",
            "ABCDEFGHK9!x",
            "hgfedcbaK9!x",
            "HGFEDCBAK9!x",
            "87654321K9!x",
            "qwertyuiK9!x",
            "IUYTREWQK9!x",
        )
        for indice, texto in enumerate(casos):
            with self.subTest(caso=indice):
                self.assertEqual(analisar_senha(texto).classificacao, "Fraca")

    def test_sequencia_minoritaria_nao_limita_senha(self):
        casos = (
            "rT7!abcdK9@pL2#xN5$",
            "rT7!4321K9@pL2#xN5$",
            "rT7!qwerK9@pL2#xN5$",
            "rT7!aaaaK9@pL2#xN5$",
        )
        for indice, texto in enumerate(casos):
            with self.subTest(caso=indice):
                resultado = analisar_senha(texto)
                self.assertEqual(resultado.classificacao, "Muito forte")

    def test_limite_de_predominancia_sem_contar_sobreposicoes(self):
        # Oito posições previsíveis de 16: penaliza no limite de 50%.
        resultado = analisar_senha("abcdefghR7!pL2$x")
        self.assertEqual(resultado.classificacao, "Fraca")
        # Sete posições de 17: os trechos sobrepostos não somam novamente.
        resultado = analisar_senha("abcdefgR7!pL2$xN5")
        self.assertEqual(resultado.classificacao, "Muito forte")

    def test_unicode_visivel(self):
        resultado = analisar_senha("áT7!vK9@pL2#xN5$")
        self.assertEqual(resultado.classificacao, "Muito forte")

    def test_unicode_equivalente_tem_resultado_identico(self):
        composto = "áT7!vK9@pL2#xN5$"
        decomposto = unicodedata.normalize("NFD", composto)
        self.assertNotEqual(composto, decomposto)
        self.assertEqual(
            analisar_senha(composto), analisar_senha(decomposto)
        )

    def test_limites_de_bonus_por_comprimento(self):
        base = "rvmpktnzghsuoxiljfewbrvmpktnzghsu"
        casos = (
            (19, "Fraca"),
            (20, "Forte"),
            (27, "Forte"),
            (28, "Muito forte"),
        )
        for tamanho, esperado in casos:
            with self.subTest(tamanho=tamanho):
                resultado = analisar_senha(base[:tamanho])
                self.assertEqual(resultado.classificacao, esperado)

    def test_frases_longas_sem_exigir_todas_as_categorias(self):
        resultado = analisar_senha("jabuticaba farol nuvem trilha horizonte")
        self.assertEqual(resultado.classificacao, "Muito forte")
        # Um trecho alfabético dentro de uma frase não deve dominar a nota.
        resultado = analisar_senha("vento leva abcdef sobre montanhas distantes")
        self.assertEqual(resultado.classificacao, "Muito forte")

    def test_comprimento_nao_compensa_baixa_diversidade_ou_padrao(self):
        for texto in ("a" * 100, "ab1!" * 20, "abcdefgh" * 10):
            self.assertEqual(analisar_senha(texto).classificacao, "Fraca")
        # Sete caracteres distintos não habilitam o bônus de comprimento.
        resultado = analisar_senha("abacabadabacabaeabacabadabacabafg")
        self.assertEqual(resultado.classificacao, "Fraca")

    def test_interface_nao_expoe_senha(self):
        segredo = "rT7!vK9@pL2#xN5$"
        with patch("verificador_senhas.getpass", return_value=segredo) as entrada:
            with redirect_stdout(io.StringIO()) as saida:
                self.assertEqual(main(), 0)
        entrada.assert_called_once()
        self.assertNotIn(segredo, saida.getvalue())
        self.assertNotIn(segredo, repr(analisar_senha(segredo)))
        self.assertIn("Muito forte", saida.getvalue())

    def test_codigos_de_cancelamento(self):
        for erro, codigo in ((EOFError, 1), (KeyboardInterrupt, 130)):
            with patch("verificador_senhas.getpass", side_effect=erro):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(), codigo)

    def test_sem_terminal_nao_le_em_claro(self):
        def entrada(_):
            warnings.warn("Sem terminal", GetPassWarning)
            self.fail("Não deve continuar a leitura")

        with patch("verificador_senhas.getpass", side_effect=entrada):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)

    def test_limite_exato_de_entrada(self):
        resultado = analisar_senha("x" * 4096)
        self.assertEqual(resultado.classificacao, "Fraca")

    def test_senhas_comuns_e_variacoes_sao_muito_fracas(self):
        casos = (
            "password", "P@ssw0rd2026!", "Senha123!", "Sênha 2026!",
            "Adm1n2026!", "1234567890", "correct horse battery staple",
            "que a força esteja com você",
        )
        for indice, senha in enumerate(casos):
            with self.subTest(caso=indice):
                resultado = analisar_senha(senha)
                self.assertEqual(resultado.classificacao, "Muito fraca")
                self.assertTrue(any(
                    "conhecidas" in r for r in resultado.recomendacoes
                ))

    def test_palavra_comum_embutida_nao_bloqueia_frase_distinta(self):
        resultado = analisar_senha("farol senha montanha jabuticaba trilha")
        self.assertEqual(resultado.classificacao, "Muito forte")

    def test_entrada_excessiva_e_tipo_invalido(self):
        with self.assertRaises(ValueError):
            analisar_senha("x" * 4097)
        with self.assertRaises(TypeError):
            analisar_senha(None)
        with patch("verificador_senhas.getpass", return_value="x" * 4097):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)

    def test_sem_argumentos_mantem_o_terminal(self):
        with patch("sys.argv", ["verificador_senhas.py"]):
            with patch("verificador_senhas.main", return_value=0) as terminal:
                self.assertEqual(executar(), 0)
        terminal.assert_called_once_with()

    def test_modo_web_inicia_apenas_no_host_local_sem_debug(self):
        with patch("sys.argv", ["verificador_senhas.py", "--web"]):
            with patch("verificador_senhas.criar_app") as fabrica:
                self.assertEqual(executar(), 0)
        fabrica.return_value.run.assert_called_once_with(
            host="127.0.0.1", port=5000, debug=False, use_reloader=False
        )

    def test_modo_web_sem_flask_orienta_a_instalacao(self):
        erro = ModuleNotFoundError("Pacote indisponível", name="flask")
        with patch("sys.argv", ["verificador_senhas.py", "--web"]):
            with patch("verificador_senhas.criar_app", side_effect=erro):
                with redirect_stdout(io.StringIO()) as saida:
                    self.assertEqual(executar(), 1)
        self.assertIn("pip install -r requirements.txt", saida.getvalue())


if __name__ == "__main__":
    unittest.main()
