import { Position } from '@capacitor/geolocation';
import mqtt, { MqttClient } from 'mqtt'

/* Lógica para receber e enviar eventos de localização utilizando MQTT.
   Ao ser instanciada, a classe GeoEvents faz tudo o que é necessário para receber
   eventos de localização:
   - Abre uma conexão com o broker MQTT, criando um cliente MQTT;
   - Inscreve o cliente em todas as rotas (que são tópicos MQTT);
   - Define que a função listener deve ser executada toda vez que um evento de
     geolocalização chegar. A "rota" é o tópico do evento, e a "position_json"
     é o payload do evento.
   A função listener deve ser fornecida na instanciação de GeoEvents. Ela pode,
   por exemplo, ser uma função que atualiza um componente da UI com base na rota
   e na geolocalização.
*/

export class GeoEvents {
    static #broker_address = "ws://localhost:8000/mqtt";
    #cliente: MqttClient;
    #rota: string;

    constructor(rota: string, listener: (rota: string, position_json: Buffer) => void) {
        this.#cliente = mqtt.connect(GeoEvents.#broker_address);

        this.#cliente.on("connect", () => {
            console.log("Cliente conectado.");
            
            this.#cliente.subscribe("rotas/#", (err) => {
                if (!err) {
                    this.#cliente.on("message", listener);
                } else {
                    console.log("Erro ao assinar os tópicos!");
                }
            });
        });

        this.#rota = rota;
    }

    getRota() {
        return this.#rota;
    }

    sendPosition(position_json: string) {
        this.#cliente.publish("rotas/".concat(this.#rota), position_json);
    }

    stop() {
        this.#cliente.end();
    }
}
