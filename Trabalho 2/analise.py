# Análise dos CSVs gerados pelo rodar_bateria.sh: médias, speedup, eficiência e gráficos.
# Não executa nenhum K-Means: só lê resultados/<impl>_<nome>_<variante>.csv.
# (A parte do resumo segue a ideia do script de bateria em Python proposto no grupo.)
#
# Uso: python analise.py --nome sint_600000
# Saída: resultados/resumo_<nome>.csv, resultados/alteracoes_<nome>.csv,
#        tabelas em Markdown na tela e, se o matplotlib estiver instalado, graficos/*.png
import argparse, csv, glob, os
from statistics import mean, median, stdev

def parse_args():
    p = argparse.ArgumentParser(description="Resumo e gráficos das baterias.")
    p.add_argument("--nome", default="sint_600000", help="conjunto de dados (sufixo dos CSVs)")
    p.add_argument("--pasta", default="resultados")
    p.add_argument("--graficos", default="graficos")
    return p.parse_args()

def le_execucoes(pasta, nome):
    """Junta as linhas de todos os CSVs desse conjunto de dados."""
    linhas = []
    for arq in sorted(glob.glob(os.path.join(pasta, f"*_{nome}_*.csv"))):
        if os.path.basename(arq).startswith(("resumo_", "alteracoes_")):
            continue # não lê as próprias saídas
        with open(arq, newline="") as f:
            linhas += list(csv.DictReader(f))
    return linhas

def agrupa(linhas):
    """(impl, variante, p) -> lista de t_total (uma entrada por repetição)."""
    grupos = {}
    for l in linhas:
        chave = (l["impl"], l["variante"], int(l["p"]))
        grupos.setdefault(chave, {"t": [], "oversub": int(l["oversub"]), "inercia": set()})
        grupos[chave]["t"].append(float(l["t_total"]))
        grupos[chave]["inercia"].add(l["inercia"])
    return grupos

def resumo(grupos):
    """Média, mediana, desvio, speedup S = T(1)/T(p) e eficiência E = S/p, por versão."""
    t_seq = mean(grupos[("seq", "base", 1)]["t"]) if ("seq", "base", 1) in grupos else None
    tabela = []
    for (impl, var, p), g in sorted(grupos.items()):
        if var != "base":
            continue # alterações vão para a outra tabela
        m = mean(g["t"])
        t1 = mean(grupos[(impl, var, 1)]["t"]) # T(1) da PRÓPRIA versão
        tabela.append(dict(
            impl=impl, p=p, n=len(g["t"]), oversub=g["oversub"],
            media_s=m, mediana_s=median(g["t"]),
            desvio_s=stdev(g["t"]) if len(g["t"]) > 1 else 0.0,
            speedup=t1 / m, eficiencia=t1 / m / p,
            ganho_vs_seq=(t_seq / m) if t_seq else "",
            inercias=len(g["inercia"]))) # 1 = todas as repetições chegaram à mesma inércia
    return tabela

def alteracoes(grupos):
    """Cada variante comparada com a versão base no mesmo p: ganho = T_base / T_variante."""
    tabela = []
    for (impl, var, p), g in sorted(grupos.items()):
        if var == "base" or (impl, "base", p) not in grupos:
            continue
        tb, tv = mean(grupos[(impl, "base", p)]["t"]), mean(g["t"])
        tabela.append(dict(impl=impl, variante=var, p=p, n=len(g["t"]),
                           base_s=tb, variante_s=tv, ganho=tb / tv))
    return tabela

def grava_csv(caminho, tabela):
    with open(caminho, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(tabela[0]))
        w.writeheader()
        w.writerows(tabela)

def imprime_markdown(tabela, colunas, fmt):
    print("| " + " | ".join(colunas) + " |")
    print("|" + "---|" * len(colunas))
    for l in tabela:
        print("| " + " | ".join(fmt.get(c, "{}").format(l[c]) for c in colunas) + " |")
    print()

# ---------------------------------------------------------------- gráficos
COR = {"mpi": "#2a78d6", "spark": "#eb6834"} # paleta categórica validada (slots 1 e 2)
TINTA, TINTA_2, GRADE = "#0b0b0b", "#52514e", "#e4e3df"

