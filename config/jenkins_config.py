import time
import requests
import json
import docker
import os
from config.env_loader import get_env

config = get_env()

client = docker.from_env()
CONTAINER_NAME = "jenkins"
ENV_FILE = "env.txt"


# -----------------------------
# UPDATE ENV
# -----------------------------
def update_env(key, value):
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()

    found = False

    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True

    if not found:
        lines.append(f"{key}={value}\n")

    with open(ENV_FILE, "w") as f:
        f.writelines(lines)

    print(f"✅ {key} updated")


# -----------------------------
# WAIT FOR JENKINS
# -----------------------------
def wait_for_jenkins():
    print("\n⏳ Waiting for Jenkins...\n")

    for i in range(40):
        try:
            r = requests.get(f"{config['JENKINS_URL']}/login")
            if r.status_code == 200:
                print("✅ Jenkins Ready")
                return
        except:
            pass

        print(f"Waiting... {i+1}/40")
        time.sleep(5)

    raise Exception("❌ Jenkins not reachable")
# -----------------------------
# ENSURE ADMIN PASSWORD 
# -----------------------------
def ensure_jenkins_password():

    print("\n🔐 Ensuring Jenkins password...\n")

    user = config["JENKINS_USER"]
    env_password = config["JENKINS_PASSWORD"]

    def can_login(pwd):
        try:
            r = requests.get(
                f"{config['JENKINS_URL']}/api/json",
                auth=(user, pwd),
                timeout=5
            )
            return r.status_code == 200
        except:
            return False

    if can_login(env_password):
        print("✅ Jenkins already using env password")
        return

    print("⚠️ Trying initial password...")

    initial_pwd = get_initial_password()

    if not initial_pwd:
        raise Exception("❌ Initial password not found")

    if not can_login(initial_pwd):
        raise Exception("❌ Cannot login with initial password")

    session = requests.Session()
    session.auth = (user, initial_pwd)

    crumb = session.get(
        f"{config['JENKINS_URL']}/crumbIssuer/api/json"
    ).json()

    session.headers.update({
        crumb["crumbRequestField"]: crumb["crumb"]
    })

    script = f"""
import jenkins.model.*
import hudson.security.*

def instance = Jenkins.instance

def hudsonRealm = new HudsonPrivateSecurityRealm(false)
hudsonRealm.createAccount("{user}", "{env_password}")

instance.setSecurityRealm(hudsonRealm)

def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
instance.setAuthorizationStrategy(strategy)

instance.save()

println("USER RESET DONE")
"""

    r = session.post(
        f"{config['JENKINS_URL']}/scriptText",
        data={"script": script}
    )

    if r.status_code != 200:
        raise Exception(f"❌ Password update failed: {r.text}")

    print("✅ Password updated")

    # Restart Jenkins
    client.containers.get("jenkins").restart()

    print("⏳ Waiting for Jenkins after restart...")

    for i in range(20):
        if can_login(env_password):
            print("✅ Login successful with env password")
            return
        time.sleep(5)

    raise Exception("❌ Password update failed after restart")

# -----------------------------
# GET INITIAL PASSWORD
# -----------------------------
def get_initial_password():
    try:
        container = client.containers.get(CONTAINER_NAME)
        result = container.exec_run(
            "cat /var/jenkins_home/secrets/initialAdminPassword"
        )
        return result.output.decode().strip()
    except:
        return None


# -----------------------------
# AUTH
# -----------------------------
def get_auth():
    token = config.get("JENKINS_TOKEN")

    if token:
        return (config["JENKINS_USER"], token)

    return (config["JENKINS_USER"], get_initial_password())


# -----------------------------
# DISABLE SETUP WIZARD
# -----------------------------
def disable_setup_wizard():
    print("\n⚙️ Disabling setup wizard...\n")

    container = client.containers.get(CONTAINER_NAME)

    container.exec_run(
        "bash -c 'echo 2.0 > /var/jenkins_home/jenkins.install.UpgradeWizard.state'"
    )

    print("✅ Setup wizard disabled")


# -----------------------------
# RESTART JENKINS
# -----------------------------
def restart_jenkins():
    print("\n🔄 Restarting Jenkins...\n")

    container = client.containers.get(CONTAINER_NAME)
    container.restart()

    time.sleep(20)

    print("✅ Jenkins restarted")


