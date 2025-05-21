from flask import Flask, request, jsonify
from priority_logic import EmergencyManager, TrafficSignalController
import threading

app = Flask(__name__)
manager = EmergencyManager()
controller = TrafficSignalController(manager)
# Start the signal controller in the background
threading.Thread(target=controller.start, daemon=True).start()

@app.route('/emergency', methods=['POST'])
def handle_emergency():
    data = request.get_json()
    ambulance_id = data.get("ambulance_id")
    severity = data.get("severity")

    if not ambulance_id or severity is None:
        return jsonify({"error": "Missing data"}), 400

    manager.add_emergency(ambulance_id, int(severity))
    return jsonify({"status": "received"}), 200

if __name__ == '__main__':
    app.run(port=5001)
