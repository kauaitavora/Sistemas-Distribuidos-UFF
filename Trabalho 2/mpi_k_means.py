import numpy
from mpi4py import MPI
from matplotlib import pyplot

from k_means_generator import generate_points

def k_means(points, k, seed, comm, rank, size):
    pass

def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    if rank == 0:
        pass

if __name__ == "__main__":
    main()