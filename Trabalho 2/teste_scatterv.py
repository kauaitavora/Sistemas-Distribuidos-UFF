# Testa a divisão de linhas com Scatterv ANTES de usar no K-Means
from mpi4py import MPI
import numpy as np

def divisao(N, p):
    """Quantas linhas cada processo recebe e onde cada pedaço começa (em LINHAS).
    Os primeiros N % p processos recebem 1 linha a mais: diferença máxima de 1 linha."""
    base, resto = divmod(N, p)
    linhas = np.array([base + (1 if r < resto else 0) for r in range(p)])
    inicios = np.concatenate(([0], np.cumsum(linhas)[:-1])) # começo = soma dos tamanhos anteriores
    return linhas, inicios

comm = MPI.COMM_WORLD
rank, p = comm.Get_rank(), comm.Get_size()
N, d = 10, 3 # N de propósito NÃO divisível por 3

linhas, inicios = divisao(N, p) # todos calculam: é barato e evita comunicação

if rank == 0:
    # X[i] = [i, i, i]: cada linha "carrega" o próprio número, fica fácil conferir quem recebeu o quê
    X = np.repeat(np.arange(N, dtype=np.float64), d).reshape(N, d)
else:
    X = None # só a raiz tem a matriz inteira

X_local = np.empty((linhas[rank], d), dtype=np.float64) # cada um aloca SÓ o seu pedaço

# counts e displs em ELEMENTOS (linhas x d), não em linhas
comm.Scatterv([X, linhas * d, inicios * d, MPI.DOUBLE], X_local, root=0)

print(f"rank {rank}: {linhas[rank]} linhas, começando na {inicios[rank]} -> "
      f"recebi as linhas {X_local[:, 0].astype(int).tolist()}", flush=True)
    