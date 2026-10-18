import numpy
from matplotlib import pyplot

def generate_points(n_points, n_dimensions, k, seed):
    rng = numpy.random.default_rng(seed)

    # Gera, para cada cluster, uma média e um desvio-padrão por dimensão.
    locs = k * n_points * rng.random((k, n_dimensions)) - k // 2 * n_points
    scales = n_points // 5 * rng.random((k, n_dimensions)) + n_points // 5

    points = numpy.empty((n_points, n_dimensions))

    for i in range(len(points)):
        points[i] = rng.normal(locs[i % k], scales[i % k])

    return points

def main():
    points = generate_points(100000, 2, 5, 2)

    pyplot.scatter(points[:, 0], points[:, 1], s = 1)
    pyplot.show()

if __name__ == "__main__":
    main()