# -----------------------------
# CRUMB
# -----------------------------
def get_crumb():
    try:
        r = requests.get(
            f"{config['JENKINS_URL']}/crumbIssuer/api/json",
            auth=get_auth()
        )
        if r.status_code == 200:
            data = r.json()
            return {data["crumbRequestField"]: data["crumb"]}
    except:
        pass
    return {}


# -----------------------------
# RUN GROOVY
# -----------------------------
def run_groovy(script):
    headers = get_crumb()

    r = requests.post(
        f"{config['JENKINS_URL']}/scriptText",
        auth=get_auth(),
        headers=headers,
        data={"script": script}
    )

    return r.text
# -----------------------------
# WAIT FOR JENKINS
# -----------------------------
def wait_for_jenkins_ready():

    print("\n⏳ Waiting for Jenkins fully ready (plugin manager)...\n")

    for i in range(40):
        try:
            r = requests.get(
                f"{config['JENKINS_URL']}/pluginManager/api/json?depth=1",
                auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"]),
                timeout=5
            )

            if r.status_code == 200 and "plugins" in r.text:
                print("✅ Jenkins fully ready")
                return

        except:
            pass

        print(f"Waiting Jenkins... {i+1}/40")
        time.sleep(5)

    raise Exception("❌ Jenkins not fully ready")


# -----------------------------
# GENERATE TOKEN
# -----------------------------
def generate_token():

    print("\n🔑 Generating Jenkins API Token...\n")

    token = config.get("JENKINS_TOKEN")

    # -----------------------------
    # Reuse if valid
    # -----------------------------
    if token:
        r = requests.get(
            f"{config['JENKINS_URL']}/api/json",
            auth=(config["JENKINS_USER"], token)
        )
        if r.status_code == 200:
            print("✅ Token already valid")
            return token

    initial_pwd = get_initial_password()

    if not initial_pwd:
        raise Exception("❌ Initial password not found")

    # -----------------------------
    # 🔥 USE SESSION 
    # -----------------------------
    session = requests.Session()
    session.auth = (config["JENKINS_USER"], initial_pwd)

    # -----------------------------
    # STEP 1: GET CRUMB (WITH SESSION)
    # -----------------------------
    crumb_res = session.get(
        f"{config['JENKINS_URL']}/crumbIssuer/api/json"
    )

    if crumb_res.status_code != 200:
        raise Exception(f"❌ Failed to get crumb: {crumb_res.text}")

    crumb_data = crumb_res.json()

    session.headers.update({
        crumb_data["crumbRequestField"]: crumb_data["crumb"]
    })

    # -----------------------------
    # STEP 2: GENERATE TOKEN (SAME SESSION)
    # -----------------------------
    url = f"{config['JENKINS_URL']}/user/{config['JENKINS_USER']}/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken"

    r = session.post(
        url,
        data={"newTokenName": "devops-token"}
    )

    if r.status_code != 200:
        raise Exception(f"❌ Token generation failed: {r.text}")

    data = r.json()
    token = data["data"]["tokenValue"]

    update_env("JENKINS_TOKEN", token)

    print("✅ Jenkins API token generated")

    return token


# -----------------------------
# INSTALL PLUGINS
# -----------------------------
def install_plugins():

    print("\n📦 Installing plugins...\n")

    # 🔥 Ensure Jenkins is ready
    wait_for_jenkins_ready()

    plugins = [
        "workflow-aggregator",
        "git",
        "github",
        "pipeline-stage-view",
        "docker-workflow",
        "kubernetes",
        "sonar",
        "config-file-provider",
        "maven-plugin",
        "pipeline-maven"
    ]

    r = requests.get(
        f"{config['JENKINS_URL']}/pluginManager/api/json?depth=1",
        auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"])
    )

    # 🔥 SAFE JSON parsing
    try:
        data = r.json()
    except:
        raise Exception(f"❌ Plugin API not ready: {r.text}")

    installed = [p["shortName"] for p in data.get("plugins", [])]

    to_install = [
        f'<install plugin="{p}@latest"/>'
        for p in plugins if p not in installed
    ]

    if not to_install:
        print("✅ Plugins already installed")
        return

    xml = f"<jenkins>{''.join(to_install)}</jenkins>"

    # 🔥 CRUMB REQUIRED AGAIN
    crumb_res = requests.get(
        f"{config['JENKINS_URL']}/crumbIssuer/api/json",
        auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"])
    )

    crumb_data = crumb_res.json()

    headers = {
        "Content-Type": "text/xml",
        crumb_data["crumbRequestField"]: crumb_data["crumb"]
    }

    requests.post(
        f"{config['JENKINS_URL']}/pluginManager/installNecessaryPlugins",
        auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"]),
        headers=headers,
        data=xml
    )

    print("⏳ Installing plugins... waiting 60s")
    time.sleep(60)
