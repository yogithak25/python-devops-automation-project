import docker

client = docker.from_env()


# -----------------------------
# CHECK TRIVY IMAGE EXISTS
# -----------------------------
def trivy_image_exists():

    images = client.images.list()

    return any("aquasec/trivy" in img.tags[0] for img in images if img.tags)


# -----------------------------
# PULL TRIVY IMAGE (IDEMPOTENT)
# -----------------------------
def setup_trivy():

    print("\n🔐 Setting up Trivy...\n")

    try:
        images = client.images.list()
        for img in images:
            if any("aquasec/trivy" in tag for tag in img.tags):
                print("✅ Trivy image already present")
                return
    except:
        pass

    print("⬇️ Pulling Trivy image...")

    client.images.pull("aquasec/trivy:0.50.0")

    print("✅ Trivy ready")
