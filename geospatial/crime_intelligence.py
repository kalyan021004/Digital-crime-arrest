"""
PHASE 10: Geospatial Crime Intelligence
Reads incidents directly from MongoDB.
"""

from collections import defaultdict

# BUGFIX: this module used to open its OWN MongoClient and read from a
# collection named "incidents", while agents/nodes.py wrote alerts to
# "incident_reports". The names never matched, so every hotspot and heatmap
# query silently returned an empty list no matter how many incidents existed.
#
# It also bypassed db/mongo.py's connection handling, so it would crash on an
# unreachable database instead of degrading gracefully.
#
# Both problems go away by reusing the single shared collection.
from db.mongo import incident_collection


class GeoCrimeIntelligence:

    def __init__(self):
        self.collection = incident_collection

    def add_incident(self, session_id, latitude, longitude, city,
                     confidence, risk_categories):
        """
        Record (or update) an incident's location for hotspot aggregation.

        server/api.py already called this method -- it just never existed,
        raising AttributeError on every alert-level session that carried
        location data. Upserts on session_id so replaying a session doesn't
        double-count it as two separate incidents in the same city.
        """
        self.collection.update_one(
            {"session_id": session_id},
            {"$set": {
                "session_id": session_id,
                "city": city,
                "latitude": latitude,
                "longitude": longitude,
                "confidence": confidence,
                "risk_categories": risk_categories,
            }},
            upsert=True,
        )

    def city_hotspots(self, min_incidents: int = 2):

        incidents = list(self.collection.find())

        by_city = defaultdict(list)

        for incident in incidents:

            city = incident.get("city")

            if city:
                by_city[city].append(incident)

        hotspots = []

        for city, incs in by_city.items():

            if len(incs) < min_incidents:
                continue

            avg_conf = (
                sum(i.get("confidence", 0) for i in incs)
                / len(incs)
            )

            hotspots.append({
                "city": city,
                "incident_count": len(incs),
                "avg_confidence": round(avg_conf, 2),
                "centroid": self._centroid(incs)
            })

        hotspots.sort(
            key=lambda x: x["incident_count"],
            reverse=True
        )

        return hotspots

    def grid_heatmap(self, cell_size_deg=0.05):

        incidents = list(self.collection.find())

        cells = defaultdict(list)

        for incident in incidents:

            lat = incident.get("latitude")
            lon = incident.get("longitude")

            # Location is optional (a WhatsApp check has no coordinates), so
            # the key may be PRESENT but None. The old `"latitude" not in
            # incident` test passed in that case and then crashed on
            # round(None / cell_size).
            if lat is None or lon is None:
                continue

            cell = (
                round(lat / cell_size_deg) * cell_size_deg,
                round(lon / cell_size_deg) * cell_size_deg,
            )

            cells[cell].append(incident)

        heatmap = []

        for (lat, lon), incs in cells.items():

            heatmap.append({

                "cell_center": {
                    "lat": lat,
                    "lon": lon
                },

                "incident_count": len(incs),

                "session_ids": [
                    i["session_id"]
                    for i in incs
                ]

            })

        heatmap.sort(
            key=lambda x: x["incident_count"],
            reverse=True
        )

        return heatmap

    @staticmethod
    def _centroid(incidents):
        """
        Mean position of the incidents that actually have coordinates.

        Skips incidents with missing or None lat/lon rather than raising --
        a city can legitimately have incidents reported without location
        (e.g. a WhatsApp message check), and one of those should not blow up
        the whole hotspot report.
        """
        located = [
            i for i in incidents
            if i.get("latitude") is not None and i.get("longitude") is not None
        ]

        if not located:
            return None

        lat = sum(i["latitude"] for i in located) / len(located)
        lon = sum(i["longitude"] for i in located) / len(located)

        return {
            "lat": round(lat, 4),
            "lon": round(lon, 4),
        }


geo = GeoCrimeIntelligence()


if __name__ == "__main__":

    import json

    print("\nCity Hotspots\n")

    print(
        json.dumps(
            geo.city_hotspots(),
            indent=4
        )
    )

    print("\nGrid Heatmap\n")

    print(
        json.dumps(
            geo.grid_heatmap(),
            indent=4
        )
    )