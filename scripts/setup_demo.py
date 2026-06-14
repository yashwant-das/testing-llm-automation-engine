import os


def setup_demo():
    """Create a broken Playwright test fixture and clear old artifacts for a fresh demo run."""

    print("Setting up healing pipeline demo...")

    test_content = """\
import { test, expect } from '@playwright/test';

test('login with invalid selector', async ({ page }) => {
  await page.goto('https://the-internet.herokuapp.com/login');

  // FAILURE CASE: selector does not exist on the page — triggers healing pipeline
  await page.locator('#this-id-does-not-exist', { timeout: 2000 } as never);
});
"""

    target_dir = "tests/generated"
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, "demo_broken.spec.ts")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(test_content)

    print(f"Created: {file_path}")

    artifacts_dir = "tests/artifacts"
    if os.path.exists(artifacts_dir):
        removed = 0
        for f in os.listdir(artifacts_dir):
            os.remove(os.path.join(artifacts_dir, f))
            removed += 1
        if removed:
            print(f"Cleared {removed} artifact(s) from {artifacts_dir}/")
    else:
        os.makedirs(artifacts_dir)

    print("Ready.")
    print()
    print("  CLI:  python -m src.agents.healer tests/generated/demo_broken.spec.ts")
    print("  UI:   uv run python src/app.py  →  Healing Pipeline tab")


if __name__ == "__main__":
    setup_demo()