# -----------------------------
# CREDENTIALS EXISTS
# -----------------------------
def credential_exists(cid):

    r = requests.get(
        f"{config['JENKINS_URL']}/credentials/store/system/domain/_/api/json?depth=2",
        auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"])
    )

    if r.status_code != 200:
        return False

    data = r.json()

    def search(creds):
        for c in creds:
            if isinstance(c, dict):
                if c.get("id") == cid:
                    return True
                if "credentials" in c:
                    if search(c["credentials"]):
                        return True
        return False

    return search(data.get("credentials", []))


# -----------------------------
# ADD CREDENTIALS
# -----------------------------
def add_credentials():

    print("\n🔐 Adding credentials...\n")

    url = f"{config['JENKINS_URL']}/credentials/store/system/domain/_/createCredentials"

    crumb_res = requests.get(
        f"{config['JENKINS_URL']}/crumbIssuer/api/json",
        auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"])
    )

    crumb_data = crumb_res.json()

    headers = {
        crumb_data["crumbRequestField"]: crumb_data["crumb"]
    }

    def create(cid, user, pwd):

        if credential_exists(cid):
            print(f"✅ {cid} exists")
            return

        payload = {
            "": "0",
            "credentials": {
                "scope": "GLOBAL",
                "id": cid,
                "username": user,
                "password": pwd,
                "$class": "com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl"
            }
        }

        r = requests.post(
            url,
            auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"]),
            headers=headers,
            data={"json": json.dumps(payload)}
        )

        if r.status_code in [200, 201, 204]:
            print(f"✅ {cid} created")
        else:
            print(f"❌ {cid} failed: {r.text}")

    create("github-cred", config["GITHUB_USER"], config["GITHUB_TOKEN"])
    create("dockerhub-cred", config["DOCKER_USER"], config["DOCKER_PASS"])
    create("nexus-cred", config["NEXUS_USER"], config["NEXUS_PASSWORD"])
# -----------------------------
# ENSURE SONAR TOKEN CREDENTIALS
# -----------------------------
def ensure_sonar_token_credential():

    print("\n🔐 Ensuring sonar-token credential...\n")

    url = f"{config['JENKINS_URL']}/credentials/store/system/domain/_/createCredentials"

    # Get crumb
    crumb_res = requests.get(
        f"{config['JENKINS_URL']}/crumbIssuer/api/json",
        auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"])
    )
    crumb = crumb_res.json()

    headers = {
        crumb["crumbRequestField"]: crumb["crumb"]
    }

    # ✅ Check existence
    if credential_exists("sonar-token"):
        print("✅ sonar-token credential already exists")
        return

    payload = {
        "": "0",
        "credentials": {
            "scope": "GLOBAL",
            "id": "sonar-token",
            "secret": config["SONAR_TOKEN"],  
            "description": "Sonar Token",
            "$class": "org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl"
        }
    }

    r = requests.post(
        url,
        auth=(config["JENKINS_USER"], config["JENKINS_TOKEN"]),
        headers=headers,
        data={"json": json.dumps(payload)}
    )

    if r.status_code in [200, 201, 204]:
        print("✅ sonar-token credential created")
    else:
        raise Exception(f"❌ Failed: {r.text}")


