import time
import os
import docker

# -----------------------------
# DOCKER CLIENT
# -----------------------------
client = docker.from_env()

CONTAINER_NAME = "k3s-server"


# -----------------------------
# CHECK CLUSTER EXISTS
# -----------------------------
def get_container():
    try:
        return client.containers.get(CONTAINER_NAME)
    except:
        return None


def cluster_running():
    container = get_container()
    return container and container.status == "running"


# -----------------------------
# DELETE CONTAINER (SAFE RESET)
# -----------------------------
def delete_container():
    container = get_container()
    if container:
        print("⚠️ Removing existing k3s container (recreating with correct ports)...")
        container.remove(force=True)
        print("✅ Old container removed")


# -----------------------------
# CREATE CLUSTER (FIXED PORTS)
# -----------------------------
def create_cluster():
    print("\n☸️ Creating Kubernetes cluster (k3s)...\n")

    client.containers.run(
        "rancher/k3s:v1.30.0-k3s1",
        name=CONTAINER_NAME,
        privileged=True,
        detach=True,
        ports={
            "6443/tcp": 6443,     # Kubernetes API
            "32578/tcp": 32578, # ArgoCD UI (IMPORTANT)
            "30007/tcp": 30007,
            "30008/tcp": 30008,
        },
        restart_policy={"Name": "always"},
        command="server"
    )

    print("⏳ Waiting for cluster to start...")
    time.sleep(30)

    print("✅ Cluster container started")


# -----------------------------
# GENERATE KUBECONFIG
# -----------------------------
def generate_kubeconfig():
    print("\n⚙️ Generating kubeconfig...\n")

    container = client.containers.get(CONTAINER_NAME)

    result = container.exec_run("cat /etc/rancher/k3s/k3s.yaml")
    kubeconfig = result.output.decode()

    # DO NOT CHANGE
    kubeconfig = kubeconfig.replace("127.0.0.1", "127.0.0.1")

    kube_dir = os.path.expanduser("~/.kube")
    os.makedirs(kube_dir, exist_ok=True)

    config_path = os.path.join(kube_dir, "config")

    with open(config_path, "w") as f:
        f.write(kubeconfig)

    print("✅ kubeconfig generated")


# -----------------------------
# WAIT FOR READY
# -----------------------------
def wait_for_ready():
    print("\n⏳ Waiting for Kubernetes to be ready...\n")

    container = client.containers.get(CONTAINER_NAME)

    for i in range(30):
        output = container.exec_run("kubectl get nodes").output.decode()

        if "Ready" in output:
            print("✅ Kubernetes is Ready")
            return

        print(f"Waiting... {i+1}/30")
        time.sleep(5)

    raise Exception("❌ Kubernetes not ready")


# -----------------------------
# VALIDATE PORT MAPPING (IDEMPOTENT)
# -----------------------------
def ports_correct():
    container = get_container()
    if not container:
        return False

    container.reload()
    ports = container.attrs['NetworkSettings']['Ports']

    return (
        ports.get('32578/tcp') is not None and
        ports.get('6443/tcp') is not None and
        ports.get('30007/tcp') is not None and
        ports.get('30008/tcp') is not None
    )


# -----------------------------
# MAIN INSTALL FUNCTION
# -----------------------------
def install_kubernetes():
    print("\n🚀 Kubernetes Setup Started\n")

    container = get_container()

    if container:
        if not ports_correct():
            # recreate container if wrong config
            delete_container()
            create_cluster()
        else:
            print("✅ Kubernetes already running with correct config")
    else:
        create_cluster()

    generate_kubeconfig()
    wait_for_ready()

    print("\n✅ Kubernetes READY\n")
