import {
    expect,
    test,
} from "../../../src/frontend/node_modules/@playwright/test/index.mjs";

const goal = "Assess battery recycling policy impacts";
const waitTimeout = Number(process.env.PLAYWRIGHT_ASSERT_TIMEOUT_MS ?? 30000);

test("browser smoke covers create session, tree navigation and report opening", async ({
    page,
}) => {
    await page.goto("/");

    await expect(
        page.getByRole("button", { name: "New Exploration" }),
    ).toBeVisible();

    await page.getByRole("button", { name: "New Exploration" }).click();
    await page
        .getByPlaceholder(
            "e.g. Analyze the impact of quantum computing on cryptography...",
        )
        .fill(goal);
    await page.getByRole("button", { name: "Start Analysis" }).click();

    await expect(page.getByText(goal).first()).toBeVisible({
        timeout: waitTimeout,
    });
    await expect(page.locator(".react-flow__node").first()).toBeVisible({
        timeout: waitTimeout,
    });

    await page.locator(".react-flow__node").first().click();
    await expect(page.getByText("Node Details")).toBeVisible({
        timeout: waitTimeout,
    });
    await page.getByRole("button", { name: "Close node details" }).click();

    await page.getByRole("button", { name: "Generate Report" }).click();
    await expect(page.getByText("Exploration Report")).toBeVisible({
        timeout: waitTimeout,
    });
});
