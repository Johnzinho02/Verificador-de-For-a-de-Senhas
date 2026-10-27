"""Medição local de requisições WSGI com entrada sintética, sem abrir portas."""

import argparse
import json
import math
import platform
import random
import statistics
import string
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verificador_senhas import criar_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=40)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000 or not 1 <= args.workers <= 16:
        parser.error("Use 1 a 1000 amostras e 1 a 16 workers.")

    # Gerador determinístico para benchmark; não gera senhas para uso real.
    gerador = random.Random(2026)
    entrada = "".join(gerador.choices(
        string.ascii_letters + string.digits + "!@#$%&", k=4096
    ))
    app = criar_app({
        "TESTING": True, "RATE_LIMIT_MAX_REQUESTS": args.samples + 1,
    })

    def medir(_):
        inicio = perf_counter()
        with app.test_client() as client:
            with client.post("/api/analisar", json={"senha": entrada}) as resposta:
                if resposta.status_code != 200:
                    raise RuntimeError("O benchmark recebeu uma resposta inesperada.")
        return (perf_counter() - inicio) * 1000

    medir(None)  # Aquecimento fora das amostras medidas.
    inicio = perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        tempos = sorted(executor.map(medir, range(args.samples)))
    duracao = perf_counter() - inicio
    print(json.dumps({
        "python": platform.python_version(),
        "sistema": platform.system(),
        "amostras": args.samples,
        "workers": args.workers,
        "caracteres_por_entrada": len(entrada),
        "media_ms": round(statistics.mean(tempos), 2),
        "p95_ms": round(tempos[math.ceil(len(tempos) * 0.95) - 1], 2),
        "requisicoes_por_segundo": round(len(tempos) / duracao, 2),
        "escopo": "cliente Flask em memória; não mede rede ou servidor WSGI externo",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
