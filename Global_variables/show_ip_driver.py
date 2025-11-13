from flask import Flask, jsonify

app = Flask(__name__)

def get_global_env():
    """
    Reads the /etc/environment file and extracts
    the values of IP and RPI_NAME (if present).
    """
    env_data = {"IP": "not_set", "RPI_NAME": "not_set"}
    try:
        with open("/etc/environment", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("IP="):
                    env_data["IP"] = line.split("=")[1].replace('"', '')
                elif line.startswith("RPI_NAME="):
                    env_data["RPI_NAME"] = line.split("=")[1].replace('"', '')
    except Exception as e:
        env_data = {"error": str(e)}
    return env_data


@app.route('/get_rpi_details', methods=['GET'])
def show_rpi_details():
    """
    Returns IP and RPI_NAME in JSON format.
    """
    return jsonify(get_global_env())


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1848, debug=True)