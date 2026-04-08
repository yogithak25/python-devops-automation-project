import requests
import base64
import time
import urllib3
from config.env_loader import get_env
from kubernetes import client, config as k8s_config

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

config = get_env()

# Load kubeconfig
k8s_config.load_kube_config()
core_v1 = client.CoreV1Api()


# -----------------------------
# WAIT FOR ARGOCD
# -----------------------------
def wait_for_argocd(url):

    print("\n⏳ Waiting for ArgoCD...\n")

    for i in range(30):
        try:
            r = requests.get(url, timeout=5, verify=False)

            if r.status_code in [200, 307]:
                print("✅ ArgoCD Ready")
                return
        except:
            pass

        print(f"Waiting... ({i+1}/30)")
        time.sleep(10)

    raise Exception("❌ ArgoCD not reachable")


# -----------------------------
# GET INITIAL PASSWORD
# -----------------------------
def get_initial_password():

    print("\n🔑 Fetching ArgoCD initial password...\n")

    try:
        secret = core_v1.read_namespaced_secret(
            name="argocd-initial-admin-secret",
            namespace="argocd"
        )

        password = base64.b64decode(
            secret.data["password"]
        ).decode()

        print("✅ Initial password fetched")
        return password

    except Exception as e:
        raise Exception(f"❌ Failed to fetch password: {str(e)}")


# -----------------------------
# LOGIN
# -----------------------------
def login(url, password):

    r = requests.post(
        f"{url}/api/v1/session",
        json={
            "username": config["ARGOCD_USER"],
            "password": password
        },
        verify=False
    )

    if r.status_code != 200:
        raise Exception(f"❌ ArgoCD login failed: {r.text}")

    return r.json()["token"]


# -----------------------------
# ENSURE PASSWORD 
# -----------------------------
def ensure_password(url):

    print("\n🔐 Ensuring ArgoCD password...\n")

    # Try login with new password
    try:
        token = login(url, config["ARGOCD_NEW_PASSWORD"])
        print("✅ Password already set")
        return token
    except:
        pass

    # Use initial password
    initial_pwd = get_initial_password()
    token = login(url, initial_pwd)

    headers = {"Authorization": f"Bearer {token}"}

    r = requests.put(
        f"{url}/api/v1/account/password",
        headers=headers,
        json={
            "currentPassword": initial_pwd,
            "newPassword": config["ARGOCD_NEW_PASSWORD"]
        },
        verify=False
    )

    if r.status_code not in [200, 204]:
        raise Exception(f"❌ Password update failed: {r.text}")

    print("✅ Password updated")

    return login(url, config["ARGOCD_NEW_PASSWORD"])


# -----------------------------
# CHECK APP EXISTS
# -----------------------------
def app_exists(url, token, name):

    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(
        f"{url}/api/v1/applications/{name}",
        headers=headers,
        verify=False
    )

    return r.status_code == 200


# -----------------------------
# CREATE OR UPDATE APP
# -----------------------------
def create_or_update_app(url, token, name, repo):

    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "metadata": {"name": name},
        "spec": {
            "project": "default",
            "source": {
                "repoURL": repo,
                "targetRevision": "main",
                "path": "."
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": "default"
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True
                }
            }
        }
    }

    if app_exists(url, token, name):
        print(f"🔄 Updating app: {name}")

        r = requests.put(
            f"{url}/api/v1/applications/{name}",
            headers=headers,
            json=payload,
            verify=False
        )

        if r.status_code in [200]:
            print(f"✅ {name} updated")
        else:
            raise Exception(f"❌ Update failed: {r.text}")

    else:
        print(f"🚀 Creating app: {name}")

        r = requests.post(
            f"{url}/api/v1/applications",
            headers=headers,
            json=payload,
            verify=False
        )

        if r.status_code in [200, 201]:
            print(f"✅ {name} created")
        else:
            raise Exception(f"❌ Create failed: {r.text}")


# -----------------------------
# VERIFY APP
# -----------------------------
def verify_app(url, token, name):

    if app_exists(url, token, name):
        print(f"✅ Verified app: {name}")
    else:
        raise Exception(f"❌ App verification failed: {name}")


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def setup_argocd():

    print("\n🚀 ARGOCD CONFIGURATION STARTED\n")

    url = config["ARGOCD_URL"]

    wait_for_argocd(url)

    token = ensure_password(url)

    apps = [
        {
            "name": "java-app",
            "repo": "https://github.com/yogithak25/devops-project-k8s-manifests.git"
        },
        {
            "name": "python-app",
            "repo": "https://github.com/yogithak25/python-devops-k8s-manifests.git"
        }
    ]

    for app in apps:
        create_or_update_app(url, token, app["name"], app["repo"])
        verify_app(url, token, app["name"])

    print("\n✅ ArgoCD FULLY CONFIGURED SUCCESSFULLY\n")
