# Gera um conjunto de pontos de dados sintético X (N pontos x d dimensões)
# e os centroides iniciais C0 (k centroides x d dimensões).
# As três implementações (sequencial, MPI e Spark) leem os mesmos arquivos.

import argparse, json, os, time
import numpy as np

def parse_args():
    p = argparse.ArgumentParser(description=
        "Gera um conjunto de pontos de dados sintético X (N pontos x d dimensões)"
        "e os centroides iniciais C0 (k centroides x d dimensões)."
    )

    p.add_argument("--N", type=int, default=400_000, help="nº de pontos")
    p.add_argument("--d", type=int, default=256, help="número de dimensões de cada ponto")
    p.add_argument("--k", type=int, default=64, help="nº de clusters")
    p.add_argument("--seed", type=int, default=42, help="semente para geração de números pseudoaleatórios")
    p.add_argument("--nome", default=None, help="sufixo dos arquivos (padrão: sint_<N>)")
    p.add_argument("--saida", default="dados", help="pasta de saída")
    return p.parse_args()

def gera_dados_sinteticos(N, d, k, seed):
    rng = np.random.default_rng(seed) # gerador com semente: reprodutível

    # Coordenadas dos centros dos k clusters: poucos termos com peso alto (^4 concentra).
    centroides = rng.random((k, d)) ** 4

    # Lista aleatória de índices: indica a qual cluster pertence cada ponto.
    y = rng.integers(0, k, N)
    
    ruido = 0.5 * rng.random((N, d)) ** 4 # ruído não negativo
    X = centroides[y] + ruido # ponto de dados = centro do cluster + ruído
    X[:] /= np.linalg.norm(X, axis=1, keepdims=True) # norma 1, igual ao real

    return X, y

def centroides_iniciais(X, k, seed):
    # Escolhe k pontos distintos ao acaso como centroides iniciais.
    # seed+1: fluxo aleatório independente do usado para gerar os dados.
    rng = np.random.default_rng(seed + 1)
    idx = np.sort(rng.choice(X.shape[0], size=k, replace=False))
    return X[idx] # indexação por lista já devolve uma cópia contígua k x d

def main():
    a = parse_args()
    os.makedirs(a.saida, exist_ok=True)
    t0 = time.perf_counter()

    X, y = gera_dados_sinteticos(a.N, a.d, a.k, a.seed)
    C0 = centroides_iniciais(X, a.k, a.seed)

    nome = a.nome or f"sint_{a.N}"
    base = os.path.join(a.saida, f"{{}}_{nome}.npy")
    
    np.save(base.format("X"), X)
    np.save(base.format("C0"), C0)
    np.save(base.format("y"), y)

    # Metadados: registram como os dados foram gerados 
    meta = dict(
        N=X.shape[0], d=X.shape[1], k=a.k, seed=a.seed,
        dtype=str(X.dtype), numpy=np.__version__
    )

    with open(os.path.join(a.saida, f"meta_{nome}.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(
        f"X: {X.shape} {X.dtype} | contígua = {X.flags['C_CONTIGUOUS']} "
        f"| tamanho = {X.nbytes/1e6:.1f} MB | soma(X) = {X.sum():.6f}\n"
        f"C0: {C0.shape} | soma(C0) = {C0.sum():.6f} | tempo = {time.perf_counter()-t0:.1f} s"
    )

if __name__ == "__main__":
    main()
