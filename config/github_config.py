import requests
from config.env_loader import get_env

config = get_env()

BASE_API = "https://api.github.com"


# -----------------------------
# COMMON HEADERS
# -----------------------------
def headers():
    return {
        "Authorization": f"token {config['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json"
    }


# -----------------------------
# GET ALL WEBHOOKS
# -----------------------------
def get_hooks(repo):

    url = f"{BASE_API}/repos/{config['GITHUB_USER']}/{repo}/hooks"

    r = requests.get(url, headers=headers())

    if r.status_code != 200:
        raise Exception(f"❌ Failed to fetch hooks for {repo}: {r.text}")

    return r.json()


# -----------------------------
# CHECK WEBHOOK EXISTS
# -----------------------------
def webhook_exists(repo):

    try:
        hooks = get_hooks(repo)
    except Exception as e:
        print(e)
        return False

    target_url = f"{config['JENKINS_URL']}/github-webhook/"

    for hook in hooks:
        if hook.get("config", {}).get("url") == target_url:
            return True

    return False


# -----------------------------
# CREATE WEBHOOK
# -----------------------------
def create_webhook(repo):

    print(f"\n🔗 Processing repo: {repo}")

    if webhook_exists(repo):
        print(f"✅ Webhook already exists for {repo}")
        return

    url = f"{BASE_API}/repos/{config['GITHUB_USER']}/{repo}/hooks"

    payload = {
        "name": "web",
        "active": True,
        "events": ["push"],
        "config": {
            "url": f"{config['JENKINS_URL']}/github-webhook/",
            "content_type": "json",
            "insecure_ssl": "0"
        }
    }

    r = requests.post(url, headers=headers(), json=payload)

    if r.status_code in [200, 201]:
        print(f"✅ Webhook created for {repo}")
    else:
        raise Exception(f"❌ Failed to create webhook for {repo}: {r.text}")


# -----------------------------
# VERIFY WEBHOOK
# -----------------------------
def verify_webhook(repo):

    target_url = f"{config['JENKINS_URL']}/github-webhook/"

    hooks = get_hooks(repo)

    for hook in hooks:
        if hook.get("config", {}).get("url") == target_url:
            print(f"✅ Verified webhook for {repo}")
            return True

    raise Exception(f"❌ Webhook verification failed for {repo}")


# -----------------------------
# MAIN FUNCTION
# -----------------------------
def setup_github():

    print("\n🚀 GITHUB WEBHOOK SETUP STARTED\n")

    repos = [
        "end-to-end-devops-project",   # Java repo
        "python-devops-project"        # Python repo
    ]

    for repo in repos:
        create_webhook(repo)
        verify_webhook(repo)

    print("\n✅ GitHub Webhooks Configured Successfully\n")
