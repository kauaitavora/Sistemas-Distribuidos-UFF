import type { GoogleMap } from '@capacitor/google-maps';
import type { Position } from '@capacitor/geolocation';

export class MapControler {
    private readonly map: GoogleMap;
    private user_position: Position | null = null;
    private marker_ids = new Map<string, string>();

    constructor(map: GoogleMap) {
	this.map = map;
    }

    public async updateUserPosition(position: Position): Promise<void> {
	await this.updateMarkerPosition('user', position);
	this.user_position = position;
    }

    public async updateMarkerPosition(id: string, position: Position): Promise<void> {
	const previousMarkerId = this.marker_ids.get(id);

	if (previousMarkerId !== undefined) {
	    await this.map.removeMarker(previousMarkerId);
	    this.marker_ids.delete(id);
	}

	const markerId = await this.map.addMarker({
	    coordinate: {
		lat: position.coords.latitude,
		lng: position.coords.longitude,
	    },
	    title: id,
	});

	this.marker_ids.set(id, markerId);
    }

    public async removeAllMarkers(): Promise<void> {
	for (const [id, markerId] of [...this.marker_ids]) {
	    await this.map.removeMarker(markerId);

	    if (this.marker_ids.get(id) === markerId) {
		this.marker_ids.delete(id);
	    }
	}
    }
}
