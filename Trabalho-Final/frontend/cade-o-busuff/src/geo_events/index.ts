import mqtt, { type MqttClient } from 'mqtt';

export class GeoEvents {
    static #broker_address = 'ws://localhost:9001/mqtt';
    #cliente: MqttClient;
    #rota: string;

    constructor(rota: string, listener: (rota: string, position_json: Buffer) => void) {
	this.#rota = rota;
	this.#cliente = mqtt.connect(GeoEvents.#broker_address);

	this.#cliente.on('message', listener);

	this.#cliente.on('error', (error) => {
	    console.error('Erro na conexão MQTT:', error);
	});

	this.#cliente.on('connect', () => {
	    console.log('Cliente conectado.');

	    this.#cliente.subscribe('rotas/#', (err) => {
		if (err) {
		    console.log('Erro ao assinar os tópicos!');
		}
	    });
	});
    }

    getRota(): string {
	return this.#rota;
    }

    sendPosition(position_json: string): void {
	this.#cliente.publish('rotas/'.concat(this.#rota), position_json);
    }

    stop(): void {
	this.#cliente.end();
    }
}