# -----------------------------
# CONFIGURE TOOLS
# -----------------------------
def configure_tools():

    print("\n⚙️ Configuring Maven + Sonar Scanner...\n")

    script = """
import jenkins.model.*
import hudson.tasks.Maven
import hudson.tools.*
import hudson.tasks.Maven.MavenInstaller
import hudson.plugins.sonar.*
import hudson.tools.InstallSourceProperty

def jenkins = Jenkins.instance

// ==========================
// MAVEN CONFIG (IDEMPOTENT)
// ==========================
def mavenDesc = jenkins.getDescriptorByType(Maven.DescriptorImpl)

def mavenName = "maven-3"
def mavenVersion = "3.9.9"

def existingMaven = mavenDesc.installations.find { it.name == mavenName }

def mavenInstaller = new MavenInstaller(mavenVersion)
def mavenProp = new InstallSourceProperty([mavenInstaller])

def newMaven = new Maven.MavenInstallation(mavenName, "", [mavenProp])

if (existingMaven == null) {

    mavenDesc.setInstallations(newMaven)
    mavenDesc.save()

    println("✅ Maven created")

} else {

    def props = existingMaven.getProperties()
    def needsUpdate = true

    if (props != null && !props.isEmpty()) {
        def installers = props[0].installers
        if (installers != null && installers.size() > 0) {
            if (installers[0].id == mavenVersion) {
                needsUpdate = false
            }
        }
    }

    if (needsUpdate) {
        mavenDesc.setInstallations(newMaven)
        mavenDesc.save()
        println("🔄 Maven updated")
    } else {
        println("✅ Maven already configured")
    }
}


// ==========================
// SONAR SCANNER CONFIG 
// ==========================
def sonarDesc = jenkins.getDescriptorByType(SonarRunnerInstallation.DescriptorImpl)

def sonarName = "sonar-scanner"
def sonarVersion = "8.0.1.6346"

def existingSonar = sonarDesc.installations.find { it.name == sonarName }

def sonarInstaller = new SonarRunnerInstaller(sonarVersion)
def sonarProp = new InstallSourceProperty([sonarInstaller])

def newSonar = new SonarRunnerInstallation(sonarName, "", [sonarProp])

if (existingSonar == null) {

    sonarDesc.setInstallations(newSonar)
    sonarDesc.save()

    println("✅ Sonar scanner created")

} else {

    def props = existingSonar.getProperties()
    def needsUpdate = true

    if (props != null && !props.isEmpty()) {
        def installers = props[0].installers
        if (installers != null && installers.size() > 0) {
            if (installers[0].id == sonarVersion) {
                needsUpdate = false
            }
        }
    }

    if (needsUpdate) {

        sonarDesc.setInstallations(newSonar)
        sonarDesc.save()

        println("🔄 Sonar scanner updated")

    } else {

        println("✅ Sonar scanner already configured")
    }
}

"""

    print(run_groovy(script))


# -----------------------------
# CONFIGURE SONAR
# -----------------------------
def configure_sonar():

    print("\n🔗 Configuring SonarQube...\n")

    script = f"""
import jenkins.model.*
import hudson.plugins.sonar.*
import org.jenkinsci.plugins.structs.describable.DescribableModel

def jenkins = Jenkins.instance
def desc = jenkins.getDescriptorByType(SonarGlobalConfiguration.class)

// Idempotent check
def existing = desc.installations.find {{ it.name == "sonarqube" }}

if (existing != null) {{
    println("SonarQube already configured")
    return
}}

def model = DescribableModel.of(SonarInstallation)

def instance = model.instantiate([
    name: "sonarqube",
    serverUrl: "{config['SONAR_URL']}",
    credentialsId: "sonar-token"
])

def installations = desc.installations as List
installations.add(instance)

desc.installations = installations
desc.save()

println("SonarQube configured")
"""

    print(run_groovy(script))

# -----------------------------
# NEXUS SETTINGS
# -----------------------------
def configure_nexus_settings():
    print("\n📦 Configuring Nexus settings.xml...\n")

    container = client.containers.get(CONTAINER_NAME)

    xml = f'''
<settings>
  <servers>
    <server>
      <id>nexus</id>
      <username>{config["NEXUS_USER"]}</username>
      <password>{config["NEXUS_PASSWORD"]}</password>
    </server>
  </servers>
</settings>
'''

    container.exec_run("mkdir -p /var/jenkins_home/.m2")

    container.exec_run(
        f"bash -c 'echo \"{xml}\" > /var/jenkins_home/.m2/settings.xml'"
    )

    print("✅ Nexus settings.xml configured")

# -----------------------------
# MAIN
# -----------------------------
def setup_jenkins():

    print("\n🚀 JENKINS FULL CONFIG STARTED\n")

    wait_for_jenkins()

    disable_setup_wizard()

    restart_jenkins()
    wait_for_jenkins()

    ensure_jenkins_password()

    generate_token()
    wait_for_jenkins_ready()

    install_plugins()
    add_credentials()
    ensure_sonar_token_credential()
    configure_tools()
    configure_sonar()
    configure_nexus_settings()

    print("\n✅ JENKINS FULLY CONFIGURED\n")
