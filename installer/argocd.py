import os
import time
import base64
import requests
from kubernetes import client, config as k8s_config, utils
from config.env_loader import get_env

# -----------------------------
# LOAD ENV
# -----------------------------
config = get_env()
EC2_IP_PUB = config['EC2_IP']

# -----------------------------
# LOAD KUBECONFIG
# -----------------------------
k8s_config.load_kube_config()

core_v1 = client.CoreV1Api()

# -----------------------------
# CONSTANTS
# -----------------------------
ARGOCD_NAMESPACE = "argocd"
ARGOCD_MANIFEST_URL = "https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"
LOCAL_MANIFEST = "/tmp/argocd-install.yaml"
NODEPORT = 32578


# -----------------------------
# CHECK NAMESPACE EXISTS
# -----------------------------
def namespace_exists():
    try:
        namespaces = core_v1.list_namespace().items
        return any(ns.metadata.name == ARGOCD_NAMESPACE for ns in namespaces)
    except:
        return False


# -----------------------------
# CREATE NAMESPACE
# -----------------------------
def create_namespace():
    print("\n📦 Creating argocd namespace...\n")

    ns = client.V1Namespace(
        metadata=client.V1ObjectMeta(name=ARGOCD_NAMESPACE)
    )
    core_v1.create_namespace(ns)

    print("✅ Namespace created")


# -----------------------------
# CHECK ARGOCD INSTALLED
# -----------------------------
def argocd_installed():
    try:
        pods = core_v1.list_namespaced_pod(ARGOCD_NAMESPACE).items
        return len(pods) > 0
    except:
        return False


# -----------------------------
# DOWNLOAD MANIFEST (IDEMPOTENT)
# -----------------------------
def download_manifest():
    if os.path.exists(LOCAL_MANIFEST):
        print("✅ Manifest already exists (idempotent)")
        return

    print("\n⬇️ Downloading ArgoCD manifest...\n")

    response = requests.get(ARGOCD_MANIFEST_URL)

    if response.status_code != 200:
        raise Exception("❌ Failed to download ArgoCD manifest")

    with open(LOCAL_MANIFEST, "w") as f:
        f.write(response.text)

    print("✅ Manifest downloaded")


# -----------------------------
# INSTALL ARGOCD
# -----------------------------
def install_argocd():
    print("\n🚀 Installing ArgoCD...\n")

    download_manifest()

    try:
        utils.create_from_yaml(
            client.ApiClient(),
            LOCAL_MANIFEST,
            namespace=ARGOCD_NAMESPACE
        )
        print("✅ ArgoCD manifests applied")

    except Exception as e:
        if "AlreadyExists" in str(e):
            print("✅ ArgoCD already installed")
        else:
            raise e


# -----------------------------
# PATCH SERVICE
# -----------------------------
def patch_service():
    print("\n🔧 Ensuring NodePort service...\n")

    svc = core_v1.read_namespaced_service(
        name="argocd-server",
        namespace=ARGOCD_NAMESPACE
    )

    if (
        svc.spec.type == "NodePort"
        and svc.spec.ports[0].node_port == NODEPORT
    ):
        print("✅ Service already configured")
        return

    svc.spec.type = "NodePort"
    svc.spec.ports[0].node_port = NODEPORT

    core_v1.patch_namespaced_service(
        name="argocd-server",
        namespace=ARGOCD_NAMESPACE,
        body=svc
    )

    print(f"✅ Service exposed on NodePort {NODEPORT}")


# -----------------------------
# WAIT FOR READY
# -----------------------------
def wait_for_ready():
    print("\n⏳ Waiting for ArgoCD pods...\n")

    for i in range(40):
        pods = core_v1.list_namespaced_pod(ARGOCD_NAMESPACE).items

        if pods:
            ready = all(
                p.status.phase == "Running" and
                all(c.ready for c in (p.status.container_statuses or []))
                for p in pods
            )

            if ready:
                print("✅ ArgoCD is Ready")
                return

        print(f"Waiting... {i+1}/40")
        time.sleep(5)

    raise Exception("❌ ArgoCD not ready")


# -----------------------------
# GET PASSWORD
# -----------------------------
def get_initial_password():
    print("\n🔑 Fetching ArgoCD password...\n")

    try:
        secret = core_v1.read_namespaced_secret(
            name="argocd-initial-admin-secret",
            namespace=ARGOCD_NAMESPACE
        )

        password = base64.b64decode(
            secret.data["password"]
        ).decode()

        return password

    except:
        print("⚠️ Password not ready yet")
        return None


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def setup_argocd():
    print("\n🚀 ArgoCD Setup Started\n")

    # Namespace
    if not namespace_exists():
        create_namespace()
    else:
        print("✅ Namespace already exists")

    # Install
    if not argocd_installed():
        install_argocd()
    else:
        print("✅ ArgoCD already installed")

    # Wait for pods
    wait_for_ready()

    # Patch service
    patch_service()


    print("\n🌐 Access ArgoCD UI:")
    print(f"http://{EC2_IP_PUB}:{NODEPORT}")

    print("\n✅ ArgoCD READY\n")
