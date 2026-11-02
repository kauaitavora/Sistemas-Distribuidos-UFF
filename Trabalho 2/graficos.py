from pathlib import Path
from statistics import stdev
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use("Agg")


def salvar(figura, pasta, arquivo):
    figura.tight_layout()
    figura.savefig(Path(pasta) / arquivo, dpi=150)
    plt.close(figura)


def eixo_paralelismo(eixo, tabela):
    ps = sorted({linha["p"] for linha in tabela})
    eixo.set_xscale("log", base=2)
    eixo.set_xticks(ps, labels=ps)
    eixo.set_xlabel("p (processos MPI / slots locais do Spark)")
    eixo.grid(alpha=0.3)
    eixo.legend()


def grafico_tempo(tabela, pasta, nome):
    fig, ax = plt.subplots(figsize=(7, 4))

    for impl in ("mpi", "spark"):
        dados = [linha for linha in tabela if linha["impl"] == impl]
        ps = [linha["p"] for linha in dados]
        medias = [linha["media_s"] for linha in dados]
        desvios = [linha["desvio_s"] for linha in dados]

        ax.errorbar(ps, medias, yerr=desvios, fmt="o-", capsize=4, label=impl.upper())

    for linha in tabela:
        if linha["impl"] == "seq":
            ax.axhline(linha["media_s"], color="gray", linestyle="--", label="Sequencial")

    ax.set_title(f"Tempo: média +- desvio padrão — {nome}")
    ax.set_ylabel("Tempo do laço (s, escala log)")
    ax.set_yscale("log")
    eixo_paralelismo(ax, tabela)
    salvar(fig, pasta, f"tempo_{nome}.png")


def grafico_speedup(tabela, pasta, nome):
    fig, ax = plt.subplots(figsize=(7, 4))

    for impl in ("mpi", "spark"):
        dados = [linha for linha in tabela if linha["impl"] == impl]
        ps = [linha["p"] for linha in dados]
        ganhos = [linha["speedup"] for linha in dados]

        ax.plot(ps, ganhos, "o-", label=impl.upper())

    ideais = sorted({linha["p"] for linha in tabela if linha["p"] <= 16})
    ax.plot(ideais, ideais, "--", color="gray", label="Ideal até 16 núcleos")
    ax.set_title(f"Speedup — {nome}")
    ax.set_ylabel("T(1) / T(p)")
    ax.set_ylim(bottom=0)
    eixo_paralelismo(ax, tabela)
    salvar(fig, pasta, f"speedup_{nome}.png")


def grafico_eficiencia(tabela, pasta, nome):
    fig, ax = plt.subplots(figsize=(7, 4))

    for impl in ("mpi", "spark"):
        dados = [linha for linha in tabela if linha["impl"] == impl]
        ps = [linha["p"] for linha in dados]
        eficiencias = [100 * linha["eficiencia"] for linha in dados]

        ax.plot(ps, eficiencias, "o-", label=impl.upper())

    ax.axhline(100, color="gray", linestyle="--", label="Ideal")
    ax.set_title(f"Eficiência — {nome}")
    ax.set_ylabel("Eficiência (%)")
    ax.set_ylim(bottom=0)
    eixo_paralelismo(ax, tabela)
    salvar(fig, pasta, f"eficiencia_{nome}.png")


def grafico_repeticoes(grupos, pasta, nome):
    fig, eixos = plt.subplots(1, 3, figsize=(12, 4))

    for ax, impl in zip(eixos, ("seq", "mpi", "spark")):
        ps = sorted(p for programa, variante, p in grupos if programa == impl and variante == "base")
        maior_tempo = 0

        for i, p in enumerate(ps):
            tempos = grupos[(impl, "base", p)]["t"]
            maior_tempo = max(maior_tempo, max(tempos))

            for repeticao, tempo in enumerate(tempos):
                # Separa os pontos de uma mesma configuração para facilitar a leitura.
                x = i + 0.12 * (repeticao - (len(tempos) - 1) / 2)
                ax.scatter(x, tempo, color="tab:blue")

        ax.set_xticks(range(len(ps)), labels=ps)
        ax.set_xlim(-0.5, len(ps) - 0.5)
        ax.set_ylim(0, maior_tempo * 1.1)
        ax.set_title(impl.upper())
        ax.set_xlabel("p")
        ax.set_ylabel("Tempo do laço (s)")
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle(f"Repetições da versão base — {nome}")
    salvar(fig, pasta, f"repeticoes_{nome}.png")


