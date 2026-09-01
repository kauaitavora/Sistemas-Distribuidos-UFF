import csv
import matplotlib.pyplot as plt
import exp_grpc_cliente

rtts_por_tamanho = {}

exp_grpc_cliente.run()

with open('benchmark.log', 'r', newline='', encoding='utf-8') as file:
    reader = csv.reader(file, delimiter=',')

    next(reader)

    for linha in reader:
        tamanho = linha[1]
        rtts = float(linha[3])
    
        if tamanho not in rtts_por_tamanho:
            rtts_por_tamanho[tamanho] = []

        rtts_por_tamanho[tamanho].append(rtts)

    medias = {}

    for tamanho, rtts in rtts_por_tamanho.items():
        medias[tamanho] = sum(rtts) / len(rtts)

    plt.bar(medias.keys(), medias.values())

    plt.xlabel("Tamanho da mensagem (bytes)")
    plt.ylabel("RTT médio (ms)")
    plt.title("RTT médio por tamanho da mensagem")

    plt.savefig("grafico.png", dpi=400)
