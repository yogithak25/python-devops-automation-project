import docker

client = docker.from_env()


# -----------------------------
# CHECK CONTAINER EXISTS
# -----------------------------
def maven_container_exists():
    return any(c.name == "maven" for c in client.containers.list(all=True))


# -----------------------------
# INSTALL MAVEN (DOCKER)
# -----------------------------
def install_maven():

    print("\n📦 Setting up Maven (Docker-based)...\n")

    if maven_container_exists():
        container = client.containers.get("maven")

        if container.status != "running":
            print("🔄 Starting Maven container...")
            container.start()
        else:
            print("✅ Maven container already running")

        return

    print("🚀 Creating Maven container...")

    client.containers.run(
        "maven:3.9.9-eclipse-temurin-17",
        name="maven",
        command="tail -f /dev/null",  # keep container alive
        detach=True,
        tty=True
    )

    print("✅ Maven setup completed\n")
