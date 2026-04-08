import os
import time
import requests
from config.env_loader import get_env

config = get_env()
BASE_URL = config["SONAR_URL"]

ENV_FILE = "env.txt"


# -----------------------------
# WAIT FOR SONAR
# -----------------------------
def wait_for_sonar():
    print("\n⏳ Waiting for SonarQube...\n")

    for i in range(30):
        try:
            r = requests.get(f"{BASE_URL}/api/system/status")
            if r.status_code == 200:
                print("✅ SonarQube Ready")
                return
        except:
            pass

        print(f"Waiting... ({i+1}/30)")
        time.sleep(5)

    raise Exception("❌ SonarQube not reachable")


# -----------------------------
# AUTH HANDLER (IDEMPOTENT)
# -----------------------------
def get_auth():
    try:
        r = requests.get(
            f"{BASE_URL}/api/authentication/validate",
            auth=(config["SONAR_USER"], config["SONAR_NEW_PASSWORD"])
        )
        if r.status_code == 200 and r.json().get("valid"):
            return (config["SONAR_USER"], config["SONAR_NEW_PASSWORD"])
    except:
        pass

    return (config["SONAR_USER"], config["SONAR_PASSWORD"])


# -----------------------------
# CHANGE PASSWORD
# -----------------------------
def change_password():
    print("\n🔐 Checking/Updating password...\n")

    # Check if already changed
    r = requests.get(
        f"{BASE_URL}/api/authentication/validate",
        auth=(config["SONAR_USER"], config["SONAR_NEW_PASSWORD"])
    )

    if r.status_code == 200 and r.json().get("valid"):
        print("✅ Password already updated")
        return

    response = requests.post(
        f"{BASE_URL}/api/users/change_password",
        auth=(config["SONAR_USER"], config["SONAR_PASSWORD"]),
        data={
            "login": config["SONAR_USER"],
            "previousPassword": config["SONAR_PASSWORD"],
            "password": config["SONAR_NEW_PASSWORD"]
        }
    )

    if response.status_code in [200, 204]:
        print("✅ Password updated")
    else:
        raise Exception("❌ Password update failed")


# -----------------------------
# UPDATE ENV FILE
# -----------------------------
def update_env(key, value):
    lines = []

    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()

    updated = False
    found = False

    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            found = True
            if line.strip() != f"{key}={value}":
                lines[i] = f"{key}={value}\n"
                updated = True

    if not found:
        lines.append(f"{key}={value}\n")
        updated = True

    if updated:
        with open(ENV_FILE, "w") as f:
            f.writelines(lines)
        print(f"✅ {key} updated in env.txt")
    else:
        print(f"✅ {key} already up-to-date")


# -----------------------------
# VALIDATE TOKEN
# -----------------------------
def is_token_valid(token):
    try:
        r = requests.get(
            f"{BASE_URL}/api/authentication/validate",
            auth=(token, "")
        )
        return r.status_code == 200 and r.json().get("valid")
    except:
        return False


# -----------------------------
# GENERATE TOKEN (IDEMPOTENT)
# -----------------------------
def generate_token():
    print("\n🔑 Checking/Generating token...\n")

    existing_token = config.get("SONAR_TOKEN")

    # If token exists and valid → reuse
    if existing_token and is_token_valid(existing_token):
        print("✅ Existing SONAR_TOKEN is valid")
        return existing_token

    # Generate new token
    response = requests.post(
        f"{BASE_URL}/api/user_tokens/generate",
        auth=get_auth(),
        data={"name": f"devops-token-{int(time.time())}"}
    )

    if response.status_code != 200:
        raise Exception("❌ Token generation failed")

    token = response.json()["token"]

    update_env("SONAR_TOKEN", token)

    print("✅ Token generated")

    return token


# -----------------------------
# CREATE PROJECT (IDEMPOTENT)
# -----------------------------
def create_project(project_key, project_name):

    res = requests.get(
        f"{BASE_URL}/api/projects/search",
        auth=get_auth(),
        params={"projects": project_key}
    )

    if res.json().get("components"):
        print(f"✅ {project_name} already exists")
        return

    requests.post(
        f"{BASE_URL}/api/projects/create",
        auth=get_auth(),
        data={
            "project": project_key,
            "name": project_name
        }
    )

    print(f"✅ {project_name} created")


# -----------------------------
# QUALITY GATE
# -----------------------------
def create_quality_gate():

    gate_name = "custom-quality-gate"

    print("\n📊 Configuring Quality Gate...\n")

    res = requests.get(
        f"{BASE_URL}/api/qualitygates/list",
        auth=get_auth()
    )

    gate_id = None

    for g in res.json()["qualitygates"]:
        if g["name"] == gate_name:
            gate_id = g["id"]
            print("✅ Quality Gate already exists")
            break

    if not gate_id:
        res = requests.post(
            f"{BASE_URL}/api/qualitygates/create",
            auth=get_auth(),
            data={"name": gate_name}
        )
        gate_id = res.json()["id"]
        print("✅ Quality Gate created")

    # Check condition
    res = requests.get(
        f"{BASE_URL}/api/qualitygates/show",
        auth=get_auth(),
        params={"id": gate_id}
    )

    conditions = res.json()["conditions"]

    for c in conditions:
        if c["metric"] == "coverage":
            print("✅ Coverage condition already exists")
            return gate_name

    requests.post(
        f"{BASE_URL}/api/qualitygates/create_condition",
        auth=get_auth(),
        data={
            "gateId": gate_id,
            "metric": "coverage",
            "op": "LT",
            "error": "20"
        }
    )

    print("✅ Coverage condition added (>=20%)")

    return gate_name


# -----------------------------
# SET DEFAULT QUALITY GATE
# -----------------------------
def set_default_quality_gate(gate_name):

    requests.post(
        f"{BASE_URL}/api/qualitygates/set_as_default",
        auth=get_auth(),
        data={"name": gate_name}
    )

    print("✅ Set as default quality gate")


# -----------------------------
# ASSIGN QUALITY GATE
# -----------------------------
def assign_quality_gate(project_key, gate_name):

    requests.post(
        f"{BASE_URL}/api/qualitygates/select",
        auth=get_auth(),
        data={
            "projectKey": project_key,
            "gateName": gate_name
        }
    )

    print(f"✅ {project_key} linked to quality gate")


# -----------------------------
# WEBHOOK (IDEMPOTENT)
# -----------------------------
def add_webhook():

    print("\n🔗 Adding Jenkins webhook...\n")

    webhook_url = f"{config['JENKINS_URL']}/sonarqube-webhook/"

    response = requests.get(
        f"{BASE_URL}/api/webhooks/list",
        auth=get_auth()
    )

    for w in response.json().get("webhooks", []):
        if w["url"] == webhook_url:
            print("✅ Webhook already exists")
            return

    requests.post(
        f"{BASE_URL}/api/webhooks/create",
        auth=get_auth(),
        data={
            "name": "jenkins-webhook",
            "url": webhook_url
        }
    )

    print("✅ Webhook created")


# -----------------------------
# MAIN
# -----------------------------
def setup_sonarqube():

    print("\n🚀 SONARQUBE CONFIGURATION STARTED\n")

    wait_for_sonar()
    change_password()

    token = generate_token()

    create_project("java-devops-project", "java-devops-project")
    create_project("python-devops-project", "python-devops-project")

    gate = create_quality_gate()
    set_default_quality_gate(gate)

    assign_quality_gate("java-devops-project", gate)
    assign_quality_gate("python-devops-project", gate)

    add_webhook()

    print("\n✅ SONARQUBE FULLY CONFIGURED\n")

    return token
