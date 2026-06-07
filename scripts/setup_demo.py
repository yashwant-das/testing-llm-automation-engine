import os


def setup_demo():
    print("🚀 Setting up Testing LLM Automation Engine Demo...")

    # 1. content
    test_content = """
import { test, expect } from '@playwright/test';

test('login failure demo', async ({ page }) => {
  // 1. Go to a real site
  await page.goto('https://the-internet.herokuapp.com/login');

  // 2. Try to click a button that DOES NOT EXIST (Intentional Failure)
  // This should trigger the Healer Agent
  console.log('Attempting to click non-existent button...');
  await page.click('#this-id-does-not-exist', { timeout: 2000 });
});
"""

    # 2. Path
    target_dir = "tests/generated"
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, "demo_broken.spec.ts")

    with open(file_path, "w") as f:
        f.write(test_content)

    print(f"✅ Created broken test file: {file_path}")

    # 3. Clean artifacts
    artifacts_dir = "tests/artifacts"
    if os.path.exists(artifacts_dir):
        for f in os.listdir(artifacts_dir):
            os.remove(os.path.join(artifacts_dir, f))
        print(f"🧹 Cleaned {artifacts_dir}/ (Ready for fresh artifacts)")
    else:
        os.makedirs(artifacts_dir)

    print("\n🎉 Demo Ready!")
    print(
        "Option A (CLI): python -m src.agents.healer tests/generated/demo_broken.spec.ts"
    )
    print(
        "                (Optional: Add '--max-retries 3' to configure healing attempts)"
    )
    print(
        "Option B (UI):  uv run src/app.py -> 'Healing Pipeline' tab -> Upload 'tests/generated/demo_broken.spec.ts'"
    )


if __name__ == "__main__":
    setup_demo()