def rotulos_alteracoes(alteracoes):
    return [f"{a['impl'].upper()} {a['variante']} (p={a['p']})" for a in alteracoes]


def grafico_ganho_alteracoes(alteracoes, pasta, nome):
    fig, ax = plt.subplots(figsize=(8, 0.4 * len(alteracoes) + 2))

    ganhos = [a["ganho"] for a in alteracoes]
    barras = ax.barh(range(len(alteracoes)), ganhos)

    ax.bar_label(barras, fmt="%.2fx", padding=4)
    ax.axvline(1, color="gray", linestyle="--")
    ax.set_yticks(range(len(alteracoes)), labels=rotulos_alteracoes(alteracoes))
    ax.invert_yaxis()
    ax.margins(x=0.15)
    ax.set_xlabel("T(base) / T(alteração): acima de 1 é mais rápido")
    ax.set_title(f"Ganho das alterações — {nome}")

    salvar(fig, pasta, f"alteracoes_{nome}.png")


def grafico_tempo_alteracoes(alteracoes, grupos, pasta, nome):
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(alteracoes) + 2))

    medias_base, medias_alteracao = [], []
    desvios_base, desvios_alteracao = [], []

    for a in alteracoes:
        base = grupos[(a["impl"], "base", a["p"])]["t"]
        variante = grupos[(a["impl"], a["variante"], a["p"])]["t"]

        medias_base.append(a["base_s"])
        medias_alteracao.append(a["variante_s"])

        desvios_base.append(stdev(base) if len(base) > 1 else 0)
        desvios_alteracao.append(stdev(variante) if len(variante) > 1 else 0)

    posicoes = range(len(alteracoes))

    ax.barh([i - 0.2 for i in posicoes], medias_base, height=0.35, xerr=desvios_base, capsize=3, label="Base")
    ax.barh([i + 0.2 for i in posicoes], medias_alteracao, height=0.35, xerr=desvios_alteracao, capsize=3, label="Alteração")
    ax.set_yticks(posicoes, labels=rotulos_alteracoes(alteracoes))
    ax.invert_yaxis()
    ax.set_xlabel("Tempo do laço (s): média +- desvio padrão")
    ax.set_title(f"Tempo antes e depois das alterações — {nome}")
    ax.legend()

    salvar(fig, pasta, f"tempos_alteracoes_{nome}.png")


def gerar_graficos(tabela, alteracoes, grupos, pasta, nome):
    Path(pasta).mkdir(parents=True, exist_ok=True)
    
    grafico_tempo(tabela, pasta, nome)
    grafico_speedup(tabela, pasta, nome)
    grafico_eficiencia(tabela, pasta, nome)
    grafico_repeticoes(grupos, pasta, nome)

    if alteracoes:
        grafico_ganho_alteracoes(alteracoes, pasta, nome)
        grafico_tempo_alteracoes(alteracoes, grupos, pasta, nome)

    print(f"Gráficos em {pasta}/")


if __name__ == "__main__":
    from analise import parse_args, le_execucoes, agrupa, resumo, alteracoes

    argumentos = parse_args()
    grupos = agrupa(le_execucoes(argumentos.pasta, argumentos.nome))

    gerar_graficos(resumo(grupos), alteracoes(grupos), grupos, argumentos.graficos, argumentos.nome)
