# otimizar_fotos.py
# ------------------------------------------------------------------
# Prepara as fotos de uma turma para o site.
#
# O que ele faz com cada foto (.jpg, .jpeg, .png):
#   1. Gira a foto para a posição certa (usando a informação EXIF
#      que o celular grava) e DEPOIS apaga todos os metadados EXIF
#      (inclusive a localização GPS), para proteger a privacidade.
#   2. Salva duas cópias em JPEG (qualidade 80, progressivo):
#        fotos/       -> lado maior com no máximo 1600 px (foto grande)
#        fotos/mini/  -> lado maior com no máximo 480 px  (miniatura)
#   3. Dá nomes simples: minúsculas, sem espaço e sem acento, em
#      sequência. Ex.: 3ia-01.jpg, 3ia-02.jpg ...
#
# Onde ficam as pastas (exemplo com a turma "3ia"):
#   turmas/_originais/3ia/   -> fotos, vídeos e .txt originais (NÃO vão para o site;
#                               a pasta _originais está no .gitignore)
#   turmas/3ia/fotos/        -> fotos grandes que o site usa
#   turmas/3ia/fotos/mini/   -> miniaturas que o site usa
#
# Só as fotos soltas na pasta da turma são usadas: SUBPASTAS são ignoradas.
# Para deixar uma foto fora do site (ex.: cartaz digital), mova o original
# para uma subpasta, como turmas/_originais/3mb/_nao-usar/.
# Atenção: tirar ou pôr fotos muda a numeração (3mb-01, 3mb-02...) na próxima
# vez que o script rodar; confira os nomes das fotos na página da turma.
#
# Os arquivos ORIGINAIS não são apagados nem alterados.
#
# Como usar (no terminal, na pasta do site):
#   pip install Pillow
#   python ferramentas/otimizar_fotos.py 3ia
#
# O nome da turma (ex.: "3ia") é o nome da pasta em turmas/_originais/
# e também vira o prefixo dos nomes das fotos. Use letras minúsculas e
# números, sem espaço e sem acento.
# ------------------------------------------------------------------

import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

# pasta "turmas" do site (este arquivo fica em ferramentas/, uma pasta abaixo do site)
PASTA_TURMAS = Path(__file__).resolve().parent.parent / "turmas"

TAMANHO_GRANDE = 1600  # px do lado maior da foto grande
TAMANHO_MINI = 480     # px do lado maior da miniatura
QUALIDADE = 80         # qualidade do JPEG (0 a 100)
EXTENSOES = {".jpg", ".jpeg", ".png"}


def nome_simples(texto):
    """Tira acentos, espaços e símbolos e deixa tudo minúsculo.
    Ex.: 'Turma 3º A' -> 'turma3a'"""
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9-]", "", texto.lower())


def ordem_natural(caminho):
    """Ordena '... 2.jpg' antes de '... 10.jpg' (como uma pessoa faria)."""
    partes = re.split(r"(\d+)", caminho.name)
    return [int(p) if p.isdigit() else p.lower() for p in partes]


def tamanho_kb(caminho):
    return f"{caminho.stat().st_size / 1024:.0f} KB"


def salvar(imagem, lado_maior, destino):
    """Reduz a foto (nunca aumenta) e salva como JPEG sem metadados."""
    copia = imagem.copy()
    copia.thumbnail((lado_maior, lado_maior))  # mantém a proporção
    # Não passamos exif=..., então nenhum metadado é gravado.
    copia.save(destino, "JPEG", quality=QUALIDADE, progressive=True, optimize=True)
    return copia.size


def main():
    if len(sys.argv) != 2:
        print("Uso: python ferramentas/otimizar_fotos.py NOME_DA_TURMA   (ex.: 3ia)")
        sys.exit(1)

    turma = sys.argv[1]
    if turma != nome_simples(turma):
        print(f'Nome inválido: "{turma}". Use só minúsculas, números e "-" (ex.: "{nome_simples(turma)}").')
        sys.exit(1)

    entrada = PASTA_TURMAS / "_originais" / turma  # onde estão os originais
    saida = PASTA_TURMAS / turma                    # pasta da turma no site
    prefixo = turma

    if not entrada.is_dir():
        print("Pasta não encontrada:", entrada)
        print("Coloque as fotos originais em turmas/_originais/" + turma + "/")
        sys.exit(1)

    pasta_grande = saida / "fotos"
    pasta_mini = pasta_grande / "mini"
    pasta_mini.mkdir(parents=True, exist_ok=True)

    # iterdir() olha só a pasta da turma (não entra em subpastas) e
    # is_file() descarta as subpastas: fotos em _nao-usar/ ficam de fora.
    fotos = sorted(
        (f for f in entrada.iterdir() if f.is_file() and f.suffix.lower() in EXTENSOES),
        key=ordem_natural,
    )
    if not fotos:
        print("Nenhuma foto encontrada em", entrada)
        sys.exit(1)

    digitos = max(2, len(str(len(fotos))))  # 01, 02 ... ou 001 se tiver 100+
    linhas = []
    total_antes = total_depois = 0

    for numero, original in enumerate(fotos, start=1):
        novo_nome = f"{prefixo}-{numero:0{digitos}d}.jpg"

        with Image.open(original) as imagem:
            # 1) gira conforme o EXIF; o resultado já sai sem a orientação
            imagem = ImageOps.exif_transpose(imagem)
            # 2) JPEG não aceita transparência: converte para RGB
            imagem = imagem.convert("RGB")
            # 3) salva as duas versões (sem EXIF/GPS)
            larg_g, alt_g = salvar(imagem, TAMANHO_GRANDE, pasta_grande / novo_nome)
            larg_m, alt_m = salvar(imagem, TAMANHO_MINI, pasta_mini / novo_nome)

        antes = original.stat().st_size
        depois = (pasta_grande / novo_nome).stat().st_size
        total_antes += antes
        total_depois += depois
        linhas.append((original.name, novo_nome, tamanho_kb(original),
                       tamanho_kb(pasta_grande / novo_nome), tamanho_kb(pasta_mini / novo_nome),
                       f"{larg_m}x{alt_m}"))

    # Tabela final
    cab = ("original", "novo", "antes", "depois", "mini", "mini (px)")
    largura = [max(len(str(l[i])) for l in linhas + [cab]) for i in range(len(cab))]
    print(" | ".join(c.ljust(w) for c, w in zip(cab, largura)))
    print("-+-".join("-" * w for w in largura))
    for l in linhas:
        print(" | ".join(str(c).ljust(w) for c, w in zip(l, largura)))
    print(f"\n{len(linhas)} fotos. Total (versão 1600 px): "
          f"{total_antes / 1024 / 1024:.1f} MB -> {total_depois / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
