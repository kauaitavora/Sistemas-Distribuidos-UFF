import mqtt, { type MqttClient } from 'mqtt';

export class GeoEvents {
    static #broker_address = 'ws://localhost:8000/mqtt';
    #cliente: MqttClient;
    #rota: string;
	#veiculo_id: string;

    constructor(
	  rota: string, veiculo_id: string,
	  listener: (rota: string, position_json: Buffer) => void
	) {
	  this.#rota = rota;

	  this.#veiculo_id = veiculo_id;

	  this.#cliente = mqtt.connect(GeoEvents.#broker_address, {
		keepalive: 15,

		will: {
		  topic: "status/".concat(veiculo_id),
          payload: JSON.stringify({ veiculo_id: veiculo_id, estado: "offline" }),
          qos: 1,
          retain: true
		}
	  });

	  this.#cliente.on('message', listener);

	  this.#cliente.on('error', (error) => {
	    console.error('Erro na conexão MQTT:', error);
	  });

	  this.#cliente.on('connect', () => {
	    console.log('Cliente conectado.');

	    this.#cliente.subscribe('rotas/+/+', (err) => {
		  if (err) {
		    console.log('Erro ao assinar os tópicos!');
		  }
	    });
	  });
    }

    getRota(): string {
	  return this.#rota;
    }

	getVeiculoID() {
	  return this.#veiculo_id;
	}

    sendPosition(position_json: string): void {
	  this.#cliente.publish(
		'rotas/' + this.#rota + '/' + this.#veiculo_id,
		position_json, { qos: 1, retain: true }
	  );
    }

    stop(): void {
	  this.#cliente.end();
    }
}
