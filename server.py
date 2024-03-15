from flask import Flask, render_template, redirect, url_for, jsonify,request
import paramiko
import json
import webbrowser
app = Flask(__name__)
def read_remote_hosts_from_json():
    try:
        with open("remote_hosts.json", "r") as file:
            data = json.load(file)
            return data.get("hosts", {})
    except Exception as e:
        print(f"Error reading remote_hosts.json: {e}")
        return {}
def write_remote_hosts_to_json(remote_hosts):
    try:
        with open("remote_hosts.json", "w") as file:
            json.dump({"hosts": remote_hosts}, file, indent=2)
    except Exception as e:
        print(f"Error writing remote_hosts.json: {e}")
remote_hosts = read_remote_hosts_from_json()
def run_addon_script(remote_host, username, password, script_url, port=22):
    try:
        # Establish an SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(remote_host, port=port, username=username, password=password)
        # Run the addon script remotely
        command = f'{script_url}'
        stdin, stdout, stderr = ssh.exec_command(command)

        ssh.close()
        return True

    except Exception as e:
        print(f"Error running addon script: {e}")
        return False
def get_running_containers(remote_hosts):
    all_containers = {}

    for remote_host, config in remote_hosts.items():
        username, password = config["credentials"]
        try:
            # Establish an SSH connection
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(remote_host, port=22, username=username, password=password)

            # Run the Docker command remotely
            stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}"')

            # Process the output
            container_info = []
            for line in stdout.readlines():
                container_id, container_name, container_image, container_status = line.strip().split('|')
                container_info.append({
                    "id": container_id,
                    "name": container_name,
                    "image": container_image,
                    "status": container_status,
                })

            all_containers[remote_host] = {"containers": container_info, "action": config.get("action")}
            ssh.close()

        except Exception as e:
            all_containers[remote_host] = {"error": f"Error connecting to the remote host: {e}", "action": config.get("action")}

    return all_containers

def restart_container(remote_host, username, password, container_id, port=22):
    try:
        # Establish an SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(remote_host, port=port, username=username, password=password)

        # Run the Docker restart command remotely
        command = f'docker restart {container_id}'
        stdin, stdout, stderr = ssh.exec_command(command)

        ssh.close()
        return True

    except Exception as e:
        print(f"Error restarting container: {e}")
        return False

@app.route('/')
def index():
    all_containers = get_running_containers(remote_hosts)
    return render_template('index_ssh_multi.html', all_containers=all_containers)

@app.route('/restart/<remote_host>/<container_id>')
def restart(remote_host, container_id):
    config = remote_hosts.get(remote_host)
    if not config:
        return f"Unknown remote host: {remote_host}"

    username, password = config["credentials"]
    success = restart_container(remote_host, username, password, container_id)

    if success:
        return redirect(url_for('index'))
    else:
        return "Failed to restart the container."

@app.route('/run-action/<remote_host>')
def run_action(remote_host):
    config = remote_hosts.get(remote_host)
    if not config:
        return jsonify({"error": f"Unknown remote host: {remote_host}"})

    username, password = config["credentials"]
    action = config.get("action")

    if not action:
        return jsonify({"error": f"No action configured for remote host: {remote_host}"})

    action_name = action.get("name")
    action_url = action.get("url")

    success = run_addon_script(remote_host, username, password, action_url)

    if success:
        return jsonify({"message": f"Action '{action_name}' executed successfully on {remote_host}"})
    else:
        return jsonify({"error": f"Failed to execute action '{action_name}' on {remote_host}"})
@app.route('/add-host', methods=['POST'])
def add_host():
    global remote_hosts
    try:
        data = request.get_json()
        new_host = data.get('host')
        credentials = data.get('credentials')
        action = data.get('action')

        remote_hosts[new_host] = {
            'credentials': credentials,
            'action': action
        }

        with open("remote_hosts.json", "w") as file:
            json.dump({'hosts': remote_hosts}, file, indent=4)
        remote_hosts = read_remote_hosts_from_json()
        return jsonify({"message": f"Host '{new_host}' added successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to add host: {str(e)}"})

def delete_host(remote_host):
    try:
        del remote_hosts[remote_host]
        write_remote_hosts_to_json(remote_hosts)
        return "Host deleted successfully"
    except KeyError:
        return f"Host {remote_host} not found"

@app.route('/delete-host/<remote_host>')
def delete_host_route(remote_host):
    result = delete_host(remote_host)
    return jsonify({"message": result})

if __name__ == "__main__":
    webbrowser.open_new_tab('http://127.0.0.1:50000')
    app.run(debug=True,port=50000,host="127.0.0.1")
