import requests
from config.env_loader import get_env

config = get_env()


# -----------------------------
# AUTH
# -----------------------------
def auth():
    return (config["JENKINS_USER"], config["JENKINS_TOKEN"])


# -----------------------------
# GET CRUMB
# -----------------------------
def get_crumb():
    r = requests.get(
        f"{config['JENKINS_URL']}/crumbIssuer/api/json",
        auth=auth()
    )

    if r.status_code != 200:
        raise Exception("❌ Failed to fetch Jenkins crumb")

    data = r.json()
    return {data["crumbRequestField"]: data["crumb"]}


# -----------------------------
# TRIGGER PIPELINE
# -----------------------------
def trigger_pipeline(job_name):

    print(f"\n🚀 Triggering {job_name}...\n")

    url = f"{config['JENKINS_URL']}/job/{job_name}/build"

    headers = get_crumb()

    r = requests.post(
        url,
        auth=auth(),
        headers=headers
    )

    if r.status_code in [200, 201, 202]:
        print(f"✅ {job_name} triggered successfully!\n")
    else:
        print(f"❌ Failed to trigger {job_name}")
        print("Response:", r.text)


# -----------------------------
# MENU (USER INPUT)
# -----------------------------
def main():

    print("\n🎯 PIPELINE TRIGGER MENU\n")
    print("1️⃣  Java Pipeline")
    print("2️⃣  Python Pipeline\n")

    user_input = input("👉 Enter your choice (java/python): ").strip().lower()

    pipelines = {
        "java": "java-devops-pipeline",
        "python": "python-devops-pipeline"
    }

    if user_input in pipelines:
        trigger_pipeline(pipelines[user_input])
    else:
        print("\n❌ Invalid input!")
        print("👉 Please enter ONLY: java OR python\n")


# -----------------------------
# ENTRY
# -----------------------------
if __name__ == "__main__":
    main()
