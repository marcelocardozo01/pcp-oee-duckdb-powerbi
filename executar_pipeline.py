"""Roda o projeto de ponta a ponta.

  python executar_pipeline.py            -> ingestao, trusted/analytics, exportacao, validacao e painel HTML
  python executar_pipeline.py --gerar    -> antes, gera de novo a base ficticia

Para na primeira etapa que falhar. Depois e so abrir painel_html/saida/index.html
ou atualizar o PBIP da pasta powerbi/.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ETAPAS = [
    ("Ingestao das 5 origens", RAIZ / "pipeline" / "01_ingestao.py"),
    ("Trusted e analytics", RAIZ / "pipeline" / "02_trusted.py"),
    ("Exportacao", RAIZ / "pipeline" / "03_exportar.py"),
    ("Validacao dos numeros", RAIZ / "pipeline" / "04_validar.py"),
    ("Painel HTML", RAIZ / "painel_html" / "gerar_painel.py"),
]
if "--gerar" in sys.argv:
    ETAPAS.insert(0, ("Geracao da base ficticia", RAIZ / "gerador" / "gerar_dados.py"))

env = dict(os.environ, PYTHONIOENCODING="utf-8")
for nome, script in ETAPAS:
    print(f"\n=== {nome} ===", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, str(script)], cwd=RAIZ, env=env)
    if r.returncode != 0:
        sys.exit(f"Falhou em: {nome}")
    print(f"({time.time() - t0:.1f}s)", flush=True)
print("\nPipeline concluido.")
