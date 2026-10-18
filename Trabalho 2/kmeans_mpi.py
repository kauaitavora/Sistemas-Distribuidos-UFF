# K-Means de Lloyd com MPI (mpi4py): Scatterv + Bcast + Allreduce
import os
for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1") # 1 processo MPI = 1 núcleo (antes do import numpy!)

import argparse
import numpy as np
from mpi4py import MPI

def parse_args():
    p = argparse.ArgumentParser(description="K-Means MPI.")
    p.add_argument("--nome", required=True)
    p.add_argument("--pasta", default="dados")
    p.add_argument("--iter", type=int, default=20)
    return p.parse_args()

def divisao(N, p):
    """Linhas por processo e início de cada pedaço."""
    base, resto = divmod(N, p)
    linhas = np.array([base + (1 if r < resto else 0) for r in range(p)])
    inicios = np.concatenate(([0], np.cumsum(linhas)[:-1]))
    return linhas, inicios

def atribui(X, C, xx):
    """Idêntica ao kmeans_seq.py, mas aplicada só à fatia local."""
    cc = np.einsum("ij,ij->i", C, C)
    D = cc - 2.0 * (X @ C.T)
    rotulos = np.argmin(D, axis=1)
    return rotulos, D.min(axis=1) + xx

def somas_locais(X_local, rotulos, k):
    """Metade do 'atualiza' do sequencial: só soma e conta. A divisão fica para DEPOIS do Allreduce."""
    somas = np.zeros((k, X_local.shape[1]))
    np.add.at(somas, rotulos, X_local)
    contagens = np.bincount(rotulos, minlength=k).astype(np.float64) # float64: mesmo tipo do buffer MPI.DOUBLE
    return somas, contagens

def distribui(comm, pasta, nome):
    rank, p = comm.Get_rank(), comm.Get_size()
    if rank == 0: # só a raiz lê o disco
        X = np.load(f"{pasta}/X_{nome}.npy")
        C = np.load(f"{pasta}/C0_{nome}.npy")
        dims = np.array([X.shape[0], X.shape[1], C.shape[0]], dtype=np.int64)
    else:
        X = None
        dims = np.empty(3, dtype=np.int64)

    comm.Bcast(dims, root=0) # todos precisam de N, d, k para ALOCAR os buffers
    N, d, k = (int(v) for v in dims)
    if rank != 0:
        C = np.empty((k, d), dtype=np.float64)
    linhas, inicios = divisao(N, p)
    X_local = np.empty((linhas[rank], d), dtype=np.float64)

    comm.Barrier(); t0 = MPI.Wtime() # cronômetro da distribuição (leitura do disco fica fora)
    comm.Scatterv([X, linhas * d, inicios * d, MPI.DOUBLE], X_local, root=0) # N x d, em fatias
    comm.Bcast(C, root=0) # k x d, para todos
    comm.Barrier(); t_dist = MPI.Wtime() - t0
    return X_local, C, N, d, k, t_dist # X (inteira) sai de escopo aqui e a memória é liberada

def kmeans_mpi(comm, X_local, C, iters):
    k, d = C.shape
    somas_g = np.empty((k, d)) # buffers de recebimento do Allreduce: alocados UMA vez
    cont_g = np.empty(k)
    t_comp = t_comm = 0.0

    comm.Barrier(); t0 = MPI.Wtime() # Barrier: todos começam juntos
    xx = np.einsum("ij,ij->i", X_local, X_local) # dentro do cronômetro, como no sequencial
    for _ in range(iters):
        ta = MPI.Wtime()
        rotulos, dmin = atribui(X_local, C, xx)
        somas, cont = somas_locais(X_local, rotulos, k)
        tb = MPI.Wtime()
        comm.Allreduce(somas, somas_g, op=MPI.SUM) # k x d: soma das somas parciais -> TODOS recebem
        comm.Allreduce(cont, cont_g, op=MPI.SUM) # k: soma das contagens -> TODOS recebem
        tc = MPI.Wtime()
        ok = cont_g > 0 # mesma regra do cluster vazio do sequencial
        C[ok] = somas_g[ok] / cont_g[ok, None] # cada processo calcula os MESMOS centróides
        t_comp += (tb - ta) + (MPI.Wtime() - tc)
        t_comm += tc - tb
    comm.Barrier(); t_total = MPI.Wtime() - t0 # Barrier: espera o mais lento
    return C, dmin, t_total, t_comp, t_comm

def main():
    a = parse_args()
    comm = MPI.COMM_WORLD
    rank, p = comm.Get_rank(), comm.Get_size()

    X_local, C, N, d, k, t_dist = distribui(comm, a.pasta, a.nome)
    C, dmin, t_total, t_comp, t_comm = kmeans_mpi(comm, X_local, C, a.iter)

    # ---- daqui para baixo: FORA do tempo (só coleta e validação) ----
    tempos = np.array([t_dist, t_total, t_comp, t_comm])
    tmax = np.empty(4) if rank == 0 else None
    comm.Reduce(tempos, tmax, op=MPI.MAX, root=0) # tempo da execução = o do processo mais lento
    ine = np.array([dmin.sum()])
    ine_g = np.empty(1) if rank == 0 else None
    comm.Reduce(ine, ine_g, op=MPI.SUM, root=0) # inércia total da última iteração

    if rank == 0:
        np.save(f"{a.pasta}/C_mpi_{a.nome}_p{p}.npy", C)
        print(f"p={p} N={N} d={d} k={k} iter={a.iter} | dist={tmax[0]:.3f}s total={tmax[1]:.3f}s "
              f"comp={tmax[2]:.3f}s comm={tmax[3]:.3f}s | inércia final={ine_g[0]:.6f}")
        C_seq = np.load(f"{a.pasta}/C_seq_{a.nome}.npy")
        print(f"max |C_mpi - C_seq| = {np.abs(C - C_seq).max():.2e}")
        
        print(f"RESULTADO,mpi,{p},{N},{d},{k},{a.iter},{tmax[0]:.6f},{tmax[1]:.6f},"
              f"{tmax[2]:.6f},{tmax[3]:.6f},{ine_g[0]:.6f}")

if __name__ == "__main__":
    main()
