"""
Tabelas de controle da ingestão (seção 3.2 do docs/architecture.md).

São arquivos JSON pequenos em data/raw/_controle/ que registram o que já foi
gravado na Bronze:
- controle_scr.json: para cada ano, a versão do ZIP (ETag) e a versão de cada
  CSV (data dentro do ZIP e CRC32), com o status da gravação;
- controle_selic.json: o watermark (maior VALDATA já gravada).

É consultando esses arquivos que o pipeline sabe o que pode pular, e por isso
rodar duas vezes não duplica a Bronze.
"""

import json
from pathlib import Path


def ler_controle(caminho):
    """Lê a tabela de controle. Se o arquivo ainda não existe, devolve {}."""
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def gravar_controle(caminho, dados):
    """
    Grava a tabela de controle de forma atômica: escreve primeiro em
    "<arquivo>.tmp" e só depois renomeia para o nome final. Se o processo
    morrer no meio da escrita, o arquivo anterior continua inteiro — nunca
    fica um JSON pela metade.
    """
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    temporario.replace(caminho)
