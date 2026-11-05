import mqtt from "https://cdn.jsdelivr.net/npm/mqtt@5.16/+esm"

export function mqtt_motorista_connect(rota) {
    const cliente = mqtt.connect("ws://localhost:8000/mqtt");

    cliente.on("connect", () => {
        console.log("Motorista conectado.");
        
        cliente.subscribe("rotas/".concat(rota), (err) => {
            if (!err) {
                cliente.publish("rotas/".concat(rota), "Motorista conectado.");
            } else {
                console.log("Erro ao assinar o tópico!");
            }
        });
    });
        
    return cliente;
}

export function mqtt_motorista_publish(cliente, rota, localizacao) {
    cliente.publish("rotas/".concat(rota), localizacao);
}

export function mqtt_aluno_connect() {
    const cliente = mqtt.connect("ws://localhost:8000/mqtt");

    cliente.on("connect", () => {
        console.log("Aluno conectado.");
        
        cliente.subscribe("rotas/#", (err) => {
            if (!err) {
                cliente.publish("rotas/#", "Aluno conectado.");
            } else {
                console.log("Erro ao assinar os tópicos!");
            }
        });
    });
        
    return cliente;
}

export function mqtt_aluno_receive(cliente) {
    cliente.on("message", (topic, message) => {
        console.log(message.toString());
        return message;
    });
}
