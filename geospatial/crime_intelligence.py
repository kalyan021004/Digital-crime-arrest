"""
PHASE 10: Geospatial Crime Intelligence
Reads incidents directly from MongoDB.
"""

from collections import defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.getenv("MONGODB_URI"))

db = client["digital_arrest_shield"]
incident_collection = db["incidents"]


class GeoCrimeIntelligence:

    def __init__(self):
        self.collection = incident_collection

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

            if "latitude" not in incident or "longitude" not in incident:
                continue

            lat = incident["latitude"]
            lon = incident["longitude"]

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

        if not incidents:
            return None

        lat = sum(
            i["latitude"]
            for i in incidents
        ) / len(incidents)

        lon = sum(
            i["longitude"]
            for i in incidents
        ) / len(incidents)

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