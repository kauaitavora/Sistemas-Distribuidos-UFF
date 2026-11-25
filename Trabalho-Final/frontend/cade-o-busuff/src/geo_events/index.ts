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
	    this.subscribeRoute(this.#rota)
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

    changeRoute(routeId: string): void {
	this.unsubscribeRoute(this.#rota);
	this.subscribeRoute(routeId);
	this.#rota = routeId
    }

    unsubscribeRoute(routeId: string): void {
	const topic = `rotas/${routeId}/+`;

	this.#cliente.unsubscribe(topic, (err) => {
	    if (err) {
		console.error('Erro ao desassinar o tópico:', err);
		return;
	    }
	    console.log('Desassinado de:', topic);
	});
    }

    subscribeRoute(routeId: string): void {
	const topic = `rotas/${routeId}/+`;

	this.#cliente.subscribe(topic, (err) => {
	    if (err) {
		console.log('Erro ao assinar os tópicos!', err);
		return;
	    }
	    console.log('Assinado em:', topic);
	});
    }

    stop(): void {
	  this.#cliente.end();
    }
}
