from flask import Flask, jsonify

app = Flask(__name__)

def get_global_ip():
    # Read /etc/environment dynamically each time
    ip_value = "not_set"
    try:
        with open("/etc/environment", "r") as f:
            for line in f:
                if line.strip().startswith("IP="):
                    ip_value = line.strip().split("=")[1].replace('"', '')
                    break
    except Exception as e:
        ip_value = f"error: {e}"
    return {"IP": ip_value}

@app.route('/get_global_ip', methods=['GET'])
def show_global_ip():
    return jsonify(get_global_ip())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1848, debug=True)