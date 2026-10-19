# ola_mpi.py — teste do ambiente MPI (passo 0.3)
# Verifica: (1) vários processos sobem, (2) Bcast e (3) Allreduce com buffers numpy.
from mpi4py import MPI
import numpy as np
import socket

comm = MPI.COMM_WORLD # comunicador com todos os processos lançados pelo mpiexec
rank = comm.Get_rank() # identificador deste processo: 0, 1, ..., size-1
size = comm.Get_size() # total de processos

# --- Teste do Bcast: o rank 0 tem os dados, todos devem receber ---
# Todos alocam o buffer ANTES (np.empty), porque a versão maiúscula
# escreve direto nessa memória. Mesmo tamanho (3) e mesmo tipo (float64) em todos.
dados = np.empty(3, dtype=np.float64)
if rank == 0:
    dados[:] = [1.0, 2.0, 3.0] # só a raiz preenche
comm.Bcast(dados, root=0) # depois daqui, todos têm [1, 2, 3]

# --- Teste do Allreduce: cada um contribui com seu rank, todos recebem a soma ---
local = np.array([rank], dtype=np.float64) # contribuição deste processo
total = np.empty(1, dtype=np.float64) # buffer de recebimento
comm.Allreduce(local, total, op=MPI.SUM) # soma de todos, entregue a TODOS

esperado = size * (size - 1) // 2 # 0 + 1 + ... + (size-1)
print(f"rank {rank}/{size} em {socket.gethostname()}: "
      f"Bcast={dados}  Allreduce={total[0]:.0f} (esperado {esperado})",
      flush=True) # flush: sem ele, as saídas dos processos podem ficar presas no buffer
      