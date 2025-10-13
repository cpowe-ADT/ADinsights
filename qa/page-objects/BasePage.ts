import type { Page } from "@playwright/test";

abstract class BasePage {
  protected readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  protected async goto(path: string): Promise<void> {
    await this.page.goto(path);
    await this.waitForNetworkIdle();
  }

  protected async waitForNetworkIdle(): Promise<void> {
    await this.page.waitForLoadState("networkidle");
  }
}

export default BasePage;
