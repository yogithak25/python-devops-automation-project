def main():

    print("\n🔥 DEVOPS AUTOMATION STARTED\n")

    # =====================================================
    # 🔹 PHASE 1: INSTALLATION
    # =====================================================
    print("\n📦 PHASE 1: INSTALLATION\n")

    # Step 1 → Python dependencies
    from installer.python_dependencies import install_requirements
    install_requirements()

    # Step 2 → Docker infra (Jenkins, Sonar, Nexus)
    from docker_manager import setup_infra
    setup_infra()

    # Step 3 → Maven
    from installer.maven import install_maven
    install_maven()

    # Step 4 → Kubernetes
    from installer.kubernetes import install_kubernetes
    install_kubernetes()

    # Step 5 → ArgoCD (on K8s)
    from installer.argocd import setup_argocd as install_argocd
    install_argocd()

    # Step 6 → Trivy
    from installer.trivy import setup_trivy
    setup_trivy()

    print("\n✅ PHASE 1 COMPLETED (INSTALLATION)\n")

    # =====================================================
    # 🔹 PHASE 2: CONFIGURATION
    # =====================================================
    print("\n⚙️ PHASE 2: CONFIGURATION\n")

    # 1️⃣ SonarQube → generates token
    from config.sonarqube_config import setup_sonarqube
    setup_sonarqube()

    # 2️⃣ Nexus → repo + creds
    from config.nexus_config import setup_nexus
    setup_nexus()

    # 3️⃣ Jenkins → password + token + plugins + tools + creds
    from config.jenkins_config import setup_jenkins
    setup_jenkins()

    # 4️⃣ GitHub → webhook / access
    from config.github_config import setup_github
    setup_github()

    # 5️⃣ ArgoCD → app deployment config
    from config.argocd_config import setup_argocd
    setup_argocd()

    print("\n✅ PHASE 2 COMPLETED (CONFIGURATION)\n")

    # =====================================================
    # 🔹 PHASE 3: PIPELINE SETUP
    # =====================================================
    print("\n🚀 PHASE 3: PIPELINE SETUP\n")

    from config.jenkins_pipeline import setup_pipelines
    setup_pipelines()

    print("\n🎉 FULL DEVOPS AUTOMATION COMPLETED SUCCESSFULLY!\n")


if __name__ == "__main__":
    main()
