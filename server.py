from flask import Flask, render_template, redirect, url_for, jsonify
import paramiko
import json

app = Flask(__name__)
remote_hosts = {
        "IPV4": {
            "credentials": ("username", "password"),
            "action": {"name": "Name of the action", "url": "shutdown now"},
        },
        "192.168.x.x": {
            "credentials": ("username", "password"),
        },
        # Add more hosts as needed
    }
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

if __name__ == "__main__":
    app.run(debug=True)