def eixo_limpo(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(TINTA_2)
    ax.tick_params(colors=TINTA_2, labelsize=9)
    ax.grid(True, color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)

def graficos(tabela, alt, pasta, nome):
    try:
        import matplotlib
        matplotlib.use("Agg") # sem janela: só grava os PNGs
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib não instalado: gráficos não gerados)")
        return
    os.makedirs(pasta, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "text.color": TINTA, "axes.labelcolor": TINTA_2})

    def serie(impl, campo):
        ls = [l for l in tabela if l["impl"] == impl]
        return [l["p"] for l in ls], [l[campo] for l in ls]

    figs = [("tempo", "media_s", "Tempo do laço (s, escala log)", True),
            ("speedup", "speedup", "Speedup S = T(1)/T(p)", False),
            ("eficiencia", "eficiencia", "Eficiência E = S/p", False)]
    for arq, campo, titulo, log in figs:
        fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=150)
        eixo_limpo(ax)
        ax.axvspan(16.5, 160, color="#f1f0ec", zorder=0) # região sem núcleo físico livre
        ax.text(150, 0.97, "acima de 16 núcleos físicos", transform=ax.get_xaxis_transform(),
                ha="right", va="top", fontsize=8, color=TINTA_2)
        if campo == "speedup":
            ps = [1, 2, 4, 8, 16]
            ax.plot(ps, ps, color=TINTA_2, linewidth=1, linestyle="--", label="ideal (S = p)")
        for impl in ("mpi", "spark"):
            x, y = serie(impl, campo)
            ax.plot(x, y, color=COR[impl], linewidth=2, marker="o", markersize=5,
                    markeredgecolor="white", markeredgewidth=1, label=impl.upper())
            ax.annotate(impl.upper(), (x[-1], y[-1]), xytext=(6, 0), textcoords="offset points",
                        va="center", fontsize=9, color=TINTA) # rótulo direto no fim da linha
        ax.set_xscale("log", base=2)
        ax.set_xticks([1, 2, 4, 8, 16, 32, 64, 128])
        ax.set_xticklabels(["1", "2", "4", "8", "16", "32", "64", "128"])
        ax.set_xlim(0.8, 180)
        if log:
            ax.set_yscale("log")
        ax.set_xlabel("p (processos MPI / núcleos do Spark)")
        ax.set_title(f"{titulo} - {nome}", loc="left", fontsize=11, color=TINTA)
        ax.legend(frameon=False, fontsize=9, loc="best")
        fig.tight_layout()
        fig.savefig(os.path.join(pasta, f"{arq}_{nome}.png"))
        plt.close(fig)

    if alt: # barras horizontais: ganho de cada alteração (1 = sem efeito)
        fig, ax = plt.subplots(figsize=(6.4, 0.42 * len(alt) + 1.2), dpi=150)
        eixo_limpo(ax)
        ax.grid(axis="y", visible=False)
        rot = [f"{a['impl'].upper()} {a['variante']} (p={a['p']})" for a in alt]
        val = [a["ganho"] for a in alt]
        ax.barh(range(len(alt)), val, height=0.6, color=[COR[a["impl"]] for a in alt])
        ax.axvline(1, color=TINTA_2, linewidth=1)
        for i, v in enumerate(val):
            ax.text(v, i, f" {v:.2f}x", va="center", fontsize=8, color=TINTA)
        ax.set_yticks(range(len(alt)))
        ax.set_yticklabels(rot, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("ganho = T(base) / T(alteração)   (> 1: mais rápido)")
        ax.set_title(f"Alterações vs. versão base - {nome}", loc="left", fontsize=11, color=TINTA)
        fig.tight_layout()
        fig.savefig(os.path.join(pasta, f"alteracoes_{nome}.png"))
        plt.close(fig)
    print(f"Gráficos em {pasta}/")

def main():
    a = parse_args()
    grupos = agrupa(le_execucoes(a.pasta, a.nome))
    tab, alt = resumo(grupos), alteracoes(grupos)
    grava_csv(os.path.join(a.pasta, f"resumo_{a.nome}.csv"), tab)
    if alt:
        grava_csv(os.path.join(a.pasta, f"alteracoes_{a.nome}.csv"), alt)

    f2 = "{:.2f}"
    imprime_markdown(tab, ["impl", "p", "n", "oversub", "media_s", "mediana_s", "desvio_s",
                           "speedup", "eficiencia", "ganho_vs_seq", "inercias"],
                     {c: f2 for c in ("media_s", "mediana_s", "desvio_s", "speedup", "eficiencia")}
                     | {"ganho_vs_seq": "{:.2f}" if tab and tab[0]["ganho_vs_seq"] != "" else "{}"})
    if alt:
        imprime_markdown(alt, ["impl", "variante", "p", "n", "base_s", "variante_s", "ganho"],
                         {c: f2 for c in ("base_s", "variante_s", "ganho")})
    graficos(tab, alt, a.graficos, a.nome)

if __name__ == "__main__":
    main()
