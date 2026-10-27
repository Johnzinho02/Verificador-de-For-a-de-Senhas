"""Integração do executável; getpass usa somente entradas fictícias."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

PROJETO = Path(__file__).resolve().parents[1]
ENTRADA = "verificador_senhas.py"
SEGREDO_FICTICIO = "rT7!vK9@pL2#xN5$"


class TestCLI(unittest.TestCase):
    def executar(self, configuracao):
        codigo = (
            "import runpy\n"
            "from unittest.mock import patch\n"
            "from getpass import GetPassWarning\n"
            f"with patch('getpass.getpass', {configuracao}):\n"
            f"    runpy.run_path({ENTRADA!r}, run_name='__main__')\n"
        )
        ambiente = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=PROJETO,
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            env=ambiente,
            check=False,
        )

    def test_entrada_conclui_sem_expor_senha(self):
        resultado = self.executar(f"return_value={SEGREDO_FICTICIO!r}")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("Classificação: Muito forte", resultado.stdout)
        self.assertNotIn(SEGREDO_FICTICIO, resultado.stdout)
        self.assertNotIn(SEGREDO_FICTICIO, resultado.stderr)

    def test_senha_fraca_tambem_retorna_sucesso(self):
        resultado = self.executar("return_value='x'")
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("Classificação: Muito fraca", resultado.stdout)

    def test_codigos_de_erro(self):
        casos = (
            ("side_effect=EOFError", 1, "cancelada"),
            ("side_effect=KeyboardInterrupt", 130, "cancelada"),
            ("side_effect=GetPassWarning", 1, "Entrada oculta indisponível"),
            ("return_value='x' * 4097", 1, "no máximo 4096"),
        )
        for configuracao, codigo, mensagem in casos:
            with self.subTest(cenario=configuracao, codigo=codigo):
                resultado = self.executar(configuracao)
                self.assertEqual(resultado.returncode, codigo, resultado.stderr)
                self.assertIn(mensagem, resultado.stdout)
                self.assertEqual(resultado.stderr, "")


if __name__ == "__main__":
    unittest.main()
