# K-Means de Lloyd em PySpark (RDD): cache + broadcast + mapPartitions + treeAggregate
import os
for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1") # vale só para o DRIVER; para os executores, ver SparkConf no main

import argparse, time
import numpy as np
from pyspark import SparkConf, SparkContext

def parse_args():
    p = argparse.ArgumentParser(description="K-Means Spark (RDD).")
    p.add_argument("--nome", required=True)
    p.add_argument("--pasta", default="dados")
    p.add_argument("--iter", type=int, default=20)

    p.add_argument("--particoes", type=int, default=0,
                   help="nº de partições (0 = nº de núcleos do Spark, defaultParallelism)")
    
    # Alteração Spark (b): sem cache, cada iteração refaz a leitura dos blocos e o cálculo de Σ(xi²)
    p.add_argument("--sem-cache", action="store_true", help="não chama cache() no RDD dos dados")

    p.add_argument("--somas", choices=["add_at", "onehot"], default="add_at",
                   help="mesma troca da alteração MPI (c), para comparar o efeito nos dois modelos")
    
    return p.parse_args()

def divisao(N, p):
    """Linhas por processo e início de cada pedaço."""
    base, resto = divmod(N, p)
    linhas = np.array([base + (1 if r < resto else 0) for r in range(p)])
    inicios = np.concatenate(([0], np.cumsum(linhas)[:-1]))
    return linhas, inicios

def atribui(X, C, xx):
    """Idêntica ao kmeans_seq.py, mas aplicada só à fatia local."""
    cc = np.sum(C * C, axis=1) # Σ(ci²) de cada centroide: C é pequeno (k x d), então a legibilidade vale mais
    D = cc - 2.0 * (X @ C.T)
    rotulos = np.argmin(D, axis=1)
    return rotulos, D.min(axis=1) + xx

def somas_locais(X_local, rotulos, k, modo="add_at"):
    """Metade do 'atualiza' do sequencial: só soma e conta. A divisão fica para DEPOIS do Allreduce."""
    if modo == "add_at":
        somas = np.zeros((k, X_local.shape[1]))
        np.add.at(somas, rotulos, X_local) # soma linha a linha: laço interno do numpy, sem BLAS
    else:
        # (M.T @ X)[j] = soma dos pontos do cluster j, com M one-hot (N_local x k): BLAS
        M = np.zeros((X_local.shape[0], k))
        M[np.arange(X_local.shape[0]), rotulos] = 1.0
        somas = M.T @ X_local
    
    contagens = np.bincount(rotulos, minlength=k).astype(np.float64) # float64: mesmo tipo do buffer MPI.DOUBLE
    return somas, contagens

def distribui(sc, caminho, P, usa_cache=True):
    N, d = np.load(caminho, mmap_mode="r").shape # lê só o cabeçalho do .npy (N e d)
    linhas, inicios = divisao(N, P) # mesma divisão por linhas do MPI

    def carrega_bloco(i):
        # Roda NO EXECUTOR: mapeia o arquivo e copia para a memória só as linhas do bloco i
        Xm = np.load(caminho, mmap_mode="r")
        Xb = np.array(Xm[inicios[i]:inicios[i] + linhas[i]], dtype=np.float64)
        return Xb, np.sum(Xb * Xb, axis=1) # guarda também Σ(xi²), que não muda entre iterações

    t0 = time.perf_counter()

    # P elementos (0..P-1) em P partições: cada partição recebe exatamente 1 índice -> 1 bloco
    rdd = sc.parallelize(range(P), P).map(carrega_bloco)

    if usa_cache:
        rdd = rdd.cache() # guarda os blocos na memória: as 20 iterações reaproveitam

    rdd.count() # AÇÃO: força a carga (e, com cache, preenche o cache)

    t_dist = time.perf_counter() - t0

    return rdd, N, d, t_dist

def kmeans_spark(sc, rdd, C0, iters, modo_somas="add_at"):
    k, d = C0.shape
    C = C0.copy()

    zero = (np.zeros((k, d)), np.zeros(k), 0.0) # (somas, contagens, inércia)
    soma3 = lambda a, b: (a[0] + b[0], a[1] + b[1], a[2] + b[2]) # cria arrays NOVOS, não altera a/b
    inercias = []

    t0 = time.perf_counter()

    for _ in range(iters):
        bc = sc.broadcast(C) # C (k x d) enviado UMA vez a cada executor

        def parcial(blocos): # roda no executor, uma vez por partição
            Cb = bc.value

            for Xb, xxb in blocos: # há exatamente 1 bloco por partição
                rotulos, dmin = atribui(Xb, Cb, xxb)
                somas, contagens = somas_locais(Xb, rotulos, k, modo_somas)
                yield somas, contagens, dmin.sum()

        # treeAggregate: combina os resultados parciais em árvore até o driver
        somas, contagens, iner = rdd.mapPartitions(parcial).treeAggregate(zero, soma3, soma3)

        inercias.append(iner)

        bc.unpersist() # descarta a cópia antiga de C nos executores

        C = C.copy() # novo array para os novos centroides
        ok = contagens > 0 # mesma regra do cluster vazio
        C[ok] = somas[ok] / contagens[ok, None]
    
    t_total = time.perf_counter() - t0

    return C, inercias, t_total

def main():
    a = parse_args()

    conf = SparkConf().setAppName(f"kmeans_spark_{a.nome}")

    # Threads da BLAS nos EXECUTORES: o os.environ do driver não chega até eles
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        conf.setExecutorEnv(var, "1")

    sc = SparkContext(conf=conf)
    sc.setLogLevel("WARN")

    caminho = os.path.abspath(f"{a.pasta}/X_{a.nome}.npy") # caminho ABSOLUTO: o executor roda em outra pasta
    
    P = a.particoes or sc.defaultParallelism # partições = núcleos
    C0 = np.load(f"{a.pasta}/C0_{a.nome}.npy")

    rdd, N, d, t_dist = distribui(sc, caminho, P, usa_cache=not a.sem_cache)
    C, inercias, t_total = kmeans_spark(sc, rdd, C0, a.iter, a.somas)
    
    np.save(f"{a.pasta}/C_spark_{a.nome}_P{P}.npy", C)

    # ---- validação ----
    C_seq = np.load(f"{a.pasta}/C_seq_{a.nome}.npy")

    monotona = all(b <= x * (1 + 1e-12) for x, b in zip(inercias, inercias[1:]))
    k = C0.shape[0]

    print(f"master={sc.master} partições={P} cache={not a.sem_cache} somas={a.somas}")

    print(f"N={N} d={d} k={k} iter={a.iter} | dist={t_dist:.3f}s total={t_total:.3f}s | "
          f"inércia final={inercias[-1]:.6f} | não crescente: {monotona}")
    
    print(f"max |C_spark - C_seq| = {np.abs(C - C_seq).max():.2e}")

    # mesmas colunas do MPI; comp/comm ficam vazios (o Spark não expõe essa separação no driver)
    print(f"RESULTADO,spark,{P},{N},{d},{k},{a.iter},{t_dist:.6f},{t_total:.6f},,,{inercias[-1]:.6f}")

    sc.stop()

if __name__ == "__main__":
    main()
