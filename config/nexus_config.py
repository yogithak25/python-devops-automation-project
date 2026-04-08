import time
import requests
import docker
from config.env_loader import get_env

# -----------------------------
# LOAD CONFIG
# -----------------------------
config = get_env()
BASE_URL = config["NEXUS_URL"]

client = docker.from_env()
CONTAINER_NAME = "nexus"


# -----------------------------
# WAIT FOR NEXUS
# -----------------------------
def wait_for_nexus():
    print("\n⏳ Waiting for Nexus...\n")

    for i in range(40):
        try:
            r = requests.get(f"{BASE_URL}/service/rest/v1/status")
            if r.status_code in [200, 401]:
                print("✅ Nexus Ready")
                return
        except:
            pass

        print(f"Waiting... ({i+1}/40)")
        time.sleep(5)

    raise Exception("❌ Nexus not reachable")


# -----------------------------
# GET INITIAL PASSWORD (DOCKER)
# -----------------------------
def get_initial_password():
    print("\n🔑 Fetching initial admin password...\n")

    try:
        container = client.containers.get(CONTAINER_NAME)

        result = container.exec_run("cat /nexus-data/admin.password")
        pwd = result.output.decode().strip()

        if pwd:
            print("✅ Initial password fetched from container")
            return pwd

    except Exception:
        pass

    print("ℹ️ Initial password not found (already changed)")
    return None


# -----------------------------
# CHECK PASSWORD UPDATED
# -----------------------------
def is_password_changed():
    try:
        r = requests.get(
            f"{BASE_URL}/service/rest/v1/status",
            auth=(config["NEXUS_USER"], config["NEXUS_PASSWORD"])
        )
        return r.status_code == 200
    except:
        return False


# -----------------------------
# CHANGE PASSWORD
# -----------------------------
def change_password(initial_pwd):
    if is_password_changed():
        print("✅ Nexus password already updated (idempotent)")
        return

    if not initial_pwd:
        raise Exception("❌ Initial password required for first-time setup")

    print("\n🔐 Changing Nexus admin password...\n")

    response = requests.put(
        f"{BASE_URL}/service/rest/v1/security/users/admin/change-password",
        auth=("admin", initial_pwd),
        headers={"Content-Type": "text/plain"},
        data=config["NEXUS_PASSWORD"]
    )

    if response.status_code in [200, 204]:
        print("✅ Password changed successfully")
    else:
        raise Exception(f"❌ Password change failed: {response.text}")


# -----------------------------
# CHECK REPO EXISTS
# -----------------------------
def repo_exists(repo_name):
    r = requests.get(
        f"{BASE_URL}/service/rest/v1/repositories",
        auth=(config["NEXUS_USER"], config["NEXUS_PASSWORD"])
    )

    if r.status_code != 200:
        raise Exception("❌ Unable to fetch repositories")

    repos = [repo["name"] for repo in r.json()]
    return repo_name in repos


# -----------------------------
# CREATE MAVEN HOSTED REPO
# -----------------------------
def create_maven_repo():
    repo_name = "maven-releases-custom"

    if repo_exists(repo_name):
        print("✅ Maven repo already exists (idempotent)")
        return repo_name

    print("\n📦 Creating Maven hosted repository...\n")

    payload = {
        "name": repo_name,
        "online": True,
        "storage": {
            "blobStoreName": "default",
            "strictContentTypeValidation": True,
            "writePolicy": "ALLOW"
        },
        "maven": {
            "versionPolicy": "RELEASE",
            "layoutPolicy": "STRICT"
        }
    }

    response = requests.post(
        f"{BASE_URL}/service/rest/v1/repositories/maven/hosted",
        auth=(config["NEXUS_USER"], config["NEXUS_PASSWORD"]),
        json=payload
    )

    if response.status_code in [200, 201]:
        print("✅ Maven repository created")
    else:
        raise Exception(f"❌ Repo creation failed: {response.text}")

    return repo_name


# -----------------------------
# GET REPO URL
# -----------------------------
def get_repo_url(repo_name):
    repo_url = f"{BASE_URL}/repository/{repo_name}/"
    print(f"✅ Repo URL: {repo_url}")
    return repo_url


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def setup_nexus():
    print("\n🚀 NEXUS CONFIGURATION STARTED\n")

    wait_for_nexus()

    # Step 1: Password setup
    initial_pwd = get_initial_password()
    change_password(initial_pwd)

    # Step 2: Repository setup
    repo_name = create_maven_repo()
    repo_url = get_repo_url(repo_name)

    print("\n✅ NEXUS FULLY CONFIGURED\n")

    return repo_url
