const path = require("path");
const pkg = require("../package.json");

const raw = String(process.env.AI_DIRECTOR_OWNED_ELECTRON_DIST || "").trim();
if (!raw) {
  throw new Error("AI_DIRECTOR_OWNED_ELECTRON_DIST is required.");
}

module.exports = {
  ...pkg.build,
  electronVersion: "36.3.2",
  electronDist: path.resolve(raw),
  directories: {
    output: "dist",
    buildResources: "build",
  },
};
