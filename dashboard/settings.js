const fs = require("fs");

const readSecret = (name) =>
    fs.readFileSync(`/run/bike-dashboard/${name}`, "utf8").trim();

module.exports = {
    flowFile: "flows.json",
    credentialSecret: readSecret("credential-secret"),
    functionGlobalContext: {
        analyticsToken: readSecret("analytics.token"),
    },
    https: {
        key: fs.readFileSync("/run/bike-certs/server.key"),
        cert: fs.readFileSync("/run/bike-certs/server.crt"),
    },
    adminAuth: {
        type: "credentials",
        users: [{
            username: "admin",
            password: readSecret("admin.hash"),
            permissions: "*",
        }],
    },
    httpNodeAuth: {
        user: "admin",
        pass: readSecret("admin.hash"),
    },
    uiPort: 1880,
};
