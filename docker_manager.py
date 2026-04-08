import docker
import time
import socket
from config.env_loader import get_env

client = docker.from_env()
config = get_env()


# -----------------------------
# CHECK CONTAINER EXISTS
# -----------------------------
def container_exists(name):
    return any(c.name == name for c in client.containers.list(all=True))


# -----------------------------
# WAIT FOR SERVICE
# -----------------------------
def wait_for_service(port, name):

    print(f"\n⏳ Waiting for {name}...\n")

    for i in range(30):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=2)
            s.close()
            print(f"✅ {name} ready")
            return
        except:
            print(f"Waiting... ({i+1}/30)")
            time.sleep(5)

    raise Exception(f"❌ {name} not reachable")


# -----------------------------
# JENKINS 
# -----------------------------
def ensure_jenkins():

    name = "jenkins"

    if container_exists(name):
        container = client.containers.get(name)

        # Check docker.sock mount
        mounts = container.attrs.get("Mounts", [])
        docker_sock_mounted = any(
            m.get("Source") == "/var/run/docker.sock"
            for m in mounts
        )

        if not docker_sock_mounted:
            print("⚠️ Jenkins exists but missing docker.sock → Recreating...")
            container.remove(force=True)
        else:
            if container.status != "running":
                print("🔄 Starting Jenkins...")
                container.start()
            else:
                print("✅ Jenkins already running")

            return container

    
    print("🚀 Creating Jenkins (with Docker access)...")

    container = client.containers.run(
        "jenkins/jenkins:lts",
        name="jenkins",
        detach=True,
        ports={"8080/tcp": 8080},
        volumes={
            "/var/run/docker.sock": {
                "bind": "/var/run/docker.sock",
                "mode": "rw"
            },
            "/home/ubuntu/jenkins_home": {   # 🔥 IMPORTANT FIX
                "bind": "/var/jenkins_home",
                "mode": "rw"
            }
        },
        user="root"
    )
    return container


# -----------------------------
# INSTALL DOCKER CLI IN JENKINS
# -----------------------------
def install_docker_cli():

    container = client.containers.get("jenkins")

    print("\n🐳 Installing Docker CLI inside Jenkins...\n")

    container.exec_run("apt-get update")
    container.exec_run("apt-get install -y docker.io")

    print("✅ Docker CLI installed in Jenkins")


# -----------------------------
# GENERIC CONTAINER CREATION
# -----------------------------
def ensure_container(name, image, ports):

    if container_exists(name):
        container = client.containers.get(name)

        if container.status != "running":
            print(f"🔄 Starting {name}...")
            container.start()
        else:
            print(f"✅ {name} already running")

        return container

    print(f"🚀 Creating {name}...")

    return client.containers.run(
        image,
        name=name,
        detach=True,
        ports=ports
    )


# -----------------------------
# SETUP INFRA
# -----------------------------
def setup_infra():

    print("\n🔥 Starting Docker Infra...\n")

    # Jenkins (special)
    ensure_jenkins()

    # Install docker CLI (only once effectively)
    install_docker_cli()

    # Other tools
    ensure_container("sonarqube", "sonarqube:lts", {"9000/tcp": 9000})
    ensure_container("nexus", "sonatype/nexus3", {"8081/tcp": 8081})

    # Wait for services
    wait_for_service(8080, "Jenkins")
    wait_for_service(9000, "SonarQube")
    wait_for_service(8081, "Nexus")

    # URLs
    print("\n🌐 ACCESS YOUR TOOLS:\n")
    print(f"Jenkins   → {config['JENKINS_URL']}")
    print(f"SonarQube → {config['SONAR_URL']}")
    print(f"Nexus     → {config['NEXUS_URL']}")

    print("\n✅ Infra Ready\n")
