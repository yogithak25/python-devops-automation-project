import os
import pip


def install_requirements():

    print("\n📦 Installing Python dependencies...\n")

    marker = ".deps_installed"

    # -----------------------------
    # IDEMPOTENT CHECK
    # -----------------------------
    if os.path.exists(marker):
        print("✅ Dependencies already installed")
        return

    # -----------------------------
    # INSTALL USING pip (NO subprocess)
    # -----------------------------
    print("⬇️ Installing dependencies...")

    pip.main(["install", "-r", "requirements.txt"])

    # -----------------------------
    # CREATE MARKER
    # -----------------------------
    open(marker, "w").close()

    print("\n✅ Dependencies installed successfully\n")
