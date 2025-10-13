import type { Page } from "@playwright/test";

import BasePage from "./BasePage";

class LoginPage extends BasePage {
  constructor(page: Page) {
    super(page);
  }

  async open(): Promise<void> {
    await this.goto("/login");
  }

  async fillEmail(value: string): Promise<void> {
    await this.page.getByLabel(/Email/i).fill(value);
  }

  async fillPassword(value: string): Promise<void> {
    await this.page.getByLabel(/Password/i).fill(value);
  }

  async submit(): Promise<void> {
    await this.page.getByRole("button", { name: /Sign In/i }).click();
    await this.waitForNetworkIdle();
  }

  async getErrorMessage(): Promise<string | null> {
    const error = this.page.getByRole("status").first();
    if (await error.isVisible()) {
      return (await error.innerText()).trim();
    }
    return null;
  }
}

export default LoginPage;
