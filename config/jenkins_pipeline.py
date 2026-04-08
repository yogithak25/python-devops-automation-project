import requests
from config.env_loader import get_env

config = get_env()


# -----------------------------
# SESSION (BEST PRACTICE)
# -----------------------------
def get_session():
    session = requests.Session()
    session.auth = (config["JENKINS_USER"], config["JENKINS_TOKEN"])

    # Get crumb
    r = session.get(f"{config['JENKINS_URL']}/crumbIssuer/api/json")

    if r.status_code == 200:
        crumb = r.json()
        session.headers.update({
            crumb["crumbRequestField"]: crumb["crumb"]
        })

    return session


# -----------------------------
# CHECK JOB EXISTS
# -----------------------------
def job_exists(session, job_name):

    r = session.get(
        f"{config['JENKINS_URL']}/job/{job_name}/api/json"
    )

    return r.status_code == 200


# -----------------------------
# CREATE OR UPDATE PIPELINE
# -----------------------------
def create_or_update_pipeline(job_name, repo_url, branch="main"):

    session = get_session()

    print(f"\n🔧 Processing pipeline: {job_name}")

    xml = f"""
<flow-definition plugin="workflow-job">
  <actions/>
  <description>{job_name}</description>
  <keepDependencies>false</keepDependencies>

  <properties>
    <org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
      <triggers>
        <com.cloudbees.jenkins.GitHubPushTrigger plugin="github">
          <spec></spec>
        </com.cloudbees.jenkins.GitHubPushTrigger>
      </triggers>
    </org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
  </properties>

  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition">
    <scm class="hudson.plugins.git.GitSCM">

      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>{repo_url}</url>
          <credentialsId>github-cred</credentialsId>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>

      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/{branch}</name>
        </hudson.plugins.git.BranchSpec>
      </branches>

    </scm>

    <scriptPath>Jenkinsfile</scriptPath>
  </definition>

</flow-definition>
"""

    headers = {"Content-Type": "application/xml"}

    # -----------------------------
    # UPDATE IF EXISTS
    # -----------------------------
    if job_exists(session, job_name):
        print(f"🔄 Updating existing pipeline: {job_name}")

        r = session.post(
            f"{config['JENKINS_URL']}/job/{job_name}/config.xml",
            headers=headers,
            data=xml
        )

        if r.status_code == 200:
            print(f"✅ {job_name} updated")
        else:
            raise Exception(f"❌ Failed to update {job_name}: {r.text}")

    # -----------------------------
    # CREATE IF NOT EXISTS
    # -----------------------------
    else:
        print(f"🚀 Creating pipeline: {job_name}")

        r = session.post(
            f"{config['JENKINS_URL']}/createItem?name={job_name}",
            headers=headers,
            data=xml
        )

        if r.status_code in [200, 201]:
            print(f"✅ {job_name} created")
        else:
            raise Exception(f"❌ Failed to create {job_name}: {r.text}")


# -----------------------------
# VERIFY PIPELINE
# -----------------------------
def verify_pipeline(job_name):

    session = get_session()

    r = session.get(
        f"{config['JENKINS_URL']}/job/{job_name}/api/json"
    )

    if r.status_code == 200:
        print(f"✅ Verified pipeline: {job_name}")
    else:
        raise Exception(f"❌ Verification failed for {job_name}")


# -----------------------------
# MAIN
# -----------------------------
def setup_pipelines():

    print("\n🚀 JENKINS PIPELINE SETUP STARTED\n")

    pipelines = [
        {
            "name": "java-devops-pipeline",
            "repo": "https://github.com/yogithak25/end-to-end-devops-project.git"
        },
        {
            "name": "python-devops-pipeline",
            "repo": "https://github.com/yogithak25/python-devops-project.git"
        }
    ]

    for p in pipelines:
        create_or_update_pipeline(p["name"], p["repo"])
        verify_pipeline(p["name"])

    print("\n✅ Jenkins Pipelines Configured Successfully\n")
