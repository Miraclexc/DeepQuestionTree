import { expect, test } from "@playwright/test";

const goal = "Assess battery recycling policy impacts";
const waitTimeout = Number(process.env.PLAYWRIGHT_ASSERT_TIMEOUT_MS ?? 30000);

test("browser smoke covers create, stop, resume and report opening", async ({
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

    page.once("dialog", async (dialog) => {
        await dialog.accept();
    });
    await page.getByRole("button", { name: "Stop & Report" }).click();
    await expect(page.getByText("Exploration Report")).toBeVisible({
        timeout: waitTimeout,
    });
    await page.getByRole("button", { name: "Close report" }).click();
    await expect(page.getByText("Exploration Report")).toHaveCount(0);

    await page.locator(".react-flow__node").first().click();
    await expect(page.getByText("Node Details")).toBeVisible({
        timeout: waitTimeout,
    });

    const sessionRow = page
        .getByRole("button", { name: new RegExp(goal, "i") })
        .first()
        .locator("xpath=..");
    await sessionRow.hover();
    await sessionRow.getByRole("button", { name: "Resume Session" }).click();

    await expect(page.locator(".react-flow__node").first()).toBeVisible({
        timeout: waitTimeout,
    });
    await expect(page.getByText("Node Details")).toHaveCount(0);
    await expect(page.getByText("Exploration Report")).toHaveCount(0);
});
