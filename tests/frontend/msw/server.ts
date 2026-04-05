import { setupServer } from "../../../src/frontend/node_modules/msw/lib/node/index.mjs";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);
