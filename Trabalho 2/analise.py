import argparse
import csv
from pathlib import Path
from statistics import mean, median, stdev
from graficos import gerar_graficos

def parse_args():
    parser = argparse.ArgumentParser(description="Análise dos resultados do K-means.")
    parser.add_argument("--nome", default="sint_600000")
    parser.add_argument("--pasta", default="resultados")
    parser.add_argument("--graficos", default="graficos")
    return parser.parse_args()


def le_execucoes(pasta, nome):
    """Lê os CSVs das execuções, sem incluir as tabelas geradas pela análise"""

    execucoes = []

    for caminho in sorted(Path(pasta).glob(f"*_{nome}_*.csv")):
        if caminho.name.startswith(("resumo_", "alteracoes_")):
            continue
        
        with caminho.open(newline="", encoding="utf-8") as arquivo:
            execucoes.extend(csv.DictReader(arquivo))
    
    return execucoes


def agrupa(execucoes):
    """Separa as repetições por implementação, variante e paralelismo"""

    grupos = {}

    for execucao in execucoes:
        chave = (execucao["impl"], execucao["variante"], int(execucao["p"]))
        
        if chave not in grupos:
            grupos[chave] = {
                "t": [],
                "oversub": int(execucao["oversub"]),
                "inercia": set(),
            }
        
        grupos[chave]["t"].append(float(execucao["t_total"]))
        grupos[chave]["inercia"].add(execucao["inercia"])
        
    print(grupos)
    return grupos


def resumo(grupos):
    """Calcula os indicadores das versões base"""

    tempo_sequencial = None

    if ("seq", "base", 1) in grupos:
        tempo_sequencial = mean(grupos[("seq", "base", 1)]["t"])

    tabela = []

    for (implementacao, variante, p), grupo in sorted(grupos.items()):
        
        if variante != "base":
            continue

        tempos = grupo["t"]
        media = mean(tempos)
        tempo_p1 = mean(grupos[(implementacao, "base", 1)]["t"])
        speedup = tempo_p1 / media
        eficiencia = speedup / p
        desvio = stdev(tempos) if len(tempos) > 1 else 0.0

        ganho_sequencial = ""
        if tempo_sequencial is not None:
            ganho_sequencial = tempo_sequencial / media

        tabela.append({
            "impl": implementacao,
            "p": p,
            "n": len(tempos),
            "oversub": grupo["oversub"],
            "media_s": media,
            "mediana_s": median(tempos),
            "desvio_s": desvio,
            "speedup": speedup,
            "eficiencia": eficiencia,
            "ganho_vs_seq": ganho_sequencial,
            "inercias": len(grupo["inercia"]),
        })

    return tabela


def alteracoes(grupos):
    """Compara cada alteração com a base da mesma implementação e do mesmo p"""

    tabela = []

    for (implementacao, variante, p), grupo in sorted(grupos.items()):
        chave_base = (implementacao, "base", p)
        
        if variante == "base" or chave_base not in grupos:
            continue

        tempo_base = mean(grupos[chave_base]["t"])
        tempo_variante = mean(grupo["t"])
        
        tabela.append({
            "impl": implementacao,
            "variante": variante,
            "p": p,
            "n": len(grupo["t"]),
            "base_s": tempo_base,
            "variante_s": tempo_variante,
            "ganho": tempo_base / tempo_variante,
        })

    return tabela


def grava_csv(caminho, tabela):
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=list(tabela[0]))
        writer.writeheader()
        writer.writerows(tabela)


def imprime_tabela(tabela):
    colunas = list(tabela[0])
    print("| " + " | ".join(colunas) + " |")
    print("|" + "---|" * len(colunas))
    for linha in tabela:
        valores = []
        for valor in linha.values():
            if isinstance(valor, float):
                valores.append(f"{valor:.2f}")
            else:
                valores.append(str(valor))
        print("| " + " | ".join(valores) + " |")
    print()


def main():
    argumentos = parse_args()
    pasta = Path(argumentos.pasta)

    execucoes = le_execucoes(pasta, argumentos.nome)
    grupos = agrupa(execucoes)
    tabela_resumo = resumo(grupos)
    tabela_alteracoes = alteracoes(grupos)

    grava_csv(pasta / f"resumo_{argumentos.nome}.csv", tabela_resumo)
    imprime_tabela(tabela_resumo)

    if tabela_alteracoes:
        grava_csv(pasta / f"alteracoes_{argumentos.nome}.csv", tabela_alteracoes)
        imprime_tabela(tabela_alteracoes)

    gerar_graficos(tabela_resumo, tabela_alteracoes, grupos,argumentos.graficos, argumentos.nome)

if __name__ == "__main__":
    main()
